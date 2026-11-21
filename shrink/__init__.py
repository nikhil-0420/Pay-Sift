"""Shrinker package for PaySift delta debugging, predicates, and explanation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from contract.events import TEST_SECRET, decode_step
from shrink.ddmin import amount_pass, ddmin
from shrink.explain import explain_failure, format_rupees, format_rupees_and_paise
from shrink.predicate import evaluate_stream, make_predicate


def format_step_for_json(step: Dict[str, Any]) -> Dict[str, Any]:
    """Enrich raw protocol step with parsed payload fields and human-readable summary for UI."""
    enriched = dict(step)
    try:
        raw_body, _sig, _tag = decode_step(step)
        parsed = json.loads(raw_body.decode("utf-8"))
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if k not in enriched:
                    enriched[k] = v
    except Exception:
        pass

    ev_type = enriched.get("type", "unknown")
    pid = enriched.get("payment_id", "")
    eid = enriched.get("event_id", "")
    amt = enriched.get("amount_paise")
    if amt is not None:
        rs = format_rupees(amt)
        enriched["summary"] = f"{ev_type} {eid} ({rs})" if eid else f"{ev_type} ({rs})"
    else:
        enriched["summary"] = f"{ev_type} {eid}".strip() if eid else ev_type

    return enriched


def shrink_failure(
    candidate_path: Path,
    failure: Dict[str, Any],
    raw_stream: List[Dict[str, Any]],
    mode: str = "normal",
    sandbox: bool = False,
    secret: str = TEST_SECRET,
    amount_pass_enabled: bool = False,
    max_runs: int = 200,
    max_seconds: float = 20.0,
    on_step_callback: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
) -> Dict[str, Any]:
    """Execute delta debugging over failing stream and populate failure with minimal trace.

    Args:
        candidate_path: Path to candidate handler.
        failure: Failure dictionary to populate.
        raw_stream: Original sequence of raw steps that provoked the failure.
        mode: Execution mode ('normal' or 'restart').
        sandbox: Whether to execute inside Docker sandbox.
        secret: Webhook HMAC secret.
        amount_pass_enabled: Whether to run optional second amount-reduction pass.
        max_runs: ddmin predicate evaluation budget.
        max_seconds: ddmin time budget.
        on_step_callback: Optional progress listener.

    Returns:
        Updated failure dictionary with minimal_stream, shrink_history, one_minimal,
        repro, explanation, and expected/observed states.
    """
    candidate_path = Path(candidate_path).resolve()

    # Concurrency and race failures are not applicable to sequential stream shrinking
    if failure.get("rule") == "R10" or mode in ("concurrency", "race"):
        failure["minimal_stream"] = []
        failure["shrink_history"] = []
        failure["one_minimal"] = False
        failure["shrink"] = "not_applicable"
        failure["repro"] = {"runs": 0, "reproduced": 0}
        return failure

    inv = failure["invariant"]
    rule = failure["rule"]

    pred = make_predicate(
        candidate=candidate_path,
        mode=mode,
        invariant=inv,
        rule=rule,
        sandbox=sandbox,
        secret=secret,
    )

    shrink_history: List[List[Dict[str, Any]]] = [list(raw_stream)]

    def _history_tracker(reduced_stream: List[Dict[str, Any]]) -> None:
        shrink_history.append(list(reduced_stream))
        if on_step_callback is not None:
            on_step_callback(reduced_stream)

    shrunk_stream, one_minimal = ddmin(
        stream=raw_stream,
        fails=pred,
        max_runs=max_runs,
        max_seconds=max_seconds,
        on_step=_history_tracker,
    )

    if amount_pass_enabled:
        shrunk_stream = amount_pass(shrunk_stream, pred, secret=secret)
        shrink_history.append(list(shrunk_stream))

    # 10x reproduction test
    reproduced = sum(1 for _ in range(10) if pred(shrunk_stream))
    repro = {"runs": 10, "reproduced": reproduced}

    # Evaluate minimal stream to extract exact expected/observed states and bad step index
    _inv, _rule, bad_step, chk = evaluate_stream(
        candidate_path=candidate_path,
        stream=shrunk_stream,
        mode=mode,
        sandbox=sandbox,
        secret=secret,
    )

    if chk is not None:
        exp_state = chk.expected_state
        obs_state = chk.observed_state
        bad_step_idx = bad_step if bad_step is not None else 0
    else:
        exp_state = failure.get("expected", {})
        obs_state = failure.get("observed", {})
        bad_step_idx = failure.get("first_bad_step", 0)

    # Format explanation text
    explanation = explain_failure(
        rule=rule,
        expected=exp_state,
        observed=obs_state,
        minimal_stream=shrunk_stream,
        bad_step=bad_step_idx,
    )

    failure["stream"] = [format_step_for_json(s) for s in raw_stream]
    failure["minimal_stream"] = [format_step_for_json(s) for s in shrunk_stream]
    failure["shrink_history"] = [
        [format_step_for_json(s) for s in intermediate] for intermediate in shrink_history
    ]
    failure["one_minimal"] = one_minimal
    failure["repro"] = repro
    failure["explanation"] = explanation
    failure["expected"] = exp_state
    failure["observed"] = obs_state
    failure["first_bad_step"] = bad_step_idx

    return failure


__all__ = [
    "ddmin",
    "amount_pass",
    "make_predicate",
    "evaluate_stream",
    "explain_failure",
    "format_rupees",
    "format_rupees_and_paise",
    "format_step_for_json",
    "shrink_failure",
]
