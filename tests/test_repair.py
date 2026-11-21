"""Unit tests for Repair Loop (repair/repair.py and repair/prompt.py)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from contract.validate_run import validate as validate_run_dict
from repair.prompt import build_repair_prompt
from repair.repair import compute_before_after, run_repair


def test_build_repair_prompt():
    """Verify repair prompt includes rule text, minimal trace, and explanation."""
    prompt = build_repair_prompt(
        failing_code="def handle_event(...): pass",
        minimal_trace=[{"summary": "payment.captured evt_1 (Rs 500.00)", "tag": "cap1"}],
        rule_id="R3",
        rule_text="Event Idempotency: An event_id takes effect at most once.",
        invariant="I2_idempotency",
        explanation="Duplicate capture committed twice.",
    )
    assert "Rule R3" in prompt
    assert "Event Idempotency" in prompt
    assert "I2_idempotency" in prompt
    assert "payment.captured evt_1 (Rs 500.00)" in prompt
    assert "def handle_event(" in prompt


def test_compute_before_after():
    """Verify before vs after per-invariant delta computation."""
    before = {
        "I2_idempotency": {"normal": {"passed": 0, "failed": 1}, "restart": None},
        "I3_conservation": {"normal": {"passed": 1, "failed": 0}, "restart": None},
    }
    after = {
        "I2_idempotency": {"normal": {"passed": 1, "failed": 0}, "restart": None},
        "I3_conservation": {"normal": {"passed": 1, "failed": 0}, "restart": None},
    }
    cmp = compute_before_after(before, after)
    assert cmp["I2_idempotency"]["fixed"] is True
    assert cmp["I2_idempotency"]["regressed"] is False
    assert cmp["I3_conservation"]["fixed"] is False


def test_run_repair_stub_execution(tmp_path):
    """Verify stub repair creates a valid run JSON without caching as demo repair."""
    rep = run_repair(
        target_run_id_or_path="runs/real_example.json",
        failure_index=0,
        stub=True,
        output_dir=tmp_path / "runs",
    )
    assert rep["repair_of"] is not None
    assert rep["candidate"]["source"] == "stub"
    assert "Stub Repair" in rep["candidate"]["label"]
    assert "before_after" in rep
    assert rep["before_after"]["I2_idempotency"]["fixed"] is True

    # Validate against run schema
    errs = validate_run_dict(rep)
    assert errs == []

    # Verify stubs are NOT cached under repair/cache/
    cache_files = list(Path("repair/cache").glob("*.json"))
    assert not any("stub" in f.name for f in cache_files)
