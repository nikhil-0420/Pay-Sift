"""Tests for PaySift Kill Matrix and Mutant evaluation (Gate 3)."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from contract.validate_run import validate_kill_matrix
from runner.kill_matrix import run_kill_matrix


@pytest.fixture(scope="module")
def kill_matrix_result(tmp_path_factory) -> dict:
    """Load or run kill matrix for testing."""
    root = Path(__file__).resolve().parent.parent
    km_json = root / "runs" / "kill_matrix.json"
    km_md = root / "runs" / "kill_matrix.md"

    if km_json.is_file() and km_md.is_file():
        km = json.loads(km_json.read_text(encoding="utf-8"))
    else:
        temp_dir = tmp_path_factory.mktemp("km_test")
        km_json = temp_dir / "kill_matrix.json"
        km_md = temp_dir / "kill_matrix.md"
        km = run_kill_matrix(
            seed_range=(0, 99),
            output_json_path=km_json,
            output_md_path=km_md,
            print_table=False,
        )

    km["_json_path"] = km_json
    km["_md_path"] = km_md
    return km


def test_kill_matrix_schema_validity(kill_matrix_result: dict):
    """Assert kill matrix JSON matches contract schema."""
    errors = validate_kill_matrix(kill_matrix_result)
    assert not errors, f"Kill matrix schema validation errors: {errors}"
    assert "assertion_errors" not in kill_matrix_result, f"Assertions failed: {kill_matrix_result.get('assertion_errors')}"


def test_reference_clean(kill_matrix_result: dict):
    """Assert reference handler produces zero failures across all 100 seeds."""
    ref_rows = [r for r in kill_matrix_result["rows"] if r["id"] == "ref"]
    assert len(ref_rows) == 1
    ref = ref_rows[0]
    assert ref["rules_hit"] == []
    assert ref["killed"] is False
    for inv, res in ref["results"].items():
        norm = res.get("normal", res)
        assert norm["failed"] == 0
        assert norm["passed"] == 100


def test_all_implemented_mutants_killed_with_intended_rule(kill_matrix_result: dict):
    """Assert each implemented mutant is killed and hits its must_fail_rule."""
    expected_rules = {
        "m1": "R3",
        "m2": "R7",
        "m3": "R6",
        "m4": "R2",
        "m5": "R8",
        "m6": "R1",
        "m7": "R9",
        "m8": "R10",
        "m9": "R10",
        "x1": "R2",
        "x2": "R2",
        "x3": "R0",
        "x4": "R1",
    }
    rows_by_id = {r["id"]: r for r in kill_matrix_result["rows"]}

    for mid, exp_rule in expected_rules.items():
        assert mid in rows_by_id, f"Mutant {mid} missing from kill matrix rows"
        row = rows_by_id[mid]
        assert row["killed"] is True, f"Mutant {mid} was not killed!"
        assert exp_rule in row["rules_hit"], (
            f"Mutant {mid} did not hit expected rule '{exp_rule}'. Hit: {row['rules_hit']}"
        )


def test_x4_family_8_sensitivity(kill_matrix_result: dict):
    """Assert mutant x4 is sensitive exclusively to non-canonical valid bodies (Family 8)."""
    rows_by_id = {r["id"]: r for r in kill_matrix_result["rows"]}
    assert "x4" in rows_by_id
    x4_row = rows_by_id["x4"]
    assert x4_row["killed"] is True
    assert "R1" in x4_row["rules_hit"]
    # 10 failures out of 100 seeds (exactly seeds 8, 18, ..., 98)
    norm = x4_row["results"]["I1_signature"].get("normal", x4_row["results"]["I1_signature"])
    assert norm["failed"] == 10
    assert norm["passed"] == 90


def test_kill_matrix_markdown_artifact_created(kill_matrix_result: dict):
    """Assert kill matrix Markdown table artifact is generated with header and table rows."""
    md_path = kill_matrix_result["_md_path"]
    assert md_path.is_file()
    text = md_path.read_text(encoding="utf-8")
    assert "# PaySift Kill Matrix Report" in text
    assert "| `ref` |" in text
    assert "| `m1` |" in text
    assert "| `x4` |" in text
