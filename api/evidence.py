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

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from grounding.fetch import fetch_rule_evidence, load_queries
from grounding.judge import rebuild_grounding_json
from grounding.youcom import YouComClient

router = APIRouter(tags=["evidence"])

RULE_ID_PATTERN = re.compile(r"^R(10|[0-9])$")
REPO_ROOT = Path(__file__).resolve().parent.parent

# In-memory search limits
_total_search_count = 0
_ip_search_timestamps: Dict[str, deque] = {}

# Configurable client hook for testing with fake clients
_client_override: Optional[Any] = None
_cache_dir_override: Optional[Path] = None
_output_file_override: Optional[Path] = None


def is_hosted_mode() -> bool:
    """Check whether HOSTED_MODE is enabled."""
    return os.environ.get("HOSTED_MODE", "").strip().lower() in ("1", "true", "yes", "on")


def get_search_max_total() -> int:
    """Return process-wide total search budget from SEARCH_MAX_TOTAL env var."""
    try:
        return int(os.environ.get("SEARCH_MAX_TOTAL", "25"))
    except ValueError:
        return 25


def get_search_max_per_ip_per_hour() -> int:
    """Return per-IP 1-hour search budget from SEARCH_MAX_PER_IP_PER_HOUR env var."""
    try:
        return int(os.environ.get("SEARCH_MAX_PER_IP_PER_HOUR", "10"))
    except ValueError:
        return 10


def reset_search_limits() -> None:
    """Reset in-memory search limit counters (useful for unit tests)."""
    global _total_search_count, _ip_search_timestamps
    _total_search_count = 0
    _ip_search_timestamps.clear()


def check_search_limits(client_ip: str) -> Optional[JSONResponse]:
    """Enforce SEARCH_MAX_TOTAL and SEARCH_MAX_PER_IP_PER_HOUR in-memory limits."""
    global _total_search_count
    hosted = is_hosted_mode()

    # Enforce total limit in hosted mode or if explicitly configured via SEARCH_MAX_TOTAL
    if hosted or "SEARCH_MAX_TOTAL" in os.environ:
        max_total = get_search_max_total()
        if _total_search_count >= max_total:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "rate_limited",
                    "message": f"Hosted search limit reached ({max_total} total per deployment). Run locally with your own YDC_API_KEY to search without limits.",
                },
            )

    max_per_ip = get_search_max_per_ip_per_hour()
    now = time.time()
    if client_ip not in _ip_search_timestamps:
        _ip_search_timestamps[client_ip] = deque()

    dq = _ip_search_timestamps[client_ip]
    while dq and (now - dq[0]) > 3600.0:
        dq.popleft()

    if len(dq) >= max_per_ip:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "rate_limited",
                "message": f"Search rate limit exceeded ({max_per_ip} queries per IP per hour). Run locally with your own YDC_API_KEY to search without limits.",
            },
        )
    return None


def record_search_success(client_ip: str) -> None:
    """Record a completed search against rate limits."""
    global _total_search_count
    _total_search_count += 1
    if client_ip not in _ip_search_timestamps:
        _ip_search_timestamps[client_ip] = deque()
    _ip_search_timestamps[client_ip].append(time.time())


def get_youcom_client() -> YouComClient:
    """Return the configured YouComClient or test override."""
    if _client_override is not None:
        return _client_override
    return YouComClient()


def set_client_override(client: Optional[Any]) -> None:
    """Set or clear a test client override."""
    global _client_override
    _client_override = client


def get_cache_dir() -> Path:
    """Return the active cache directory or test override."""
    if _cache_dir_override is not None:
        return _cache_dir_override
    return REPO_ROOT / "grounding" / "cache"


def set_cache_dir_override(cache_dir: Optional[Path]) -> None:
    """Set or clear a test cache dir override."""
    global _cache_dir_override
    _cache_dir_override = cache_dir


def get_output_file() -> Path:
    """Return the output file for runs/grounding.json or test override."""
    if _output_file_override is not None:
        return _output_file_override
    return REPO_ROOT / "runs" / "grounding.json"


def set_output_file_override(output_file: Optional[Path]) -> None:
    """Set or clear a test output file override."""
    global _output_file_override
    _output_file_override = output_file


class EvidenceSearchRequest(BaseModel):
    rule_id: str = Field(..., description="Specification rule ID (e.g. R1, R10)")
    extra_terms: Optional[str] = Field(None, description="Optional extra search terms (max 80 chars)")


@router.get("/evidence")
def get_all_evidence() -> Dict[str, Any]:
    """Retrieve full runs/grounding.json artifact."""
    grounding_file = get_output_file()
    if not grounding_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="runs/grounding.json artifact not found on server.",
        )
    try:
        return json.loads(grounding_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to read runs/grounding.json: {exc}",
        )


@router.get("/evidence/{rule_id}")
def get_rule_evidence(rule_id: str) -> Dict[str, Any]:
    """Retrieve evidence citations and judge status for a specific rule."""
    rule_id = rule_id.strip().upper()
    if not RULE_ID_PATTERN.match(rule_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid rule_id '{rule_id}'. Must match ^R(10|[0-9])$",
        )

    grounding_file = get_output_file()
    if not grounding_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="runs/grounding.json artifact not found on server.",
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
def search_evidence(req: EvidenceSearchRequest, request: Request) -> Dict[str, Any]:
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
        extra_terms = re.sub(r"[\r\n\t]+", " ", extra_terms)

    # Determine client IP for per-IP rate limiting
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    # Enforce SEARCH_MAX_TOTAL and SEARCH_MAX_PER_IP_PER_HOUR
    rate_limit_err = check_search_limits(client_ip)
    if rate_limit_err is not None:
        return rate_limit_err

    # Verify YDC_API_KEY if no test client override
    if _client_override is None and not os.environ.get("YDC_API_KEY", "").strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="YDC_API_KEY is not configured on the server.",
        )

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
        base_queries = rule_spec.get("queries", [])
        rule_spec["queries"] = [f"{base_queries[0]} {extra_terms}"] + base_queries[1:]

    cache_dir = get_cache_dir()
    try:
        cache_data = fetch_rule_evidence(
            client=client,
            rule_id=rule_id,
            rule_spec=rule_spec,
            cache_dir=cache_dir,
            refresh=True,
        )
        record_search_success(client_ip)
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
            output_file=get_output_file(),
        )
    except Exception:
        pass

    return {
        "status": "ok",
        "rule_id": rule_id,
        "sources_retrieved": len(cache_data.get("sources", [])),
        "data": cache_data,
    }
