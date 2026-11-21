"""PaySift Thin REST API (FastAPI).

Provides endpoints for UI integration, live scenario testing (/break),
and repair loop triggering (/repair).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from generate.spec_binding import get_current_spec_sha
from oracle.checks import compute_oracle_sha

app = FastAPI(
    title="PaySift API",
    description="Thin backend API serving runs, kill-matrix, scenario testing, and repair workflows.",
    version="1.0.0",
)


def is_hosted_mode() -> bool:
    """Return True if running in read-only hosted mode (e.g. on Render)."""
    val = os.environ.get("HOSTED_MODE", "").strip().lower()
    return val in ("1", "true", "yes", "on")


def get_allowed_origins() -> List[str]:
    """Retrieve allowed CORS origins from env or sensible defaults."""
    env_origins = os.environ.get("CORS_ORIGINS", "").strip()
    if env_origins:
        return [o.strip() for o in env_origins.split(",") if o.strip()]
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://pay-sift.vercel.app",
    ]


# Configure CORS with private-network preflight support
origins = get_allowed_origins()
allow_credentials = False if "*" in origins else True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_private_network=True,
)

from api.evidence import router as evidence_router
app.include_router(evidence_router)

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")
REPO_ROOT = Path(__file__).resolve().parent.parent

# Automatically load local .env if present without external dependencies
_local_env = REPO_ROOT / ".env"
if _local_env.is_file():
    try:
        for _line in _local_env.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                _k, _v = _k.strip(), _v.strip()
                if _k and _k not in os.environ:
                    os.environ[_k] = _v
    except Exception:
        pass

# Cache for sandbox availability check (30 seconds)
_sandbox_cache: Optional[bool] = None
_sandbox_cache_time: float = 0.0


def check_sandbox_available() -> bool:
    """Check if Docker is reachable and paysift-sandbox:1 exists.
    
    Result is cached for 30 seconds and never raises an exception.
    """
    global _sandbox_cache, _sandbox_cache_time
    now = time.time()
    if _sandbox_cache is not None and (now - _sandbox_cache_time) < 30.0:
        return _sandbox_cache
    avail = False
    try:
        from runner.sandbox import is_docker_available, is_docker_image_available
        avail = bool(
            is_docker_available(force_refresh=True)
            and is_docker_image_available("paysift-sandbox:1", force_refresh=True)
        )
    except Exception:
        avail = False
    _sandbox_cache = avail
    _sandbox_cache_time = now
    return avail


class BreakRequest(BaseModel):
    candidate_id: str = Field(..., description="Candidate identifier or alias")
    scenario: str = Field(..., description="Scenario name from fixed suite")


class RepairRequest(BaseModel):
    candidate_id: str = Field(..., description="Candidate identifier to repair")
    failure_id: int = Field(0, description="Index of failure to address")


@app.get("/health")
def health() -> Dict[str, Any]:
    """Healthcheck endpoint returning system status, contract hashes, and capabilities."""
    return {
        "status": "ok",
        "spec_sha": get_current_spec_sha(),
        "oracle_sha": compute_oracle_sha(),
        "hosted_mode": is_hosted_mode(),
        "sandbox": check_sandbox_available(),
    }


@app.get("/runs")
def list_runs() -> List[Dict[str, Any]]:
    """List summary metadata for all completed runs in runs/*.json."""
    runs_dir = REPO_ROOT / "runs"
    runs_list: List[Dict[str, Any]] = []
    if not runs_dir.exists():
        return runs_list

    for rf in sorted(runs_dir.glob("*.json")):
        if rf.name in ("scenario_verdicts.json", "kill_matrix.json", "kill_matrix.sample.json", "grounding.json"):
            continue
        try:
            data = json.loads(rf.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "run_id" not in data:
                continue
            failures = data.get("failures", [])
            cand = data.get("candidate", {})
            financial_count = sum(
                1 for f in failures if f.get("invariant") in ("I1_signature", "I2_idempotency", "I3_conservation", "I4_bounds")
            )
            interface_count = sum(
                1 for f in failures if f.get("invariant") == "I5_interface"
            )

            runs_list.append({
                "id": data.get("run_id"),
                "run_id": data.get("run_id"),
                "created_at": data.get("created_at"),
                "candidate": cand,
                "candidate_id": cand.get("id"),
                "candidate_source": cand.get("source"),
                "candidate_model": cand.get("model"),
                "candidate_condition": cand.get("condition"),
                "failures_count": len(failures),
                "failure_count": len(failures),
                "financial_failures_count": financial_count,
                "financial_failure_count": financial_count,
                "interface_failures_count": interface_count,
                "interface_failure_count": interface_count,
                "repair_of": data.get("repair_of"),
                "spec_sha": data.get("spec_sha"),
                "oracle_sha": data.get("oracle_sha"),
                "path": f"runs/{rf.name}",
            })
        except Exception:
            continue

    return runs_list


@app.get("/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    """Retrieve full Run JSON document by run_id."""
    if not ID_PATTERN.match(run_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid run_id format (must be alphanumeric, hyphens, or underscores).",
        )

    runs_dir = REPO_ROOT / "runs"
    run_file = runs_dir / f"{run_id}.json"
    if not run_file.exists():
        run_file = runs_dir / run_id
    if not run_file.exists() or not run_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found.",
        )

    try:
        return json.loads(run_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading run JSON: {exc}",
        )


@app.get("/kill-matrix")
def get_kill_matrix() -> Dict[str, Any]:
    """Retrieve the kill matrix data."""
    km_file = REPO_ROOT / "runs" / "kill_matrix.json"
    if not km_file.exists():
        sample_file = REPO_ROOT / "runs" / "kill_matrix.sample.json"
        if sample_file.exists():
            return json.loads(sample_file.read_text(encoding="utf-8"))
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kill matrix data has not been generated yet.",
        )
    return json.loads(km_file.read_text(encoding="utf-8"))


@app.post("/break")
def break_candidate(req: BreakRequest) -> Any:
    """Run a fixed scenario against a candidate and return verdict & ledger diff."""
    if is_hosted_mode():
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "disabled_in_hosted_mode",
                "message": "Needs Docker and your own model key. Clone the repo and run it locally.",
            },
        )

    cand_id = req.candidate_id.strip()
    scenario_name = req.scenario.strip()

    if not ID_PATTERN.match(cand_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid candidate_id format (path traversal characters forbidden).",
        )

    from scenarios.scenarios import SCENARIOS, resolve_candidate_path, run_scenario
    if scenario_name not in SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown scenario '{scenario_name}'. Available: {sorted(SCENARIOS.keys())}",
        )

    try:
        cand_path, cid, is_trusted = resolve_candidate_path(cand_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Candidate not found: {exc}",
        )

    if not is_trusted:
        from pilot.runner import check_sandbox_precondition
        ok, reason = check_sandbox_precondition()
        if not ok:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Untrusted candidate '{cid}' cannot execute natively and Docker sandbox is unavailable: {reason}",
            )

    try:
        res = run_scenario(cand_id, scenario_name)
        return res
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@app.post("/repair")
def repair_candidate(req: RepairRequest) -> Any:
    """Trigger repair loop or retrieve cached pre-run repair."""
    cand_id = req.candidate_id.strip()
    failure_id = req.failure_id

    if not ID_PATTERN.match(cand_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid candidate_id format (path traversal characters forbidden).",
        )

    # Check cached pre-run repair first
    cache_dir = REPO_ROOT / "repair" / "cache"
    cached_repair_file = cache_dir / f"{cand_id}__{failure_id}.json"
    if cached_repair_file.exists():
        try:
            return {
                "source": "pre-run",
                "cached": True,
                "data": json.loads(cached_repair_file.read_text(encoding="utf-8")),
            }
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to read cached repair: {exc}",
            )

    # When not cached: in hosted mode, live repair is disabled
    if is_hosted_mode():
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "disabled_in_hosted_mode",
                "message": "Needs Docker and your own model key. Clone the repo and run it locally.",
            },
        )

    # Local mode: check model API key requirement
    needed_key_env = "GEMINI_API_KEY"
    models_yaml_path = REPO_ROOT / "config" / "models.yaml"
    if models_yaml_path.exists():
        try:
            import yaml
            mdata = yaml.safe_load(models_yaml_path.read_text(encoding="utf-8")) or {}
            for m in mdata.get("models", []):
                if m.get("name") in cand_id or m.get("model_id") in cand_id:
                    needed_key_env = m.get("api_key_env", "GEMINI_API_KEY")
                    break
        except Exception:
            pass

    if not os.environ.get(needed_key_env, "").strip():
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "missing_api_key",
                "message": f"Missing required environment variable: {needed_key_env}. Add it to your .env file.",
            },
        )

    # Check sandbox precondition
    from pilot.runner import check_sandbox_precondition
    sandbox_ok, reason = check_sandbox_precondition()
    if not sandbox_ok:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "error": "sandbox_unavailable",
                "message": f"Docker sandbox unavailable: {reason}",
            },
        )

    # Attempt live repair
    try:
        from repair.repair import run_repair
        res = run_repair(cand_id, failure_index=failure_id)
        return res
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Repair execution failed: {exc}",
        )
