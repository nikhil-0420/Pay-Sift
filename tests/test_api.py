"""Unit tests for PaySift FastAPI backend (api/main.py)."""

from __future__ import annotations

import json
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from api.main import app

client = TestClient(app)


def test_api_health():
    """GET /health must return ok status and non-empty hashes."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["spec_sha"]) == 64
    assert len(data["oracle_sha"]) == 64


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


def test_api_post_repair_blocked():
    """POST /repair returns 403 or 503 when uncached and live repair is blocked."""
    payload = {
        "candidate_id": "m1_no_dedupe",
        "failure_id": 0,
    }
    resp = client.post("/repair", json=payload)
    assert resp.status_code in (403, 503)
    data = resp.json()
    assert "detail" in data


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

