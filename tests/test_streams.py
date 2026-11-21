"""Tests for runner/streams.py deterministic stream generator."""

from __future__ import annotations

import pytest

from runner.streams import generate_stream, render_stream


def test_stream_determinism():
    """Verify that identical seeds produce identical stream bytes and tags."""
    for seed in [0, 5, 17, 42, 99]:
        s1 = generate_stream(seed)
        s2 = generate_stream(seed)
        assert s1 == s2, f"Stream for seed {seed} was not deterministic"


def test_family_coverage_and_bounds():
    """Verify all 10 families (seeds 0-9) generate 3-40 valid steps."""
    for seed in range(10):
        steps = generate_stream(seed)
        assert 3 <= len(steps) <= 40, f"Seed {seed} step count {len(steps)} out of [3, 40] bounds"
        for st in steps:
            assert "raw_body_b64" in st and len(st["raw_body_b64"]) > 0
            assert "signature" in st
            assert "tag" in st


def test_render_stream():
    """Verify render_stream generates human-readable text."""
    steps = generate_stream(0)
    text = render_stream(steps)
    assert f"Stream contains {len(steps)} steps:" in text
    assert "tag=" in text
