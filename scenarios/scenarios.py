"""Fixed break-it scenarios for PaySift live demonstration and static replay.

Defines six canonical scenarios:
1. duplicate_capture (R3, normal)
2. forged_signature (R1, normal)
3. over_refund (R6, normal)
4. bool_amount (R2, normal)
5. restart_between_calls (R9, restart)
6. rejected_redelivery (R8, normal)
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple, Union

from contract.events import TEST_SECRET, canonical_bytes, sign
from oracle.checks import RULE_TO_INVARIANT, verify_step
from oracle.model import Model
from runner.sandbox import is_docker_available, is_docker_image_available, run_in_sandbox
from runner.worker import native_allowed, run_sequence_normal, run_sequence_restart


def _make_step(data: Dict[str, Any], tag: str, valid_sig: bool = True, custom_sig: Optional[str] = None) -> Dict[str, str]:
    """Helper to construct a raw step with base64 payload and signature."""
    raw = canonical_bytes(data)
    sig = custom_sig if custom_sig is not None else (sign(raw, TEST_SECRET) if valid_sig else "00" * 32)
    return {
        "raw_body_b64": base64.b64encode(raw).decode("ascii"),
        "signature": sig,
        "tag": tag,
    }


def _build_scenarios() -> Dict[str, Dict[str, Any]]:
    """Build the six fixed scenario specifications."""
    # 1. duplicate_capture
    cap_dup = {
        "event_id": "evt_break_dup_1",
        "payment_id": "pay_break_dup",
        "type": "payment.captured",
        "amount_paise": 50000,
    }
    step_dup_1 = _make_step(cap_dup, "capture_initial")
    step_dup_2 = _make_step(cap_dup, "capture_duplicate")

    # 2. forged_signature
    cap_forged = {
        "event_id": "evt_break_sig_1",
        "payment_id": "pay_break_sig",
        "type": "payment.captured",
        "amount_paise": 75000,
    }
    step_forged = _make_step(cap_forged, "capture_forged_sig", valid_sig=False)

    # 3. over_refund
    cap_ovr = {
        "event_id": "evt_break_ovr_cap",
        "payment_id": "pay_break_ovr",
        "type": "payment.captured",
        "amount_paise": 50000,
    }
    ref_ovr = {
        "event_id": "evt_break_ovr_ref",
        "payment_id": "pay_break_ovr",
        "refund_id": "rf_break_ovr_1",
        "type": "refund.processed",
        "amount_paise": 60000,
    }
    step_ovr_1 = _make_step(cap_ovr, "capture_500")
    step_ovr_2 = _make_step(ref_ovr, "refund_600_excess")

    # 4. bool_amount (amount_paise is boolean True)
    raw_bool = b'{"amount_paise":true,"event_id":"evt_break_bool","payment_id":"pay_break_bool","type":"payment.captured"}'
    sig_bool = sign(raw_bool, TEST_SECRET)
    step_bool = {
        "raw_body_b64": base64.b64encode(raw_bool).decode("ascii"),
        "signature": sig_bool,
        "tag": "capture_boolean_amount",
    }

    # 5. restart_between_calls
    cap_rst = {
        "event_id": "evt_break_rst_1",
        "payment_id": "pay_break_rst",
        "type": "payment.captured",
        "amount_paise": 100000,
    }
    step_rst_1 = _make_step(cap_rst, "capture_before_restart")
    step_rst_2 = _make_step(cap_rst, "capture_after_restart_dup")

    # 6. rejected_redelivery (rejected event must not consume event_id)
    raw_neg = b'{"amount_paise":-5000,"event_id":"evt_break_rej_1","payment_id":"pay_break_rej","type":"payment.captured"}'
    step_rej_1 = {
        "raw_body_b64": base64.b64encode(raw_neg).decode("ascii"),
        "signature": sign(raw_neg, TEST_SECRET),
        "tag": "rejected_negative_amount",
    }
    cap_valid_redelivery = {
        "event_id": "evt_break_rej_1",
        "payment_id": "pay_break_rej",
        "type": "payment.captured",
        "amount_paise": 50000,
    }
    step_rej_2 = _make_step(cap_valid_redelivery, "valid_redelivery_same_id")

    return {
        "duplicate_capture": {
            "name": "duplicate_capture",
            "title": "Duplicate Capture (Event Idempotency)",
            "rule": "R3",
            "invariant": "I2_idempotency",
            "mode": "normal",
            "explanation": "Delivers the same valid payment.captured event twice. A compliant handler must deduplicate (Rule R3) and record exactly one ledger entry.",
            "steps": [step_dup_1, step_dup_2],
        },
        "forged_signature": {
            "name": "forged_signature",
            "title": "Forged Signature Verification",
            "rule": "R1",
            "invariant": "I1_signature",
            "mode": "normal",
            "explanation": "Delivers a capture event with an invalid HMAC-SHA256 signature. The handler must reject the event (Rule R1) and commit no state to payments or ledger.",
            "steps": [step_forged],
        },
        "over_refund": {
            "name": "over_refund",
            "title": "Refund Balance Bound",
            "rule": "R6",
            "invariant": "I4_bounds",
            "mode": "normal",
            "explanation": "Captures Rs 500.00, then attempts to refund Rs 600.00. Total refunds cannot exceed captured amount (Rule R6); handler must reject the excess refund.",
            "steps": [step_ovr_1, step_ovr_2],
        },
        "bool_amount": {
            "name": "bool_amount",
            "title": "Boolean Amount Rejection",
            "rule": "R2",
            "invariant": "I4_bounds",
            "mode": "normal",
            "explanation": "Delivers a capture event with amount_paise set to boolean true instead of an integer. JSON schema rejects booleans (Rule R2); handler must reject without state change.",
            "steps": [step_bool],
        },
        "restart_between_calls": {
            "name": "restart_between_calls",
            "title": "Durability Across Restarts",
            "rule": "R9",
            "invariant": "I2_idempotency",
            "mode": "restart",
            "explanation": "Simulates worker process restart between webhook deliveries. Idempotency records must persist across process lifetimes in SQLite (Rule R9).",
            "steps": [step_rst_1, step_rst_2],
        },
        "rejected_redelivery": {
            "name": "rejected_redelivery",
            "title": "Rejection Non-Consumption",
            "rule": "R8",
            "invariant": "I2_idempotency",
            "mode": "normal",
            "explanation": "Delivers an invalid event that is rejected, then redelivers the same event_id with valid parameters. Rejection must not consume the event_id (Rule R8); second call must apply.",
            "steps": [step_rej_1, step_rej_2],
        },
    }


SCENARIOS = _build_scenarios()


def resolve_candidate_path(candidate_id_or_path: Union[str, Path]) -> Tuple[Path, str, bool]:
    """Resolve a candidate identifier to its filesystem path.

    Returns:
        (path, candidate_id, is_trusted)
    """
    repo_root = Path(__file__).resolve().parent.parent
    c_str = str(candidate_id_or_path).strip()

    # Direct path
    p = Path(c_str)
    if not p.is_absolute():
        p = (repo_root / p).resolve()
    if p.exists() and p.is_file():
        cand_id = p.stem
        is_trusted = native_allowed(p)
        return p, cand_id, is_trusted

    # Named aliases
    if c_str in ("ref", "reference", "handler_ref"):
        ref_path = (repo_root / "ref" / "handler_ref.py").resolve()
        return ref_path, "reference", True

    # Mutants lookup
    mutant_path = (repo_root / "mutants" / f"{c_str}.py").resolve()
    if mutant_path.exists():
        return mutant_path, c_str, True

    # Candidate file lookup under candidates/
    matching = list((repo_root / "candidates").glob(f"*/*/{c_str}.py"))
    if matching:
        return matching[0].resolve(), c_str, False

    raise FileNotFoundError(f"Could not resolve candidate: '{candidate_id_or_path}'")


def run_scenario(
    candidate_id_or_path: Union[str, Path],
    scenario_name: str,
    secret: str = TEST_SECRET,
    force_sandbox: bool = False,
) -> Dict[str, Any]:
    """Execute a single scenario against a candidate and return verdict & ledger diff."""
    if scenario_name not in SCENARIOS:
        raise ValueError(f"Unknown scenario '{scenario_name}'. Available: {sorted(SCENARIOS.keys())}")

    scenario = SCENARIOS[scenario_name]
    cand_path, cand_id, is_trusted = resolve_candidate_path(candidate_id_or_path)

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / "contract" / "schema.sql"
    child_script = repo_root / "runner" / "child.py"

    if not is_trusted or force_sandbox:
        # Require Gate 4 Docker Sandbox
        from pilot.runner import check_sandbox_precondition
        ok, reason = check_sandbox_precondition()
        if not ok:
            raise PermissionError(f"Candidate '{cand_id}' is untrusted and Docker sandbox is unavailable: {reason}")
        # Run inside sandbox
        job = {
            "candidate_file": str(cand_path),
            "mode": scenario["mode"],
            "sequences": [{
                "seed": 0,
                "steps": scenario["steps"],
            }],
        }
        sbx_res = run_in_sandbox(job)
        if sbx_res.get("status") != "ok":
            raise RuntimeError(f"Sandbox execution failed: {sbx_res.get('error')}")
        results = sbx_res["results"][0]["steps"]
    else:
        # Native execution for trusted candidate
        if scenario["mode"] == "restart":
            results = run_sequence_restart(
                candidate_path=cand_path,
                steps=scenario["steps"],
                secret=secret,
                schema_path=schema_path,
                child_script=child_script,
            )
        else:
            results = run_sequence_normal(
                candidate_path=cand_path,
                steps=scenario["steps"],
                secret=secret,
                schema_path=schema_path,
                child_script=child_script,
            )

    # Evaluate results against oracle model
    model = Model()
    first_failure: Optional[Dict[str, Any]] = None
    step_records: List[Dict[str, Any]] = []

    for step_idx, step_input in enumerate(scenario["steps"]):
        cand_step = results[step_idx]
        step_resp = cand_step.get("response")
        db_snap = cand_step.get("snapshot", {})

        raw_bytes = base64.b64decode(step_input["raw_body_b64"])
        sig_str = step_input.get("signature", "")

        check_res = verify_step(
            step_idx=step_idx,
            raw_body=raw_bytes,
            signature=sig_str,
            secret=secret,
            step_response=step_resp,
            db_snapshot=db_snap,
            model=model,
            mode=scenario["mode"],
        )

        step_records.append({
            "step_index": step_idx,
            "tag": step_input.get("tag"),
            "expected_status": check_res.expected_status,
            "observed_status": check_res.observed_status,
            "has_violation": check_res.has_financial_violation or check_res.has_interface_violation,
            "explanation": check_res.explanation,
        })

        if not first_failure and (check_res.has_financial_violation or check_res.has_interface_violation):
            first_failure = {
                "step_index": step_idx,
                "rule": check_res.violation_rule,
                "invariant": check_res.violation_invariant,
                "severity": check_res.violation_severity,
                "explanation": check_res.explanation,
                "expected_state": check_res.expected_state,
                "observed_state": check_res.observed_state,
            }

    # Final snapshot from last step
    final_db_snap = results[-1].get("snapshot", {}) if results else {}
    expected_snap = model.get_snapshot()

    observed_ledger = final_db_snap.get("ledger", [])
    expected_ledger = expected_snap.get("ledger", [])

    obs_captures = sum(e["amount_paise"] for e in observed_ledger if e.get("kind") == "capture")
    obs_refunds = sum(e["amount_paise"] for e in observed_ledger if e.get("kind") == "refund")
    exp_captures = sum(e["amount_paise"] for e in expected_ledger if e.get("kind") == "capture")
    exp_refunds = sum(e["amount_paise"] for e in expected_ledger if e.get("kind") == "refund")

    net_obs_balance = obs_captures - obs_refunds
    net_exp_balance = exp_captures - exp_refunds
    balance_diff_paise = net_obs_balance - net_exp_balance

    if balance_diff_paise > 0:
        diff_summary = f"+{len(observed_ledger) - len(expected_ledger)} extra entries; Rs {balance_diff_paise/100:.2f} created from nothing"
    elif balance_diff_paise < 0:
        diff_summary = f"Net balance Rs {-balance_diff_paise/100:.2f} below expected"
    elif len(observed_ledger) != len(expected_ledger):
        diff_summary = f"Entry count mismatch ({len(observed_ledger)} observed vs {len(expected_ledger)} expected)"
    else:
        diff_summary = "Ledger matches expected state exactly."

    ledger_diff = {
        "expected_count": len(expected_ledger),
        "observed_count": len(observed_ledger),
        "expected_balance_paise": net_exp_balance,
        "observed_balance_paise": net_obs_balance,
        "balance_diff_paise": balance_diff_paise,
        "diff_summary": diff_summary,
    }

    verdict = "fail" if first_failure else "pass"

    return {
        "scenario": scenario_name,
        "title": scenario["title"],
        "mode": scenario["mode"],
        "target_rule": scenario["rule"],
        "target_invariant": scenario["invariant"],
        "candidate_id": cand_id,
        "candidate_path": str(cand_path),
        "verdict": verdict,
        "failure": first_failure,
        "ledger_diff": ledger_diff,
        "observed_ledger": observed_ledger,
        "expected_ledger": expected_ledger,
        "observed_payments": final_db_snap.get("payments", []),
        "expected_payments": expected_snap.get("payments", []),
        "steps": step_records,
    }


def generate_all_scenario_verdicts(output_path: Path = Path("runs/scenario_verdicts.json")) -> Dict[str, Any]:
    """Run all 6 scenarios across reference and all mutants, and save to runs/scenario_verdicts.json."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    repo_root = Path(__file__).resolve().parent.parent

    # Collect targets
    targets = ["reference"]
    mutants = [
        "m1_no_dedupe",
        "m2_nonatomic",
        "m3_no_bound",
        "m4_neg_amount",
        "m5_reject_consumes_id",
        "m6_sig_reserialized",
        "m7_inmemory_dedupe",
        "m8_check_then_insert",
        "m9_bound_race",
        "x1_bool_amount",
        "x2_float_amount",
        "x3_nonascii_sig_crash",
        "x4_sig_canonical_reserialized",
    ]
    targets.extend(mutants)

    verdicts_by_candidate: Dict[str, Dict[str, Any]] = {}
    verdicts_by_scenario: Dict[str, Dict[str, Any]] = {s_name: {} for s_name in SCENARIOS}

    for target in targets:
        verdicts_by_candidate[target] = {}
        for s_name in SCENARIOS:
            res = run_scenario(target, s_name)
            verdicts_by_candidate[target][s_name] = res
            verdicts_by_scenario[s_name][target] = {
                "verdict": res["verdict"],
                "ledger_diff": res["ledger_diff"],
                "failure": res["failure"],
            }

    data = {
        "scenarios": {s_name: {"title": s["title"], "explanation": s["explanation"], "rule": s["rule"], "invariant": s["invariant"], "mode": s["mode"]} for s_name, s in SCENARIOS.items()},
        "candidates": targets,
        "by_candidate": verdicts_by_candidate,
        "by_scenario": verdicts_by_scenario,
    }

    output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data
