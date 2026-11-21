"""Candidate test orchestrator running seeds 0-99 and generating Run JSON v1.1."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple

from contract.events import decode_step
from contract.spec_sha import compute_spec_sha
from contract.validate_run import validate
from oracle.checks import compute_oracle_sha, verify_step
from oracle.model import Model
from runner.streams import generate_stream
from runner.worker import execute_job, native_allowed


def execute(candidate_file: Path, job: Dict[str, Any], sandbox: bool = False) -> Dict[str, Any]:
    """Execute candidate job either natively or in Docker sandbox."""
    if sandbox:
        from runner.sandbox import run_in_sandbox
        sb_res = run_in_sandbox(candidate_file, job, mode=job.get("mode", "normal"))
        if not sb_res.get("ok"):
            raise RuntimeError(f"Sandbox execution failed: {sb_res.get('error')}")
        return sb_res["results"]
    return execute_job(job, is_sandbox=False)


def run_candidate(
    candidate_path: Path,
    mode: str = "normal",
    seed_range: Tuple[int, int] = (0, 99),
    sandbox: bool = False,
    label: str = "",
    source: str = "reference",
    model_id: str = "reference",
    condition: str = "-",
    sample_num: Optional[int] = None,
    amount_pass_enabled: bool = False,
    auto_shrink: bool = True,
) -> Dict[str, Any]:
    """Run candidate across seed range, evaluate with oracle, and produce Run JSON v1.1."""
    candidate_path = candidate_path.resolve()

    repo_root = Path(__file__).resolve().parent.parent
    spec_path = repo_root / "contract" / "SPEC.md"
    schema_path = repo_root / "contract" / "schema.sql"
    hash_file = repo_root / "contract" / "SPEC_HASH"

    if hash_file.is_file():
        spec_sha = hash_file.read_text(encoding="utf-8").strip()
    else:
        spec_sha = compute_spec_sha(spec_path, schema_path)

    # Refuse stale candidates whose spec_sha differs from current contract
    from generate.spec_binding import check_candidate_spec_binding
    is_compatible, stale_msg = check_candidate_spec_binding(candidate_path, spec_sha)
    if not is_compatible:
        raise ValueError(stale_msg)

    if not sandbox and not native_allowed(candidate_path):
        raise PermissionError(
            f"Native execution forbidden for untrusted code: {candidate_path}. "
            "Must execute inside Docker sandbox (Rule 3)."
        )

    oracle_sha = compute_oracle_sha()
    candidate_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()

    # 1. Build test streams
    secret = "paysift_secret_key_v1_offline_test"
    sequences: List[Dict[str, Any]] = []
    stream_map: Dict[int, List[Dict[str, str]]] = {}

    if mode == "restart":
        target_seeds = [s for s in range(100) if (s % 10) in {0, 6, 7, 9}][:20]
    else:
        target_seeds = list(range(seed_range[0], seed_range[1] + 1))

    for seed in target_seeds:
        steps = generate_stream(seed, secret=secret)
        stream_map[seed] = steps
        sequences.append({
            "seed": seed,
            "steps": steps,
        })

    job = {
        "candidate_file": str(candidate_path),
        "mode": mode,
        "secret": secret,
        "sequences": sequences,
    }

    # 2. Execute candidate
    t0 = time.monotonic()
    job_results = execute(candidate_path, job, sandbox=sandbox)
    exec_duration = time.monotonic() - t0

    # 3. Evaluate results with oracle
    invariants = ["I1_signature", "I2_idempotency", "I3_conservation", "I4_bounds", "I5_interface"]
    results_stats: Dict[str, Any] = {
        inv: {
            "normal": {"passed": 0, "failed": 0} if mode == "normal" else None,
            "restart": {"passed": 0, "failed": 0} if mode == "restart" else None,
        }
        for inv in invariants
    }

    failures: List[Dict[str, Any]] = []
    total_seeds = len(sequences)

    for seq_out in job_results["sequences"]:
        seed = seq_out["seed"]
        step_results = seq_out["results"]
        steps_input = stream_map[seed]

        model = Model()
        seed_failed_invariants = set()
        first_failure: Optional[Dict[str, Any]] = None

        for step_idx, step_res in enumerate(step_results):
            raw_input_step = steps_input[step_idx]
            raw_body, signature, tag = decode_step(raw_input_step)
            resp = step_res["response"]
            snapshot = step_res["snapshot"]

            chk = verify_step(
                step_idx=step_idx,
                raw_body=raw_body,
                signature=signature,
                secret=secret,
                step_response=resp,
                db_snapshot=snapshot,
                model=model,
                mode=mode,
            )

            if chk.has_financial_violation:
                seed_failed_invariants.add(chk.violation_invariant)
                if first_failure is None:
                    # Render friendly stream steps preview
                    stream_preview = []
                    for s in steps_input:
                        rb, sig, tg = decode_step(s)
                        try:
                            parsed_ev = json.loads(rb.decode("utf-8"))
                        except Exception:
                            parsed_ev = {"raw": repr(rb[:40])}
                        stream_preview.append(parsed_ev)

                    first_failure = {
                        "invariant": chk.violation_invariant,
                        "severity": chk.violation_severity,
                        "rule": chk.violation_rule,
                        "mode": mode,
                        "seed": seed,
                        "first_bad_step": step_idx,
                        "stream": stream_preview,
                        "minimal_stream": [],
                        "one_minimal": False,
                        "shrink_history": [],
                        "expected": chk.expected_state,
                        "observed": chk.observed_state,
                        "explanation": chk.explanation,
                        "classification": {
                            "label": "unreviewed",
                            "by": "agent-proposed",
                            "note": f"Seed {seed} failed at step {step_idx}",
                        },
                    }
            elif chk.has_interface_violation:
                seed_failed_invariants.add("I5_interface")
                if first_failure is None:
                    first_failure = {
                        "invariant": "I5_interface",
                        "severity": "interface",
                        "rule": "R0",
                        "mode": mode,
                        "seed": seed,
                        "first_bad_step": step_idx,
                        "stream": [],
                        "minimal_stream": [],
                        "one_minimal": False,
                        "shrink_history": [],
                        "expected": chk.expected_state,
                        "observed": chk.observed_state,
                        "explanation": chk.explanation,
                        "classification": {
                            "label": "unreviewed",
                            "by": "agent-proposed",
                            "note": f"Interface violation at step {step_idx}",
                        },
                    }

        for inv in invariants:
            if inv in seed_failed_invariants:
                results_stats[inv][mode]["failed"] += 1
            else:
                results_stats[inv][mode]["passed"] += 1

        if first_failure is not None:
            failures.append(first_failure)

    # 4. Automatic shrinking for first failing sequential seed of each distinct (invariant, rule)
    if auto_shrink and failures:
        from shrink import format_step_for_json, shrink_failure

        shrunk_keys = set()
        for f in failures:
            inv = f["invariant"]
            rule = f["rule"]
            key = (inv, rule)
            raw_seq = stream_map.get(f["seed"], [])
            if key not in shrunk_keys and raw_seq:
                shrunk_keys.add(key)
                shrink_failure(
                    candidate_path=candidate_path,
                    failure=f,
                    raw_stream=raw_seq,
                    mode=mode,
                    sandbox=sandbox,
                    secret=secret,
                    amount_pass_enabled=amount_pass_enabled,
                )
            else:
                f["stream"] = [format_step_for_json(s) for s in raw_seq]
                f["minimal_stream"] = []
                f["shrink_history"] = []
                f["one_minimal"] = False
                f["repro"] = {"runs": 0, "reproduced": 0}

    now_iso = datetime.now(timezone.utc).isoformat()
    clean_stem = candidate_path.stem
    run_id = f"run_{clean_stem}_{int(time.time())}"

    run_data: Dict[str, Any] = {
        "run_id": run_id,
        "contract_version": "1.0",
        "spec_sha": spec_sha,
        "oracle_sha": oracle_sha,
        "created_at": now_iso,
        "candidate": {
            "id": clean_stem,
            "model": model_id,
            "condition": condition,
            "sample": sample_num,
            "sha256": candidate_sha,
            "source": source,
            "label": label or f"Candidate {clean_stem}",
        },
        "harness": {
            "mode_set": [mode],
            "docker": sandbox,
            "cpus": 1,
        },
        "seeds": [seed_range[0], seed_range[1]],
        "results": results_stats,
        "concurrency": {
            "scenario_A": {"trials": 0, "failed": 0, "warnings": 0},
            "scenario_B": {"trials": 0, "failed": 0, "warnings": 0},
        },
        "failures": failures,
        "noncompliant": None,
        "repair_of": None,
    }

    # Validate against schema
    errors = validate(run_data)
    if errors:
        raise ValueError(f"Run JSON failed validation: {errors}")

    # Write run file
    runs_dir = repo_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    out_file = runs_dir / f"{run_id}.json"
    out_file.write_text(json.dumps(run_data, indent=2), encoding="utf-8")

    # Print summary table
    print("=" * 65)
    print(f" PaySift Candidate Execution: {candidate_path.name}")
    print("=" * 65)
    print(f" Run ID       : {run_id}")
    print(f" Mode         : {mode} | Seeds: {seed_range[0]}..{seed_range[1]} ({total_seeds} total)")
    print(f" Execution    : {exec_duration:.2f}s | Sandbox: {sandbox}")
    print(f" Spec SHA     : {spec_sha[:16]}... | Oracle SHA: {oracle_sha[:16]}...")
    print("-" * 65)
    mode_label = "Restart" if mode == "restart" else "Normal"
    print(f" {'Invariant':<18} | {f'{mode_label} Passed':<14} | {f'{mode_label} Failed':<14} | {'Status'}")
    print("-" * 65)
    all_financial_passed = True
    for inv in invariants:
        stat = results_stats[inv][mode]
        p = stat["passed"] if stat else 0
        f = stat["failed"] if stat else 0
        status = "PASS" if f == 0 else "FAIL"
        if f > 0 and inv != "I5_interface":
            all_financial_passed = False
        print(f" {inv:<18} | {p:<14} | {f:<14} | {status}")
    print("-" * 65)
    print(f" Total Failures Logged : {len(failures)}")
    print(f" Saved Run JSON to     : {out_file}")
    print("=" * 65)

    return run_data
