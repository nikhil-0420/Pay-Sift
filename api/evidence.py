"""API router for PaySift You.com evidence endpoints."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from grounding.fetch import fetch_rule_evidence, load_queries
from grounding.judge import rebuild_grounding_json
from grounding.youcom import YouComClient

router = APIRouter(tags=["evidence"])

RULE_ID_PATTERN = re.compile(r"^R(10|[0-9])$")
REPO_ROOT = Path(__file__).resolve().parent.parent

# In-memory sliding window rate limiter (10 calls per 60 seconds)
RATE_LIMIT_CALLS = 10
RATE_LIMIT_WINDOW_SECS = 60.0
_request_timestamps: deque = deque()

# Configurable client hook for testing with fake clients
_client_override: Optional[Any] = None


def get_youcom_client() -> YouComClient:
    """Return the configured YouComClient or test override."""
    if _client_override is not None:
        return _client_override
    return YouComClient()


def set_client_override(client: Optional[Any]) -> None:
    """Set or clear a test client override."""
    global _client_override
    _client_override = client


def check_rate_limit() -> None:
    """Enforce per-process 10 requests per minute limit."""
    now = time.time()
    while _request_timestamps and now - _request_timestamps[0] > RATE_LIMIT_WINDOW_SECS:
        _request_timestamps.popleft()

    if len(_request_timestamps) >= RATE_LIMIT_CALLS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: maximum {RATE_LIMIT_CALLS} search requests per minute.",
        )
    _request_timestamps.append(now)


class EvidenceSearchRequest(BaseModel):
    rule_id: str = Field(..., description="Specification rule ID (e.g. R1, R10)")
    extra_terms: Optional[str] = Field(None, description="Optional extra search terms (max 80 chars)")


@router.get("/evidence")
def get_all_evidence() -> Dict[str, Any]:
    """Retrieve full runs/grounding.json artifact."""
    grounding_file = REPO_ROOT / "runs" / "grounding.json"
    if not grounding_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="runs/grounding.json not found. Run 'python cli.py ground --fetch' first.",
        )
    try:
        return json.loads(grounding_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading grounding.json: {exc}",
        )


@router.get("/evidence/{rule_id}")
def get_rule_evidence(rule_id: str) -> Dict[str, Any]:
    """Retrieve evidence details for a specific rule."""
    if not RULE_ID_PATTERN.match(rule_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rule_id '{rule_id}'. Must match ^R(10|[0-9])$",
        )

    grounding_file = REPO_ROOT / "runs" / "grounding.json"
    if not grounding_file.is_file():
        # Fallback to cache file if grounding.json has not been rebuilt yet
        cache_file = REPO_ROOT / "grounding" / "cache" / f"{rule_id}.json"
        if cache_file.is_file():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No evidence found for rule '{rule_id}'.",
        )

    try:
        data = json.loads(grounding_file.read_text(encoding="utf-8"))
        rules = data.get("rules", {})
        if rule_id not in rules:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Rule '{rule_id}' not present in runs/grounding.json.",
            )
        return rules[rule_id]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading evidence: {exc}",
        )


@router.post("/evidence/search")
def search_evidence(req: EvidenceSearchRequest) -> Dict[str, Any]:
    """Trigger a live search for a rule with optional extra search terms."""
    rule_id = req.rule_id.strip()
    if not RULE_ID_PATTERN.match(rule_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rule_id '{rule_id}'. Must match ^R(10|[0-9])$",
        )

    extra_terms = req.extra_terms
    if extra_terms is not None:
        extra_terms = extra_terms.strip()
        if len(extra_terms) > 80:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="extra_terms exceeds maximum length of 80 characters.",
            )
        # Sanitize control characters
        extra_terms = re.sub(r"[\r\n\t]+", " ", extra_terms)

    # Check rate limit
    check_rate_limit()

    client = get_youcom_client()

    queries_path = REPO_ROOT / "grounding" / "queries.yaml"
    queries_data = load_queries(queries_path)
    all_rules = queries_data.get("rules", {})
    if rule_id not in all_rules:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rule '{rule_id}' is not defined in queries.yaml.",
        )

    rule_spec = dict(all_rules[rule_id])
    if extra_terms:
        # Augment queries with extra terms
        base_queries = rule_spec.get("queries", [])
        rule_spec["queries"] = [f"{base_queries[0]} {extra_terms}"] + base_queries[1:]

    cache_dir = REPO_ROOT / "grounding" / "cache"
    try:
        cache_data = fetch_rule_evidence(
            client=client,
            rule_id=rule_id,
            rule_spec=rule_spec,
            cache_dir=cache_dir,
            refresh=True,
        )
    except Exception as exc:
        err_msg = str(exc)
        if "API call cap reached" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"You.com API call cap reached: {err_msg}",
            )
        if "YDC_API_KEY is missing" in err_msg:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="YDC_API_KEY is not configured on the server.",
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"You.com search request failed: {err_msg}",
        )

    # Rebuild runs/grounding.json so GET /evidence is kept in sync
    try:
        rebuild_grounding_json(
            cache_dir=cache_dir,
            output_file=REPO_ROOT / "runs" / "grounding.json",
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "rule_id": rule_id,
        "sources_retrieved": len(cache_data.get("sources", [])),
        "data": cache_data,
    }
