"""Unit tests for ddmin algorithm, synthetic predicates, 1-minimality, and explain generator."""

from __future__ import annotations

import time
from typing import Any, List
import pytest

from shrink.ddmin import ddmin, amount_pass
from shrink.explain import explain_failure, format_rupees, format_rupees_and_paise


def test_ddmin_synthetic_reduction():
    """Verify ddmin shrinks a 10-element stream to the exact 2 elements causing the bug."""
    stream = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

    # Predicate: failure requires both 3 and 7 to be present
    def fails(cand: List[int]) -> bool:
        return 3 in cand and 7 in cand

    reduced, one_minimal = ddmin(stream, fails)
    assert reduced == [3, 7]
    assert one_minimal is True


def test_ddmin_1_minimality_property():
    """Verify the 1-minimality property: removing any single remaining event stops the failure."""
    stream = list(range(20))

    # Failure requires 4, 9, 15
    def fails(cand: List[int]) -> bool:
        return all(x in cand for x in (4, 9, 15))

    reduced, one_minimal = ddmin(stream, fails)
    assert one_minimal is True
    assert set(reduced) == {4, 9, 15}

    # Strict 1-minimality test: removing ANY single event MUST return False
    for i in range(len(reduced)):
        single_removed = [e for j, e in enumerate(reduced) if j != i]
        assert not fails(single_removed), f"Removing {reduced[i]} did not remove failure"


def test_ddmin_budget_stop_max_runs():
    """Verify budget stop on max_runs returns one_minimal=False."""
    stream = list(range(30))

    def fails(cand: List[int]) -> bool:
        return 5 in cand and 12 in cand

    # Limit to 3 runs
    reduced, one_minimal = ddmin(stream, fails, max_runs=3)
    assert one_minimal is False
    assert len(reduced) <= len(stream)


def test_ddmin_budget_stop_max_seconds():
    """Verify budget stop on max_seconds returns one_minimal=False."""
    stream = list(range(20))

    def slow_fails(cand: List[int]) -> bool:
        time.sleep(0.01)
        return 2 in cand and 8 in cand

    # Tiny time budget of 0.015 seconds
    reduced, one_minimal = ddmin(stream, slow_fails, max_seconds=0.015)
    assert one_minimal is False


def test_ddmin_determinism():
    """Verify ddmin is strictly deterministic across repeated runs."""
    stream = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]

    def fails(cand: List[int]) -> bool:
        return 20 in cand and 80 in cand

    r1, m1 = ddmin(stream, fails)
    r2, m2 = ddmin(stream, fails)
    assert r1 == r2
    assert m1 == m2 == True


def test_ddmin_on_step_strictly_decreasing():
    """Verify on_step callback receives intermediate streams with strictly decreasing lengths."""
    stream = list(range(40))

    def fails(cand: List[int]) -> bool:
        return 7 in cand and 23 in cand and 35 in cand

    lengths = []
    reduced, one_minimal = ddmin(stream, fails, on_step=lambda s: lengths.append(len(s)))

    assert one_minimal is True
    assert len(lengths) > 0
    # Every accepted step must be strictly smaller than the previous
    prev_len = len(stream)
    for l in lengths:
        assert l < prev_len, f"Reduction step did not strictly decrease: {l} not < {prev_len}"
        prev_len = l
    assert lengths[-1] == len(reduced)


def test_ddmin_already_minimal():
    """Verify ddmin handles short streams (len < 2) immediately."""
    assert ddmin([1], lambda s: True) == ([1], True)
    assert ddmin([], lambda s: True) == ([], True)


def test_explain_templates_coverage():
    """Verify explanation generator produces expected text for all rules R0 through R10."""
    rules = ["R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10"]
    for r in rules:
        exp = explain_failure(
            rule=r,
            expected={"status": "duplicate", "summary": {}},
            observed={"status": "applied", "summary": {}},
            minimal_stream=[{"event_id": "evt_test", "type": "payment.captured", "amount_paise": 50000}],
        )
        assert r in exp
        assert len(exp) > 20


def test_format_rupees_helpers():
    """Verify rupees formatting helpers."""
    assert format_rupees(50000) == "Rs 500"
    assert format_rupees(50050) == "Rs 500.50"
    assert format_rupees(100000) == "Rs 1,000"
    assert format_rupees_and_paise(50000) == "Rs 500 (50,000 paise)"
