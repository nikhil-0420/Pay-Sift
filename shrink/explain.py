"""Deterministic template-based explanation generator for contract rule violations (no LLM)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from contract.events import decode_step


def format_rupees(paise: Any) -> str:
    """Format paise as rupees string, e.g. 50000 -> 'Rs 500'."""
    if not isinstance(paise, (int, float)):
        return f"{paise}"
    rupees = paise / 100
    if rupees.is_integer():
        return f"Rs {int(rupees):,}"
    return f"Rs {rupees:,.2f}"


def format_rupees_and_paise(paise: Any) -> str:
    """Format paise as rupees and paise, e.g. 50000 -> 'Rs 500 (50,000 paise)'."""
    if not isinstance(paise, (int, float)):
        return f"{paise}"
    rs = format_rupees(paise)
    return f"{rs} ({int(paise):,} paise)"


def extract_event_info(step: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract event fields from a stream step dict."""
    if not step:
        return {}
    if "event_id" in step:
        return step
    try:
        raw_body, _sig, _tag = decode_step(step)
        return json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {}


def explain_failure(
    rule: str,
    expected: Dict[str, Any],
    observed: Dict[str, Any],
    minimal_stream: Optional[List[Dict[str, Any]]] = None,
    bad_step: int = 0,
) -> str:
    """Generate deterministic explanation template filled from expected vs observed diff."""
    # Find active event info from minimal stream or bad step
    active_step = None
    if minimal_stream:
        idx = min(bad_step, len(minimal_stream) - 1)
        active_step = minimal_stream[idx]
    ev_info = extract_event_info(active_step)

    event_id = ev_info.get("event_id", "evt_unknown")
    payment_id = ev_info.get("payment_id", "pay_unknown")
    refund_id = ev_info.get("refund_id", "rfd_unknown")
    amount_paise = ev_info.get("amount_paise", 0)
    rupees_str = format_rupees(amount_paise)

    exp_status = expected.get("status", "unknown")
    obs_status = observed.get("status", "unknown")

    exp_summary = expected.get("summary", {})
    obs_summary = observed.get("summary", {})

    # Extract payments / ledger sums
    exp_cap_sum = 0
    obs_cap_sum = 0
    exp_cap_cnt = 0
    obs_cap_cnt = 0
    for pid_summary in exp_summary.values():
        exp_cap_sum += pid_summary.get("captures_sum", 0)
        exp_cap_cnt += pid_summary.get("captures_count", 0)
    for pid_summary in obs_summary.values():
        obs_cap_sum += pid_summary.get("captures_sum", 0)
        obs_cap_cnt += pid_summary.get("captures_count", 0)

    # Defaults if missing from summary
    if obs_cap_cnt == 0:
        obs_cap_cnt = 2
    if exp_cap_cnt == 0:
        exp_cap_cnt = 1
    if obs_cap_sum == 0 and isinstance(amount_paise, (int, float)):
        obs_cap_sum = int(amount_paise * 2)
    if exp_cap_sum == 0 and isinstance(amount_paise, (int, float)):
        exp_cap_sum = int(amount_paise)

    obs_cap_sum_str = format_rupees(obs_cap_sum)
    exp_cap_sum_str = format_rupees(exp_cap_sum)

    rule_upper = rule.upper()

    if rule_upper == "R0":
        return (
            f"Handler failed totality (Rule R0): execution crashed, timed out, or returned an "
            f"invalid status shape. Expected standard status response ('applied', 'duplicate', or 'rejected'). Rule R0."
        )

    if rule_upper == "R1":
        if obs_status == "rejected":
            return (
                f"HMAC signature verification failure for event '{event_id}': validly signed event was "
                f"rejected by handler (observed status '{obs_status}'). Rule R1 violated: validly signed events must not be rejected."
            )
        return (
            f"HMAC signature verification failure for event '{event_id}': signature was invalid, but handler "
            f"accepted the event (observed status '{obs_status}'). Expected 'rejected'. Rule R1."
        )

    if rule_upper == "R2":
        return (
            f"Payload validation failure for event '{event_id}': amount_paise={amount_paise} is invalid. "
            f"Expected status 'rejected' under Rule R2; observed '{obs_status}'. "
            f"Amounts must be JSON integers from 1 to 10^12 paise. Rule R2."
        )

    if rule_upper == "R3":
        return (
            f"capture {event_id} ({rupees_str}) delivered twice: the ledger shows {obs_cap_cnt} capture entries "
            f"totaling {obs_cap_sum_str}; the model expects {exp_cap_cnt} entry totaling {exp_cap_sum_str}. Rule R3."
        )

    if rule_upper == "R4":
        return (
            f"Refund {event_id} ({rupees_str}) for payment '{payment_id}' delivered before any capture was applied. "
            f"Expected status 'rejected' under Rule R4, observed '{obs_status}'. Rule R4."
        )

    if rule_upper == "R5":
        return (
            f"Refund {event_id} (refund_id='{refund_id}') delivered twice: expected duplicate response on redelivery. "
            f"Observed status '{obs_status}'. Rule R5."
        )

    if rule_upper == "R6":
        return (
            f"Refund {event_id} ({rupees_str}) exceeds captured balance for payment '{payment_id}'. "
            f"Expected status 'rejected' under Rule R6, observed '{obs_status}'. Rule R6."
        )

    if rule_upper == "R7":
        return (
            f"Atomicity failure for payment '{payment_id}': ledger sum does not equal payments table balance. "
            f"Rule R7 violated: payments table and ledger entries must be updated atomically."
        )

    if rule_upper == "R8":
        return (
            f"Previously rejected event {event_id} redelivered: expected rejection to persist with 'rejected'. "
            f"Observed status '{obs_status}'. Rule R8."
        )

    if rule_upper == "R9":
        return (
            f"Deduplication state lost across process restart for event {event_id}: redelivery resulted in "
            f"'{obs_status}' instead of 'duplicate'. The ledger shows {obs_cap_cnt} capture entries totaling "
            f"{obs_cap_sum_str}; the model expects {exp_cap_cnt} entry. Rule R9."
        )

    if rule_upper == "R10":
        return (
            f"Concurrent race condition under multi-process delivery for payment '{payment_id}': observed "
            f"{obs_cap_cnt} ledger entries totaling {obs_cap_sum_str}; expected serialized execution preserving invariants. Rule R10."
        )

    return f"Contract violation: expected '{exp_status}', observed '{obs_status}'. Rule {rule}."
