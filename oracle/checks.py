"""Oracle verification checks comparing DB snapshots and responses to model truth."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from oracle.model import Model
from oracle.validate import check_signature, validate_payload


RULE_TO_INVARIANT: Dict[str, Tuple[str, str]] = {
    "R1": ("I1_signature", "financial"),
    "R3": ("I2_idempotency", "financial"),
    "R8": ("I2_idempotency", "financial"),
    "R9": ("I2_idempotency", "financial"),
    "R4": ("I3_conservation", "financial"),
    "R7": ("I3_conservation", "financial"),
    "R2": ("I4_bounds", "financial"),
    "R5": ("I4_bounds", "financial"),
    "R6": ("I4_bounds", "financial"),
    "R0": ("I5_interface", "interface"),
}


def rule_for_concurrency(scenario: str) -> Tuple[str, str, str]:
    """Return (rule, invariant, severity) for concurrency scenario failures."""
    if scenario == "scenario_A":
        return "R10", "I2_idempotency", "financial"
    elif scenario == "scenario_B":
        return "R10", "I4_bounds", "financial"
    return "R10", "I4_bounds", "financial"


def compute_oracle_sha() -> str:
    """Compute deterministic SHA-256 over oracle/*.py files (LF-normalized)."""
    oracle_dir = Path(__file__).resolve().parent
    files = sorted(oracle_dir.glob("*.py"))
    hasher = hashlib.sha256()
    for f in files:
        text = f.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
        hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()


class OracleStepResult:
    """Detailed result of checking a single step."""

    def __init__(
        self,
        step_idx: int,
        expected_status: str,
        expected_rule: str,
        observed_status: Optional[str],
        has_financial_violation: bool,
        has_interface_violation: bool,
        violation_rule: Optional[str] = None,
        violation_invariant: Optional[str] = None,
        violation_severity: Optional[str] = None,
        explanation: str = "",
        expected_state: Optional[Dict[str, Any]] = None,
        observed_state: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.step_idx = step_idx
        self.expected_status = expected_status
        self.expected_rule = expected_rule
        self.observed_status = observed_status
        self.has_financial_violation = has_financial_violation
        self.has_interface_violation = has_interface_violation
        self.violation_rule = violation_rule
        self.violation_invariant = violation_invariant
        self.violation_severity = violation_severity
        self.explanation = explanation
        self.expected_state = expected_state or {}
        self.observed_state = observed_state or {}


def verify_step(
    step_idx: int,
    raw_body: bytes,
    signature: str,
    secret: str,
    step_response: Any,
    db_snapshot: Dict[str, Any],
    model: Model,
    mode: str = "normal",
) -> OracleStepResult:
    """Verify candidate execution at a single step against ground truth.

    Args:
        step_idx: Index of the current step in the sequence.
        raw_body: Raw bytes sent to candidate.
        signature: Hex signature sent to candidate.
        secret: Webhook secret.
        step_response: Value returned by candidate handler (or error dict / timeout).
        db_snapshot: Snapshot read directly from SQLite by worker connection.
        model: Model instance tracking ground truth state.
    """
    # 1. Independent validation
    sig_ok = check_signature(raw_body, signature, secret)
    payload_ok, parsed_payload, _ = validate_payload(raw_body)

    # 2. Model state transition
    expected_status, expected_rule = model.apply(raw_body, sig_ok, payload_ok, parsed_payload)
    expected_snapshot = model.get_snapshot()

    # 3. Check R0 / Interface Shape
    observed_status: Optional[str] = None
    interface_violation = False
    interface_rule = "R0"
    interface_explanation = ""

    if step_response == "timeout":
        interface_violation = True
        interface_explanation = f"Step {step_idx}: handler execution timed out (R0)."
    elif isinstance(step_response, dict) and "error" in step_response and "status" not in step_response:
        interface_violation = True
        interface_explanation = f"Step {step_idx}: uncaught exception in handler: {step_response.get('error')} (R0)."
    elif not isinstance(step_response, dict):
        interface_violation = True
        interface_explanation = f"Step {step_idx}: handler returned non-dict type {type(step_response).__name__} (R0)."
    else:
        observed_status = step_response.get("status")
        if observed_status not in ("applied", "duplicate", "rejected"):
            interface_violation = True
            interface_explanation = f"Step {step_idx}: invalid status string '{observed_status}' (R0)."
        elif observed_status != expected_status:
            interface_violation = True
            interface_explanation = (
                f"Step {step_idx}: status mismatch. Expected '{expected_status}', "
                f"observed '{observed_status}' ({expected_rule})."
            )

    # 4. Check Internal DB Consistency (R7: payments must agree with ledger)
    db_payments = {p["payment_id"]: p for p in db_snapshot.get("payments", [])}
    db_summary = db_snapshot.get("summary", {})

    r7_violation = False
    r7_explanation = ""
    for pid, pdata in db_payments.items():
        psum = db_summary.get(pid, {"captures_sum": 0, "refunds_sum": 0})
        if pdata["captured_paise"] != psum["captures_sum"]:
            r7_violation = True
            r7_explanation = (
                f"Step {step_idx}: R7 atomicity violation. payments.captured_paise ({pdata['captured_paise']}) "
                f"!= ledger sum ({psum['captures_sum']}) for payment '{pid}'."
            )
            break
        if pdata["refunded_paise"] != psum["refunds_sum"]:
            r7_violation = True
            r7_explanation = (
                f"Step {step_idx}: R7 atomicity violation. payments.refunded_paise ({pdata['refunded_paise']}) "
                f"!= ledger sum ({psum['refunds_sum']}) for payment '{pid}'."
            )
            break

    # 5. Check DB Snapshot vs Model Ground Truth
    exp_payments = {p["payment_id"]: p for p in expected_snapshot.get("payments", [])}
    exp_summary = expected_snapshot.get("summary", {})

    state_divergence = False
    state_explanation = ""

    if r7_violation:
        state_divergence = True
        state_explanation = r7_explanation
        cited_financial_rule = "R7"
    else:
        # Compare payments set
        if set(db_payments.keys()) != set(exp_payments.keys()):
            state_divergence = True
            state_explanation = (
                f"Step {step_idx}: payment IDs mismatch. Expected {sorted(exp_payments.keys())}, "
                f"observed {sorted(db_payments.keys())} ({expected_rule})."
            )
        else:
            for pid, exp_p in exp_payments.items():
                act_p = db_payments[pid]
                if act_p["captured_paise"] != exp_p["captured_paise"] or act_p["refunded_paise"] != exp_p["refunded_paise"]:
                    state_divergence = True
                    state_explanation = (
                        f"Step {step_idx}: balance mismatch for '{pid}'. "
                        f"Expected captured={exp_p['captured_paise']}, refunded={exp_p['refunded_paise']}; "
                        f"Observed captured={act_p['captured_paise']}, refunded={act_p['refunded_paise']} ({expected_rule})."
                    )
                    break

        if not state_divergence:
            # Compare ledger counts and sums
            for pid, exp_s in exp_summary.items():
                act_s = db_summary.get(pid, {"captures_count": 0, "captures_sum": 0, "refunds_count": 0, "refunds_sum": 0})
                if (
                    act_s["captures_count"] != exp_s["captures_count"]
                    or act_s["captures_sum"] != exp_s["captures_sum"]
                    or act_s["refunds_count"] != exp_s["refunds_count"]
                    or act_s["refunds_sum"] != exp_s["refunds_sum"]
                ):
                    state_divergence = True
                    state_explanation = (
                        f"Step {step_idx}: ledger summary mismatch for '{pid}'. "
                        f"Expected captures={exp_s['captures_count']} (₹{exp_s['captures_sum']}), "
                        f"refunds={exp_s['refunds_count']} (₹{exp_s['refunds_sum']}); "
                        f"Observed captures={act_s['captures_count']} (₹{act_s['captures_sum']}), "
                        f"refunds={act_s['refunds_count']} (₹{act_s['refunds_sum']}) ({expected_rule})."
                    )
                    break

        # Check if candidate erroneously rejected a validly signed event due to signature check
        # Under Rule R1: "Conversely, a validly signed event MUST NOT be rejected for signature."
        resp_reason = str(step_response.get("reason", "")).lower() if isinstance(step_response, dict) else ""
        if sig_ok and observed_status == "rejected" and ("sig" in resp_reason or "r1" in resp_reason):
            cited_financial_rule = "R1"
        else:
            cited_financial_rule = expected_rule

        # In restart mode, deduplication failures attribute to R9 (Restart durability)
        if mode == "restart" and cited_financial_rule in ("R3", "R8"):
            cited_financial_rule = "R9"

    # Resolve primary violation
    if state_divergence:
        inv, sev = RULE_TO_INVARIANT.get(cited_financial_rule, ("I3_conservation", "financial"))
        return OracleStepResult(
            step_idx=step_idx,
            expected_status=expected_status,
            expected_rule=expected_rule,
            observed_status=observed_status,
            has_financial_violation=True,
            has_interface_violation=interface_violation,
            violation_rule=cited_financial_rule,
            violation_invariant=inv,
            violation_severity=sev,
            explanation=state_explanation,
            expected_state=expected_snapshot,
            observed_state=db_snapshot,
        )
    elif interface_violation:
        return OracleStepResult(
            step_idx=step_idx,
            expected_status=expected_status,
            expected_rule=expected_rule,
            observed_status=observed_status,
            has_financial_violation=False,
            has_interface_violation=True,
            violation_rule="R0",
            violation_invariant="I5_interface",
            violation_severity="interface",
            explanation=interface_explanation,
            expected_state=expected_snapshot,
            observed_state=db_snapshot,
        )
    else:
        return OracleStepResult(
            step_idx=step_idx,
            expected_status=expected_status,
            expected_rule=expected_rule,
            observed_status=observed_status,
            has_financial_violation=False,
            has_interface_violation=False,
            expected_state=expected_snapshot,
            observed_state=db_snapshot,
        )
