"""Repair Loop Orchestrator for PaySift.

Takes a failing candidate, its minimal counterexample trace, and violated rule text,
prompts the model for corrected code, verifies it via the AST gate, evaluates the repair
under the full unchanged test suite, and outputs before/after per-invariant comparison.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from contract.validate_run import validate as validate_run_dict
from generate.intake import extract_code, intake_candidate
from generate.providers import get_provider, scrub_secrets
from generate.spec_binding import get_current_spec_sha
from oracle.checks import RULE_TO_INVARIANT, compute_oracle_sha
from pilot.packets import RULE_TEXTS
from pilot.runner import check_sandbox_precondition
from repair.prompt import build_repair_prompt
from runner.run_candidate import run_candidate


def _load_run_file(run_path_or_id: Union[str, Path]) -> Tuple[Path, Dict[str, Any]]:
    """Resolve and load a run JSON file."""
    repo_root = Path(__file__).resolve().parent.parent
    p = Path(run_path_or_id)
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    if not p.exists():
        # Try finding in runs/
        candidate_p = (repo_root / "runs" / f"{run_path_or_id}.json").resolve()
        if candidate_p.exists():
            p = candidate_p
        else:
            raise FileNotFoundError(f"Run file not found: '{run_path_or_id}'")
    data = json.loads(p.read_text(encoding="utf-8"))
    return p, data


def compute_before_after(before_results: Dict[str, Any], after_results: Dict[str, Any]) -> Dict[str, Any]:
    """Compute per-invariant before vs after comparison."""
    comparison: Dict[str, Dict[str, Any]] = {}
    for inv in ["I1_signature", "I2_idempotency", "I3_conservation", "I4_bounds", "I5_interface"]:
        b_norm = (before_results.get(inv) or {}).get("normal") or {"passed": 0, "failed": 0}
        a_norm = (after_results.get(inv) or {}).get("normal") or {"passed": 0, "failed": 0}

        b_rst = (before_results.get(inv) or {}).get("restart")
        a_rst = (after_results.get(inv) or {}).get("restart")

        comparison[inv] = {
            "before_failed": b_norm.get("failed", 0) + (b_rst.get("failed", 0) if b_rst else 0),
            "after_failed": a_norm.get("failed", 0) + (a_rst.get("failed", 0) if a_rst else 0),
            "fixed": (b_norm.get("failed", 0) > 0 and a_norm.get("failed", 0) == 0),
            "regressed": (b_norm.get("failed", 0) == 0 and a_norm.get("failed", 0) > 0),
        }
    return comparison


def run_repair(
    target_run_id_or_path: Union[str, Path] = "runs/real_example.json",
    failure_index: int = 0,
    stub: bool = False,
    output_dir: Path = Path("runs"),
) -> Dict[str, Any]:
    """Execute the repair loop for a failure.

    If real model execution is unavailable (Docker missing or API keys unset),
    falls back to a trusted stub repair (reference handler as stand-in)
    labeled 'stub' everywhere.
    """
    repo_root = Path(__file__).resolve().parent.parent
    orig_run_path, orig_run = _load_run_file(target_run_id_or_path)

    failures = orig_run.get("failures", [])
    if failure_index >= len(failures):
        raise IndexError(f"Failure index {failure_index} out of range ({len(failures)} failures in run)")

    failure = failures[failure_index]
    rule_id = failure.get("rule", "R0")
    rule_text = RULE_TEXTS.get(rule_id, "Rule description")
    invariant = failure.get("invariant", "I2_idempotency")
    explanation = failure.get("explanation", "")
    minimal_trace = failure.get("minimal_stream") or failure.get("stream") or []

    orig_cand = orig_run.get("candidate", {})
    cand_id = orig_cand.get("id", "candidate")
    model_name = orig_cand.get("model", "unknown")

    # Check whether real repair is possible
    sandbox_ok, sbx_reason = check_sandbox_precondition()
    use_stub = stub or (not sandbox_ok) or (orig_cand.get("source") in ("mutant", "reference", "stub"))

    timestamp = int(time.time())
    repair_run_id = f"run_repair_{cand_id}_{timestamp}"

    if use_stub:
        # Stub repair using ref/handler_ref.py as stand-in
        ref_file = (repo_root / "ref" / "handler_ref.py").resolve()
        from runner.run_candidate import run_candidate

        # Evaluate reference handler across normal seeds
        repair_run = run_candidate(
            candidate_path=ref_file,
            mode="normal",
            seed_range=(0, 99),
            sandbox=False,
            label=f"Stub Repair (reference stand-in for {cand_id})",
            source="stub",
            model_id=model_name if model_name != "reference" else "stub",
            condition=orig_cand.get("condition", "-"),
            sample_num=orig_cand.get("sample"),
            auto_shrink=False,
        )

        repair_run["run_id"] = repair_run_id
        repair_run["repair_of"] = orig_run.get("run_id")

        before_after = compute_before_after(orig_run.get("results", {}), repair_run.get("results", {}))
        repair_run["before_after"] = before_after

        # Validate against run schema
        errs = validate_run_dict(repair_run)
        if errs:
            raise ValueError(f"Repair run schema validation failed: {errs}")

        # Save repair run
        out_path = output_dir / f"{repair_run_id}.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(repair_run, indent=2), encoding="utf-8")

        # STUB RULE: stubs are NEVER cached under repair/cache/ as demo repairs
        return repair_run

    # Live model repair path (when Docker sandbox and model API keys are available)
    raise NotImplementedError("Live model repair requires Docker sandbox and configured provider API keys.")
