"""Tests for restart-between-calls mode (Gate 5)."""

from __future__ import annotations

from pathlib import Path
import pytest

from runner.run_candidate import run_candidate


def test_reference_passes_restart_mode():
    """Assert reference handler passes all invariants across all restart seeds."""
    ref_path = Path("ref/handler_ref.py")
    res = run_candidate(ref_path, mode="restart")
    assert len(res["failures"]) == 0
    for inv, stats in res["results"].items():
        assert stats["restart"]["failed"] == 0
        assert stats["restart"]["passed"] == 20


def test_m7_passes_normal_mode():
    """Assert mutant m7 passes all invariants in normal mode (long-lived process)."""
    m7_path = Path("mutants/m7_inmemory_dedupe.py")
    res = run_candidate(m7_path, seed_range=(0, 99), mode="normal")
    assert len(res["failures"]) == 0
    for inv, stats in res["results"].items():
        assert stats["normal"]["failed"] == 0
        assert stats["normal"]["passed"] == 100


def test_m7_fails_restart_mode_with_r9():
    """Assert mutant m7 fails in restart mode with Rule R9 (restart durability)."""
    m7_path = Path("mutants/m7_inmemory_dedupe.py")
    res = run_candidate(m7_path, mode="restart")
    assert len(res["failures"]) > 0
    rules = set(f["rule"] for f in res["failures"])
    assert "R9" in rules
    invs = set(f["invariant"] for f in res["failures"])
    assert "I2_idempotency" in invs
