"""Unit tests for Phase P8 Pilot Runner, Packets, and Reporting."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

import cli
from contract.validate_run import validate as validate_run_dict
from pilot.packets import RULE_TEXTS, classify_failure, format_failure_packet, write_failure_packet
from pilot.runner import check_sandbox_precondition, generate_pilot_report, run_pilot


def test_sandbox_precondition_missing_gate4():
    """check_sandbox_precondition must return False when runs/GATE4_PASSED does not exist."""
    ok, reason = check_sandbox_precondition()
    assert ok is False
    assert "runs/GATE4_PASSED does not exist" in reason or "Docker" in reason


def test_classify_failure():
    """Verify agent-proposed classification adheres to plan section 11 rules."""
    cand_a = {"condition": "A", "model": "strong_a"}
    fail_r3 = {"rule": "R3", "invariant": "I2_idempotency"}
    class_a = classify_failure(cand_a, fail_r3)
    assert class_a["label"] == "a"
    assert class_a["by"] == "agent-proposed"
    assert "R3" in class_a["note"]

    cand_b = {"condition": "B", "model": "strong_b"}
    fail_r2 = {"rule": "R2", "invariant": "I4_bounds"}
    class_b = classify_failure(cand_b, fail_r2)
    assert class_b["label"] == "d"
    assert class_b["by"] == "agent-proposed"
    assert "Condition B" in class_b["note"]
    assert "illustrative" in class_b["note"]


def test_format_failure_packet(tmp_path):
    """Verify failure packet formatting includes all required sections."""
    mock_run = {
        "run_id": "test_run_123",
        "spec_sha": "289fa48f542ffcf36eb6f27ba4fd513c97312f8c987396b8a2e98e1cdaea230a",
        "candidate": {
            "id": "cand_sample_1",
            "model": "gpt-4o",
            "condition": "A",
            "sample": 1,
            "sha256": "abcdef123456",
            "source": "live",
            "label": "Candidate cand_sample_1",
        },
        "failures": [
            {
                "invariant": "I2_idempotency",
                "rule": "R3",
                "mode": "normal",
                "seed": 0,
                "stream": [
                    {"summary": "payment.captured s0_cap_0 (Rs 100.00)", "tag": "cap1"},
                    {"summary": "payment.captured s0_cap_0 (Rs 100.00)", "tag": "cap1_dup"},
                ],
                "explanation": "Event delivered twice resulting in double capture balance. Rule R3.",
                "observed_state": {"balance": 200},
                "expected_state": {"balance": 100},
                "repro": {"runs": 10, "reproduced": 10},
                "one_minimal": True,
            }
        ],
    }

    dummy_code = "def handle_event(db, raw, sig, sec):\n    return {'status': 'applied'}\n"
    dummy_py = tmp_path / "cand.py"
    dummy_py.write_text(dummy_code, encoding="utf-8")

    packet_md = format_failure_packet(
        run_dict=mock_run,
        failure_index=0,
        candidate_code=dummy_code,
        candidate_path_str=str(dummy_py),
        run_path_str="runs/test_run_123.json",
    )

    assert "# Failure Packet: `cand_sample_1` (Failure #0)" in packet_md
    assert "Rule R3" in packet_md
    assert "Event Idempotency" in packet_md
    assert "payment.captured s0_cap_0 (Rs 100.00)" in packet_md
    assert "Proposed Class:** `(a)`" in packet_md
    assert "agent-proposed" in packet_md
    assert "10 of 10 runs" in packet_md


def test_write_failure_packet(tmp_path):
    """Verify write_failure_packet writes packet file to destination."""
    mock_run = {
        "run_id": "test_run_456",
        "spec_sha": "test_spec_sha",
        "candidate": {
            "id": "cand_b_2",
            "model": "claude-3-5",
            "condition": "B",
            "sample": 2,
            "sha256": "1234567890ab",
            "source": "live",
            "label": "Candidate cand_b_2",
        },
        "failures": [
            {
                "invariant": "I4_bounds",
                "rule": "R6",
                "mode": "normal",
                "seed": 1,
                "stream": [{"summary": "refund.processed (Rs 500.00)"}],
                "explanation": "Refund exceeded captured balance.",
            }
        ],
    }
    dummy_py = tmp_path / "handler.py"
    dummy_py.write_text("print('test')", encoding="utf-8")

    out_file = write_failure_packet(
        mock_run,
        0,
        dummy_py,
        output_dir=tmp_path / "packets",
        run_path=tmp_path / "runs" / "test_run_456.json",
    )
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert "cand_b_2" in content
    assert "Rule R6" in content
    assert "Proposed Class:** `(d)`" in content


def test_generate_pilot_report_blocked():
    """Verify generate_pilot_report produces valid report structure when blocked."""
    report = generate_pilot_report(
        blocked=True,
        block_reason="runs/GATE4_PASSED does not exist",
        candidates=[],
        runs=[],
    )
    assert "# PaySift Pilot Verification Report" in report
    assert "PILOT BLOCKED: sandbox gate not passed" in report
    assert "Draft Headline:" in report
    assert "Condition A: Full Specification Performance" in report
    assert "Condition B: Casual Prompt (Illustrative Only)" in report
    assert "Outcome Table Assessment" in report or "Plan Outcome Assessment" in report
    assert "Demo Candidate Proposals (Marked HUMAN DECISION)" in report
    assert "m1_no_dedupe" in report
    assert "DRAFT-FROZEN" in report


def test_real_example_json_validity():
    """Verify runs/real_example.json exists, is valid against schema, and has correct label."""
    p = Path("runs/real_example.json")
    assert p.exists(), "runs/real_example.json must exist"
    data = json.loads(p.read_text(encoding="utf-8"))
    errs = validate_run_dict(data)
    assert errs == [], f"Validation errors in real_example.json: {errs}"
    cand = data.get("candidate", {})
    assert cand.get("label") == "hand-written mutant, not model output"
    assert cand.get("source") == "mutant"

    # Verify runs/sample.json was not overwritten and remains valid
    sample_p = Path("runs/sample.json")
    assert sample_p.exists()
    sample_data = json.loads(sample_p.read_text(encoding="utf-8"))
    sample_errs = validate_run_dict(sample_data)
    assert sample_errs == []
    assert sample_data.get("run_id") != data.get("run_id")


def test_cli_pilot_execution():
    """Verify 'python cli.py pilot' runs safely and returns code 1 when precondition fails."""
    ret = cli.main(["pilot"])
    assert ret == 1
    report_file = Path("pilot/PILOT_REPORT.md")
    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "PILOT BLOCKED: sandbox gate not passed" in content
