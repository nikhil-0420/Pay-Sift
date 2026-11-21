"""Unit tests for Static HTML Report generation (report/generate.py)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from report.generate import (
    build_reports,
    generate_index_html,
    generate_kill_matrix_html,
    generate_run_html,
    generate_scenarios_html,
)


def test_build_reports_execution(tmp_path):
    """Verify build_reports generates index.html, kill_matrix.html, scenarios.html, and run pages."""
    runs_dir = Path("runs")
    out_dir = tmp_path / "out"

    files = build_reports(runs_dir=runs_dir, out_dir=out_dir)
    assert len(files) >= 4

    index_p = out_dir / "index.html"
    assert index_p.exists()
    index_html = index_p.read_text(encoding="utf-8")
    assert "PaySift Verification Dashboard" in index_html
    assert "kill_matrix.html" in index_html
    assert "scenarios.html" in index_html
    # Ensure no external CDN or fonts
    assert "http://" not in index_html and "https://" not in index_html

    km_p = out_dir / "kill_matrix.html"
    assert km_p.exists()
    km_html = km_p.read_text(encoding="utf-8")
    assert "Mutant Kill Matrix" in km_html
    assert "HAND-WRITTEN MUTANT" in km_html

    sc_p = out_dir / "scenarios.html"
    assert sc_p.exists()
    sc_html = sc_p.read_text(encoding="utf-8")
    assert "Break-it Scenarios (Static Replay)" in sc_html
    assert "Financial Breach Detected" in sc_html


def test_run_html_contains_badge_and_shrink_history():
    """Verify run page renders correct badge, mutant label, and shrink history."""
    run_p = Path("runs/real_example.json")
    run_dict = json.loads(run_p.read_text(encoding="utf-8"))

    html_content = generate_run_html(run_dict)
    assert "HAND-WRITTEN MUTANT" in html_content
    assert "Invariant Scorecard" in html_content
    assert "Rule R3" in html_content
    assert "Shrinker History & Counterexample Timeline" in html_content
    assert "10x Repro" in html_content
