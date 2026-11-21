"""Unit tests for PaySift FastAPI backend (api/main.py)."""

from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from api.main import app

client = TestClient(app)


def test_api_health():
    """GET /health must return ok status, hashes, hosted_mode and sandbox flags."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["spec_sha"]) == 64
    assert len(data["oracle_sha"]) == 64
    assert "hosted_mode" in data
    assert isinstance(data["hosted_mode"], bool)
    assert "sandbox" in data
    assert isinstance(data["sandbox"], bool)


def test_api_list_runs():
    """GET /runs must return a list of run summary objects."""
    resp = client.get("/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert isinstance(runs, list)
    assert len(runs) > 0
    first = runs[0]
    assert "run_id" in first
    assert "candidate" in first
    assert "failures_count" in first


def test_api_get_run_existing():
    """GET /runs/{id} returns full run JSON for existing run."""
    resp = client.get("/runs/real_example")
    assert resp.status_code == 200
    data = resp.json()
    assert data["candidate"]["label"] == "hand-written mutant, not model output"
    assert len(data["failures"]) > 0


def test_api_get_run_not_found():
    """GET /runs/{id} returns 404 for nonexistent run."""
    resp = client.get("/runs/nonexistent_run_9999999")
    assert resp.status_code == 404


def test_api_get_run_path_traversal():
    """GET /runs/{id} rejects path traversal attempts."""
    resp = client.get("/runs/..%2F..%2Fsecret")
    assert resp.status_code in (400, 404)


def test_api_get_kill_matrix():
    """GET /kill-matrix returns the kill matrix JSON."""
    resp = client.get("/kill-matrix")
    assert resp.status_code == 200
    data = resp.json()
    assert "rows" in data or "matrix" in data or "runs" in data


def test_api_post_break_valid():
    """POST /break with reference and duplicate_capture returns pass."""
    payload = {
        "candidate_id": "reference",
        "scenario": "duplicate_capture",
    }
    resp = client.post("/break", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "pass"
    assert data["ledger_diff"]["balance_diff_paise"] == 0


def test_api_post_break_mutant():
    """POST /break with m1_no_dedupe and duplicate_capture returns fail with diff."""
    payload = {
        "candidate_id": "m1_no_dedupe",
        "scenario": "duplicate_capture",
    }
    resp = client.post("/break", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["verdict"] == "fail"
    assert data["ledger_diff"]["balance_diff_paise"] > 0
    assert "Rs 500.00 created from nothing" in data["ledger_diff"]["diff_summary"]


def test_api_post_break_invalid_scenario():
    """POST /break with invalid scenario returns 400."""
    payload = {
        "candidate_id": "reference",
        "scenario": "nonexistent_scenario",
    }
    resp = client.post("/break", json=payload)
    assert resp.status_code == 400


def test_api_post_repair_missing_key(monkeypatch):
    """POST /repair returns 400 when missing model key in local mode without cached repair."""
    monkeypatch.setenv("HOSTED_MODE", "0")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    payload = {
        "candidate_id": "m1_no_dedupe",
        "failure_id": 9999,
    }
    resp = client.post("/repair", json=payload)
    assert resp.status_code == 400
    data = resp.json()
    assert data.get("error") == "missing_api_key"
    assert "GEMINI_API_KEY" in data.get("message", "")


def test_api_runs_field_contract():
    """Verify GET /runs entries expose all required fields for frontend integration."""
    resp = client.get("/runs")
    assert resp.status_code == 200
    runs = resp.json()
    assert len(runs) > 0
    item = runs[0]
    required_fields = [
        "id",
        "created_at",
        "spec_sha",
        "candidate_id",
        "candidate_source",
        "candidate_model",
        "candidate_condition",
        "failure_count",
        "financial_failure_count",
        "interface_failure_count",
    ]
    for rf in required_fields:
        assert rf in item, f"Missing field '{rf}' in /runs response"


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_api_cors_preflight(origin: str):
    """Verify CORS preflight OPTIONS request returns 200 with allowed headers."""
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    }
    resp = client.options("/break", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin


def test_hosted_mode_post_break(monkeypatch):
    """HOSTED_MODE=1: POST /break returns 403 disabled_in_hosted_mode."""
    monkeypatch.setenv("HOSTED_MODE", "1")
    payload = {
        "candidate_id": "reference",
        "scenario": "duplicate_capture",
    }
    resp = client.post("/break", json=payload)
    assert resp.status_code == 403
    data = resp.json()
    assert data.get("error") == "disabled_in_hosted_mode"
    assert "Needs Docker and your own model key" in data.get("message", "")


def test_hosted_mode_post_repair_uncached(monkeypatch):
    """HOSTED_MODE=1: POST /repair without cached result returns 403 disabled_in_hosted_mode."""
    monkeypatch.setenv("HOSTED_MODE", "1")
    payload = {
        "candidate_id": "m1_no_dedupe",
        "failure_id": 9999,
    }
    resp = client.post("/repair", json=payload)
    assert resp.status_code == 403
    data = resp.json()
    assert data.get("error") == "disabled_in_hosted_mode"
    assert "Needs Docker and your own model key" in data.get("message", "")


def test_hosted_mode_post_repair_cached(monkeypatch, tmp_path):
    """HOSTED_MODE=1: POST /repair with cached result returns 200."""
    monkeypatch.setenv("HOSTED_MODE", "1")
    fake_cache_dir = tmp_path / "repair" / "cache"
    fake_cache_dir.mkdir(parents=True)
    fake_file = fake_cache_dir / "test_cand__0.json"
    fake_data = {"status": "ok", "patched_code": "def solve(): pass"}
    fake_file.write_text(json.dumps(fake_data), encoding="utf-8")

    import api.main
    monkeypatch.setattr(api.main, "REPO_ROOT", tmp_path)

    resp = client.post("/repair", json={"candidate_id": "test_cand", "failure_id": 0})
    assert resp.status_code == 200
    res_data = resp.json()
    assert res_data.get("cached") is True
    assert res_data.get("source") == "pre-run"
    assert res_data.get("data") == fake_data


def test_hosted_mode_read_endpoints(monkeypatch):
    """HOSTED_MODE=1: GET /health, GET /runs, GET /kill-matrix, GET /evidence/rules work normally."""
    monkeypatch.setenv("HOSTED_MODE", "1")
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["hosted_mode"] is True

    runs_resp = client.get("/runs")
    assert runs_resp.status_code == 200
    assert isinstance(runs_resp.json(), list)

    km_resp = client.get("/kill-matrix")
    assert km_resp.status_code == 200

    evidence_resp = client.get("/evidence")
    assert evidence_resp.status_code == 200
    assert "rules" in evidence_resp.json()

    r1_resp = client.get("/evidence/R1")
    assert r1_resp.status_code == 200


def test_api_cors_private_network():
    """OPTIONS preflight from hosted UI with private network returns 200 and private network header."""
    origin = "https://pay-sift.vercel.app"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
        "Access-Control-Request-Private-Network": "true",
    }
    resp = client.options("/break", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == origin
    assert resp.headers.get("access-control-allow-private-network") == "true"


def test_evidence_search_rate_limits(monkeypatch):
    """SEARCH_MAX_TOTAL and SEARCH_MAX_PER_IP_PER_HOUR return 429 when limits are hit."""
    from api.evidence import reset_search_limits, set_client_override
    from tests.test_grounding import FakeYouComClient

    reset_search_limits()
    fake_client = FakeYouComClient()
    set_client_override(fake_client)

    try:
        # Test total limit in hosted mode
        monkeypatch.setenv("HOSTED_MODE", "1")
        monkeypatch.setenv("SEARCH_MAX_TOTAL", "2")
        monkeypatch.setenv("SEARCH_MAX_PER_IP_PER_HOUR", "10")

        # First call succeeds
        r1 = client.post("/evidence/search", json={"rule_id": "R1"})
        assert r1.status_code == 200

        # Second call succeeds
        r2 = client.post("/evidence/search", json={"rule_id": "R1"})
        assert r2.status_code == 200

        # Third call hits SEARCH_MAX_TOTAL
        r3 = client.post("/evidence/search", json={"rule_id": "R1"})
        assert r3.status_code == 429
        data3 = r3.json()
        assert data3.get("error") == "rate_limited"
        assert "Hosted search limit reached" in data3.get("message", "")

        # Test per-IP limit
        reset_search_limits()
        monkeypatch.setenv("HOSTED_MODE", "0")
        monkeypatch.delenv("SEARCH_MAX_TOTAL", raising=False)
        monkeypatch.setenv("SEARCH_MAX_PER_IP_PER_HOUR", "1")

        # First call from IP 10.0.0.1
        r_ip1 = client.post(
            "/evidence/search",
            json={"rule_id": "R1"},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert r_ip1.status_code == 200

        # Second call from IP 10.0.0.1 hits rate limit
        r_ip2 = client.post(
            "/evidence/search",
            json={"rule_id": "R1"},
            headers={"X-Forwarded-For": "10.0.0.1"},
        )
        assert r_ip2.status_code == 429
        data_ip2 = r_ip2.json()
        assert data_ip2.get("error") == "rate_limited"
        assert "queries per IP per hour" in data_ip2.get("message", "")

        # Different IP 10.0.0.2 is not blocked
        r_ip3 = client.post(
            "/evidence/search",
            json={"rule_id": "R1"},
            headers={"X-Forwarded-For": "10.0.0.2"},
        )
        assert r_ip3.status_code == 200

    finally:
        set_client_override(None)
        reset_search_limits()


