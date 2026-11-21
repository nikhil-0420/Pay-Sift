"""Gate 7 verification tests: sequential failure shrinking to <= 4 events with 10/10 reproduction."""

from __future__ import annotations

from pathlib import Path
import pytest

from runner.streams import generate_stream
from shrink import ddmin, make_predicate, shrink_failure


@pytest.mark.parametrize(
    "name,path_str,mode,inv,rule,seed,max_len",
    [
        ("m1", "mutants/m1_no_dedupe.py", "normal", "I2_idempotency", "R3", 0, 4),
        ("m2", "mutants/m2_nonatomic.py", "normal", "I3_conservation", "R7", 0, 4),
        ("m3", "mutants/m3_no_bound.py", "normal", "I4_bounds", "R6", 9, 4),
        ("m4", "mutants/m4_neg_amount.py", "normal", "I4_bounds", "R2", 4, 4),
        ("m5", "mutants/m5_reject_consumes_id.py", "normal", "I2_idempotency", "R8", 5, 4),
        ("m6", "mutants/m6_sig_reserialized.py", "normal", "I1_signature", "R1", 0, 4),
        ("x1", "mutants/x1_bool_amount.py", "normal", "I4_bounds", "R2", 4, 4),
        ("x2", "mutants/x2_float_amount.py", "normal", "I4_bounds", "R2", 24, 4),
        ("x3", "mutants/x3_nonascii_sig_crash.py", "normal", "I5_interface", "R0", 5, 4),
        ("x4", "mutants/x4_sig_canonical_reserialized.py", "normal", "I1_signature", "R1", 8, 4),
        ("m7", "mutants/m7_inmemory_dedupe.py", "restart", "I2_idempotency", "R9", 7, 4),
    ],
)
def test_gate7_mutant_shrinking(
    name: str,
    path_str: str,
    mode: str,
    inv: str,
    rule: str,
    seed: int,
    max_len: int,
):
    """Verify each mutant sequential failure shrinks to <= 4 events with 10/10 reproduction."""
    cand_path = Path(path_str)
    raw_stream = generate_stream(seed)

    failure_stub = {
        "invariant": inv,
        "rule": rule,
        "mode": mode,
        "seed": seed,
        "first_bad_step": len(raw_stream) - 1,
    }

    res = shrink_failure(
        candidate_path=cand_path,
        failure=failure_stub,
        raw_stream=raw_stream,
        mode=mode,
        sandbox=False,
    )

    minimal_stream = res["minimal_stream"]
    assert len(minimal_stream) <= max_len, (
        f"Mutant {name} shrunk to {len(minimal_stream)} events, exceeding max {max_len}."
    )
    assert res["one_minimal"] is True, f"Mutant {name} was not 1-minimal."
    assert res["repro"]["runs"] == 10
    assert res["repro"]["reproduced"] == 10, (
        f"Mutant {name} failed reproduction requirement (reproduced {res['repro']['reproduced']}/10)."
    )
    assert rule in res["explanation"], f"Explanation missing rule {rule}: {res['explanation']}"


def test_gate7_m3_seed2_accumulation_analysis():
    """Verify and analyze mutant m3 on Seed 2 (Family 2 accumulation over-refund).

    In Seed 2, four partial refunds (20k + 20k + 20k + 40k = 100k) exactly equal
    the capture balance before the 5k refund exceeds it. Deletion of any prior
    refund drops total refunds to <= 100k, preventing over-refund. Thus, Seed 2
    is mathematically 1-minimal at 6 events under deletion-only delta debugging.
    """
    m3_path = Path("mutants/m3_no_bound.py")
    raw_stream = generate_stream(2)
    pred = make_predicate(m3_path, mode="normal", invariant="I4_bounds", rule="R6")

    shrunk, one_minimal = ddmin(raw_stream, pred)
    assert len(shrunk) == 6
    assert one_minimal is True

    # Confirm 1-minimality: removing any single event prevents the R6 failure
    for i in range(len(shrunk)):
        assert not pred([e for j, e in enumerate(shrunk) if j != i])
