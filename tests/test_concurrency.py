"""Unit tests for Concurrency Harness and Scenarios A & B (Gate 6)."""

from __future__ import annotations

from pathlib import Path
import pytest

from runner.concurrency import run_scenario_a, run_scenario_b, run_concurrency_suite


def test_reference_passes_concurrency_scenarios():
    """Assert reference handler passes both concurrency scenarios without violations."""
    ref_file = Path("ref/handler_ref.py")
    res = run_concurrency_suite(ref_file, trials=15, processes=8)
    assert res["scenario_A"]["failed"] == 0
    assert res["scenario_A"]["evidence"] is None
    assert res["scenario_B"]["failed"] == 0
    assert res["scenario_B"]["evidence"] is None


def test_m8_fails_scenario_a():
    """Assert mutant m8 fails Scenario A due to duplicate capture race condition."""
    m8_file = Path("mutants/m8_check_then_insert.py")
    res = run_scenario_a(m8_file, trials=15, processes=8)
    assert res["failed"] > 0
    assert res["evidence"] is not None
    assert res["evidence"]["scenario"] == "scenario_A"
    assert res["evidence"]["observed"]["captures_count"] > 1


def test_m9_fails_scenario_b():
    """Assert mutant m9 fails Scenario B due to concurrent refund balance race condition."""
    m9_file = Path("mutants/m9_bound_race.py")
    res = run_scenario_b(m9_file, trials=15, processes=8)
    assert res["failed"] > 0
    assert res["evidence"] is not None
    assert res["evidence"]["scenario"] == "scenario_B"
    assert res["evidence"]["observed"]["refunds_count"] > 1
    assert res["evidence"]["observed"]["refunded_paise"] > 60000
