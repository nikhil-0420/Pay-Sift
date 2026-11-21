"""Failure predicate generator with memoization for delta debugging."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from contract.events import TEST_SECRET, decode_step
from oracle.checks import verify_step
from oracle.model import Model
from runner.run_candidate import execute
from runner.worker import native_allowed


def hash_stream(stream: List[Dict[str, Any]]) -> str:
    """Compute a deterministic hash representing the stream sequence."""
    hasher = hashlib.sha256()
    for s in stream:
        raw_b64 = str(s.get("raw_body_b64", ""))
        sig = str(s.get("signature", ""))
        tag = str(s.get("tag", ""))
        hasher.update(raw_b64.encode("ascii", errors="ignore"))
        hasher.update(b"|")
        hasher.update(sig.encode("ascii", errors="ignore"))
        hasher.update(b"|")
        hasher.update(tag.encode("ascii", errors="ignore"))
        hasher.update(b";")
    return hasher.hexdigest()


def evaluate_stream(
    candidate_path: Path,
    stream: List[Dict[str, Any]],
    mode: str = "normal",
    sandbox: bool = False,
    secret: str = TEST_SECRET,
) -> Tuple[Optional[str], Optional[str], Optional[int], Optional[Any]]:
    """Run stream on candidate in fresh DB and return (violation_invariant, violation_rule, bad_step, step_chk).

    Returns (None, None, None, None) if candidate passes all invariants on this stream.
    """
    candidate_path = Path(candidate_path).resolve()
    if sandbox:
        gate4_marker = Path("runs/GATE4_PASSED")
        if not gate4_marker.is_file():
            raise RuntimeError("Sandbox execution blocked: runs/GATE4_PASSED missing (Gate 4 not passed).")
    else:
        if not native_allowed(candidate_path):
            raise PermissionError(f"Untrusted candidate '{candidate_path}' cannot be run natively.")

    job = {
        "candidate_file": str(candidate_path),
        "mode": mode,
        "secret": secret,
        "sequences": [{"seed": 0, "steps": stream}],
    }

    job_res = execute(candidate_path, job, sandbox=sandbox)
    step_results = job_res["sequences"][0]["results"]

    model = Model()
    for step_idx, step_res in enumerate(step_results):
        raw_input_step = stream[step_idx]
        raw_body, signature, _tag = decode_step(raw_input_step)
        resp = step_res.get("response")
        snapshot = step_res.get("snapshot", {})

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
            return chk.violation_invariant, chk.violation_rule, step_idx, chk
        elif chk.has_interface_violation:
            return "I5_interface", "R0", step_idx, chk

    return None, None, None, None


def make_predicate(
    candidate: Path | str,
    mode: str = "normal",
    invariant: str = "I2_idempotency",
    rule: str = "R3",
    sandbox: bool = False,
    secret: str = TEST_SECRET,
) -> Callable[[List[Dict[str, Any]]], bool]:
    """Create a failure predicate for ddmin.

    The returned fails(stream) executes the candidate in a fresh database under the given mode,
    and returns True only if the SAME invariant AND rule ID are violated.

    Memoizes results by stream hash within this predicate instance.
    """
    candidate_path = Path(candidate).resolve()
    cache: Dict[str, bool] = {}

    def fails(stream: List[Dict[str, Any]]) -> bool:
        if not stream:
            return False

        h = hash_stream(stream)
        if h in cache:
            return cache[h]

        inv_hit, rule_hit, _step, _chk = evaluate_stream(
            candidate_path=candidate_path,
            stream=stream,
            mode=mode,
            sandbox=sandbox,
            secret=secret,
        )

        result = (inv_hit == invariant and rule_hit == rule)
        cache[h] = result
        return result

    return fails
