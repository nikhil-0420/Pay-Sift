"""Gate 2 verification tests: reference 100/100 pass, determinism, and mutants m1-m3."""

from __future__ import annotations

from pathlib import Path
import pytest

from runner.run_candidate import run_candidate


def test_gate2_reference_passes_all_invariants():
    """Verify reference handler passes 100/100 across all 5 invariants."""
    ref_path = Path("E:/PaySift/ref/handler_ref.py")
    run_data = run_candidate(ref_path, mode="normal", seed_range=(0, 99))

    invariants = ["I1_signature", "I2_idempotency", "I3_conservation", "I4_bounds", "I5_interface"]
    for inv in invariants:
        res = run_data["results"][inv]["normal"]
        assert res["failed"] == 0, f"Reference failed on {inv}: {res}"
        assert res["passed"] == 100, f"Reference passed count != 100 for {inv}: {res}"

    assert len(run_data["failures"]) == 0


def test_gate2_reference_repeatability():
    """Verify two consecutive runs of reference handler produce identical Run JSON (modulo run_id, created_at)."""
    ref_path = Path("E:/PaySift/ref/handler_ref.py")
    r1 = run_candidate(ref_path, mode="normal", seed_range=(0, 9))
    r2 = run_candidate(ref_path, mode="normal", seed_range=(0, 9))

    for r in (r1, r2):
        r.pop("run_id")
        r.pop("created_at")

    assert r1 == r2, "Reference runs were not identical"


def test_gate2_mutant_m1_fails_r3():
    """Verify mutant m1 (no dedupe) fails Rule R3 with 2-event divergence in failure record."""
    m1_path = Path("E:/PaySift/mutants/m1_no_dedupe.py")
    run_data = run_candidate(m1_path, mode="normal", seed_range=(0, 0))

    assert len(run_data["failures"]) > 0
    fail = run_data["failures"][0]
    assert fail["rule"] == "R3"
    assert fail["invariant"] == "I2_idempotency"
    assert fail["first_bad_step"] == 1  # 2nd step (0-indexed: 1) = 2-event divergence
    assert "Rule R3" in fail["explanation"]


def test_gate2_mutant_m2_fails_r7():
    """Verify mutant m2 (non-atomic ledger) fails Rule R7."""
    m2_path = Path("E:/PaySift/mutants/m2_nonatomic.py")
    run_data = run_candidate(m2_path, mode="normal", seed_range=(0, 0))

    assert len(run_data["failures"]) > 0
    fail = run_data["failures"][0]
    assert fail["rule"] == "R7"
    assert fail["invariant"] == "I3_conservation"
    assert "Rule R7" in fail["explanation"]


def test_gate2_mutant_m3_fails_r6():
    """Verify mutant m3 (no refund bound) fails Rule R6."""
    m3_path = Path("E:/PaySift/mutants/m3_no_bound.py")
    run_data = run_candidate(m3_path, mode="normal", seed_range=(2, 2))  # seed 2 has over-bound refund

    assert len(run_data["failures"]) > 0
    fail = run_data["failures"][0]
    assert fail["rule"] == "R6"
    assert fail["invariant"] == "I4_bounds"
    assert "Rule R6" in fail["explanation"]
