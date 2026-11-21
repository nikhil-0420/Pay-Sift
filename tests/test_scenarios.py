"""Unit tests for fixed break-it scenarios (scenarios/scenarios.py)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from scenarios.scenarios import SCENARIOS, resolve_candidate_path, run_scenario


def test_scenario_definitions_count_and_keys():
    """Verify all 6 canonical scenarios are defined with required attributes."""
    expected = [
        "duplicate_capture",
        "forged_signature",
        "over_refund",
        "bool_amount",
        "restart_between_calls",
        "rejected_redelivery",
    ]
    assert sorted(SCENARIOS.keys()) == sorted(expected)
    for name, sc in SCENARIOS.items():
        assert "name" in sc
        assert "title" in sc
        assert "rule" in sc
        assert "invariant" in sc
        assert "mode" in sc
        assert "explanation" in sc
        assert "steps" in sc
        assert len(sc["steps"]) >= 1


def test_resolve_candidate_path():
    """Verify candidate alias and mutant resolution."""
    path, cid, is_trusted = resolve_candidate_path("reference")
    assert is_trusted is True
    assert cid == "reference"
    assert path.name == "handler_ref.py"

    path_m1, cid_m1, trusted_m1 = resolve_candidate_path("m1_no_dedupe")
    assert trusted_m1 is True
    assert cid_m1 == "m1_no_dedupe"
    assert path_m1.name == "m1_no_dedupe.py"


def test_run_scenario_reference_clean():
    """Reference handler must pass all 6 scenarios cleanly."""
    for s_name in SCENARIOS:
        res = run_scenario("reference", s_name)
        assert res["verdict"] == "pass", f"Reference failed scenario {s_name}: {res.get('failure')}"
        assert res["ledger_diff"]["balance_diff_paise"] == 0


def test_run_scenario_m1_duplicate_capture():
    """m1_no_dedupe must fail duplicate_capture scenario with positive balance diff."""
    res = run_scenario("m1_no_dedupe", "duplicate_capture")
    assert res["verdict"] == "fail"
    assert res["failure"]["rule"] == "R3"
    assert res["ledger_diff"]["balance_diff_paise"] == 50000
    assert "Rs 500.00 created from nothing" in res["ledger_diff"]["diff_summary"]


def test_run_scenario_m3_over_refund():
    """m3_no_bound must fail over_refund scenario with R6."""
    res = run_scenario("m3_no_bound", "over_refund")
    assert res["verdict"] == "fail"
    assert res["failure"]["rule"] == "R6"


def test_scenario_verdicts_json_structure():
    """Verify runs/scenario_verdicts.json exists and has valid top-level schema."""
    p = Path("runs/scenario_verdicts.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "scenarios" in data
    assert "candidates" in data
    assert "by_candidate" in data
    assert "by_scenario" in data
    assert len(data["candidates"]) >= 14
