"""Delta debugging stream minimizer (Zeller's ddmin algorithm) and amount reducer."""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from contract.events import TEST_SECRET, decode_step, encode_step, sign


def ddmin(
    stream: List[Any],
    fails: Callable[[List[Any]], bool],
    max_runs: int = 200,
    max_seconds: float = 20.0,
    on_step: Optional[Callable[[List[Any]], None]] = None,
) -> Tuple[List[Any], bool]:
    """Delta debugging stream minimizer according to plan section 13.

    Args:
        stream: List of stream events/steps causing a failure.
        fails: Predicate returning True if the SAME invariant+rule is still violated.
        max_runs: Maximum number of predicate evaluations allowed before budget stop.
        max_seconds: Maximum wall-clock seconds before budget stop.
        on_step: Optional callback invoked with each accepted intermediate reduced stream.

    Returns:
        (stream, one_minimal): The reduced stream and a boolean flag indicating
        whether the stream is 1-minimal (removing any single event removes the failure).
        one_minimal is True only if the loop finished at chunk size 1 with no further reduction;
        False if the budget stopped it.
    """
    start = time.monotonic()
    runs = 0
    n = 2

    def test(c: List[Any]) -> bool:
        nonlocal runs
        runs += 1
        return fails(c)

    # Initial stream must satisfy failure condition
    if len(stream) < 2:
        return stream, True

    while len(stream) >= 2:
        if runs >= max_runs or (time.monotonic() - start) > max_seconds:
            return stream, False

        chunk = max(1, len(stream) // n)
        parts = [stream[i : i + chunk] for i in range(0, len(stream), chunk)]
        reduced = False

        for i in range(len(parts)):
            if runs >= max_runs or (time.monotonic() - start) > max_seconds:
                return stream, False

            # Candidate stream is everything except part i
            cand = [e for j, p in enumerate(parts) if j != i for e in p]
            if cand and test(cand):
                stream = cand
                n = max(n - 1, 2)
                reduced = True
                if on_step is not None:
                    on_step(stream)
                break

        if not reduced:
            if chunk == 1:
                return stream, True
            n = min(len(stream), n * 2)

    return stream, True


def amount_pass(
    stream: List[Dict[str, Any]],
    fails: Callable[[List[Dict[str, Any]]], bool],
    secret: str = TEST_SECRET,
    target_amount_paise: int = 1000,
) -> List[Dict[str, Any]]:
    """Optional second pass: replace amounts with small constants while failure persists.

    Never touches values whose TYPE is the bug (bool, float, string, null, negative, zero, huge).
    Recomputes valid HMAC signatures whenever a payload body is rebuilt.
    """
    reduced_stream = list(stream)

    for idx, step in enumerate(reduced_stream):
        try:
            raw_body, orig_sig, tag = decode_step(step)
            body_dict = json.loads(raw_body.decode("utf-8"))
        except Exception:
            continue

        if not isinstance(body_dict, dict):
            continue

        orig_amt = body_dict.get("amount_paise")

        # Never touch values whose TYPE or domain is the bug:
        # bool, float, string, null, negative, zero, huge (> 10^12)
        if type(orig_amt) is not int or isinstance(orig_amt, bool):
            continue
        if orig_amt <= 0 or orig_amt > 10**12:
            continue
        if orig_amt <= target_amount_paise:
            continue

        # Try replacing with smaller constant amount
        cand_dict = dict(body_dict)
        cand_dict["amount_paise"] = target_amount_paise

        # Re-encode body canonically and re-sign
        cand_body = json.dumps(
            cand_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        new_sig = sign(cand_body, secret)
        cand_step = encode_step(cand_body, new_sig, tag)

        trial_stream = list(reduced_stream)
        trial_stream[idx] = cand_step

        if fails(trial_stream):
            reduced_stream = trial_stream

    return reduced_stream
