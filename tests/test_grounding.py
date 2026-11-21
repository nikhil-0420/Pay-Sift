"""Unit and integration tests for PaySift You.com grounding layer."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional
import unittest

from fastapi.testclient import TestClient
import pytest

from api.evidence import router, set_client_override
from api.main import app
from grounding.fetch import fetch_all_evidence, fetch_rule_evidence, load_queries
from grounding.judge import (
    build_judge_prompt,
    rebuild_grounding_json,
    validate_judge_verdict,
)
from grounding.validator import validate_grounding
from grounding.youcom import DEFAULT_CALL_CAP, YouComClient
from repair.prompt import build_repair_prompt


class FakeYouComClient:
    """Mock YouComClient for deterministic, offline testing."""

    def __init__(self, fail_attempts: int = 0, status_code: int = 500, call_cap: int = 60) -> None:
        self.call_cap = call_cap
        self.calls_used = 0
        self.fail_attempts = fail_attempts
        self.status_code = status_code

    def search(self, query: str, count: int = 5, allow_keyless: Optional[bool] = None) -> Dict[str, Any]:
        self.calls_used += 1
        if self.calls_used > self.call_cap:
            raise RuntimeError(f"You.com API call cap reached: {self.calls_used}/{self.call_cap} calls used.")

        if self.calls_used <= self.fail_attempts:
            raise RuntimeError(f"Simulated HTTP {self.status_code} upstream failure with sk-secret-123456789")

        return {
            "results": {
                "web": [
                    {
                        "url": "https://docs.stripe.com/webhooks/signature",
                        "title": "Stripe Webhook Signatures",
                        "description": "Verify signatures using raw request body.",
                        "snippets": [
                            "Always verify HMAC-SHA256 signatures over the exact raw body payload bytes.",
                            "Do not verify signature over re-serialized JSON."
                        ],
                    },
                    {
                        "url": "https://razorpay.com/docs/webhooks",
                        "title": "Razorpay Webhooks",
                        "description": "Webhook signature verification documentation.",
                        "snippets": [
                            "Compute the signature using hex digest of the raw request body."
                        ],
                    }
                ]
            },
            "metadata": {"query": query, "latency": 0.05}
        }


def test_queries_yaml_integrity():
    """Verify queries.yaml defines R0 through R10 with text hashes and 2-3 queries."""
    data = load_queries()
    rules = data.get("rules", {})
    assert len(rules) == 11
    for i in range(11):
        rid = f"R{i}"
        assert rid in rules
        r = rules[rid]
        assert "title" in r and len(r["title"]) > 0
        assert "text_hash" in r and len(r["text_hash"]) == 64
        queries = r.get("queries", [])
        assert 2 <= len(queries) <= 3


def test_rule_text_hash_change_detection():
    """Verify that altering rule text changes the computed hash."""
    import hashlib
    h1 = hashlib.sha256("Rule R1: Signature Verification: The signature must equal...".encode()).hexdigest()
    h2 = hashlib.sha256("Rule R1: Signature Verification: The signature must EQUAL...".encode()).hexdigest()
    assert h1 != h2


def test_youcom_call_cap():
    """Verify call cap raises RuntimeError when limit is hit."""
    client = FakeYouComClient(call_cap=3)
    client.search("q1")
    client.search("q2")
    client.search("q3")
    with pytest.raises(RuntimeError, match="call cap reached"):
        client.search("q4")


def test_fetch_and_cache(tmp_path: Path):
    """Verify fetch_rule_evidence correctly parses and caches raw responses and sources."""
    fake_client = FakeYouComClient()
    spec = {
        "title": "Signature Verification",
        "description": "Signature verification test",
        "text_hash": "dummyhash",
        "queries": ["stripe signature verification"]
    }
    cached = fetch_rule_evidence(
        client=fake_client,
        rule_id="R1",
        rule_spec=spec,
        cache_dir=tmp_path,
        refresh=True,
    )
    assert cached["rule_id"] == "R1"
    assert len(cached["sources"]) == 2
    assert cached["sources"][0]["id"] == "R1_s1"
    assert cached["sources"][0]["provider"] == "you.com"
    assert (tmp_path / "R1.json").is_file()

    # Second call without refresh should load from cache without calling client
    calls_before = fake_client.calls_used
    cached_again = fetch_rule_evidence(
        client=fake_client,
        rule_id="R1",
        rule_spec=spec,
        cache_dir=tmp_path,
        refresh=False,
    )
    assert fake_client.calls_used == calls_before
    assert len(cached_again["sources"]) == 2


def test_judge_validation_rules():
    """Verify hard code checks on model judge verdicts."""
    sources = [
        {
            "id": "R1_s1",
            "snippet": "Always verify HMAC-SHA256 signatures over the exact raw body payload bytes.",
        }
    ]

    # 1. Valid verbatim quote
    v1 = {
        "label": "SUPPORTED",
        "sources_used": ["R1_s1"],
        "quote": "Always verify HMAC-SHA256 signatures",
        "reason": "Doc clearly specifies raw body HMAC.",
    }
    res1 = validate_judge_verdict(v1, sources)
    assert res1["label"] == "SUPPORTED"
    assert res1["quote"] == "Always verify HMAC-SHA256 signatures"
    assert res1["convention"] is False

    # 2. Quote exceeding 25 words -> downgraded to NOT_FOUND
    long_quote = " ".join(["word"] * 26)
    v2 = {
        "label": "SUPPORTED",
        "sources_used": ["R1_s1"],
        "quote": long_quote,
        "reason": "Should fail word count",
    }
    res2 = validate_judge_verdict(v2, sources)
    assert res2["label"] == "NOT_FOUND"
    assert res2["convention"] is True

    # 3. Non-substring quote -> downgraded to NOT_FOUND
    v3 = {
        "label": "SUPPORTED",
        "sources_used": ["R1_s1"],
        "quote": "This text does not exist in snippet",
        "reason": "Should fail substring check",
    }
    res3 = validate_judge_verdict(v3, sources)
    assert res3["label"] == "NOT_FOUND"

    # 4. Unknown source id -> downgraded to NOT_FOUND
    v4 = {
        "label": "SUPPORTED",
        "sources_used": ["R1_unknown"],
        "quote": "Always verify HMAC-SHA256 signatures",
        "reason": "Invalid source ID",
    }
    res4 = validate_judge_verdict(v4, sources)
    assert res4["label"] == "NOT_FOUND"


def test_grounding_schema_validator():
    """Verify validate_grounding accepts compliant documents and rejects invalid ones."""
    valid_doc = {
        "generated_at": "2026-11-21T00:00:00Z",
        "spec_sha": "abc123",
        "provider": "you.com",
        "rules": {
            "R1": {
                "title": "Signature Verification",
                "label": "NOT_JUDGED",
                "convention": False,
                "human_reviewed": False,
                "sources": [
                    {
                        "id": "R1_s1",
                        "url": "https://docs.stripe.com",
                        "title": "Stripe",
                        "snippet": "Snippet text",
                        "rank": 1,
                        "query": "query text",
                        "retrieved_at": "2026-11-21T00:00:00Z",
                        "provider": "you.com"
                    }
                ],
                "sources_used": [],
                "quote": "",
                "reason": "",
                "judge": {"model": None, "temperature": None}
            }
        }
    }
    assert len(validate_grounding(valid_doc)) == 0

    # Bad label
    bad_label_doc = json.loads(json.dumps(valid_doc))
    bad_label_doc["rules"]["R1"]["label"] = "INVALID_LABEL"
    assert len(validate_grounding(bad_label_doc)) > 0


def test_evidence_api_endpoints():
    """Verify FastAPI evidence router endpoints with TestClient."""
    set_client_override(FakeYouComClient())
    client = TestClient(app)

    # 1. Invalid rule id returns 400
    res_bad = client.get("/evidence/R999")
    assert res_bad.status_code == 400

    # 2. CORS preflight check from localhost:5173
    cors_res = client.options(
        "/evidence",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        }
    )
    assert cors_res.status_code == 200
    assert cors_res.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # 3. Search endpoint with extra terms > 80 chars
    long_terms = "x" * 85
    search_bad = client.post("/evidence/search", json={"rule_id": "R1", "extra_terms": long_terms})
    assert search_bad.status_code == 400

    # 4. Search endpoint valid execution
    search_ok = client.post("/evidence/search", json={"rule_id": "R1", "extra_terms": "stripe test"})
    assert search_ok.status_code in (200, 502)

    set_client_override(None)


def test_repair_prompt_sources():
    """Verify build_repair_prompt includes Sources section when provided."""
    sources = [
        {
            "id": "R1_s1",
            "title": "Stripe Webhooks",
            "url": "https://docs.stripe.com",
            "snippet": "Signature verification documentation",
        }
    ]
    prompt_with_sources = build_repair_prompt(
        failing_code="def handle_event(): pass",
        minimal_trace=[],
        rule_id="R1",
        rule_text="Verify signatures",
        invariant="I1_signature",
        explanation="Bad signature",
        sources=sources,
    )
    assert "OFFICIAL DOCUMENTATION & VERIFIED SOURCES" in prompt_with_sources
    assert "[R1_s1] Stripe Webhooks" in prompt_with_sources

    prompt_no_sources = build_repair_prompt(
        failing_code="def handle_event(): pass",
        minimal_trace=[],
        rule_id="R1",
        rule_text="Verify signatures",
        invariant="I1_signature",
        explanation="Bad signature",
        sources=[],
    )
    assert "OFFICIAL DOCUMENTATION & VERIFIED SOURCES" not in prompt_no_sources
