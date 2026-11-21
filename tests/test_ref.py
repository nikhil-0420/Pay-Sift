"""Tests for reference payment webhook handler (ref/handler_ref.py)."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import pytest

from contract.events import TEST_SECRET, decode_step
from ref.handler_ref import handle_event


@pytest.fixture
def empty_db(tmp_path: Path):
    """Create initialized database with schema."""
    schema_sql = Path("E:/PaySift/contract/schema.sql").read_text(encoding="utf-8")
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(schema_sql)
    conn.close()
    return str(db_file)


def test_ref_handler_vs_cases(tmp_path: Path):
    """Verify reference handler matches expected statuses and final state for all cases.jsonl."""
    cases_file = Path("E:/PaySift/contract/cases.jsonl")
    cases = [json.loads(line) for line in cases_file.read_text(encoding="utf-8").splitlines()]
    schema_sql = Path("E:/PaySift/contract/schema.sql").read_text(encoding="utf-8")

    for c in cases:
        cid = c["id"]
        db_file = tmp_path / f"{cid}.db"
        conn = sqlite3.connect(str(db_file))
        conn.executescript(schema_sql)
        conn.close()

        for sidx, (st, exp_s) in enumerate(zip(c["steps"], c["expected"]["steps"])):
            raw, sig, _ = decode_step(st)
            resp = handle_event(str(db_file), raw, sig, TEST_SECRET)
            assert resp.get("status") == exp_s["status"], f"Case {cid} step {sidx} status mismatch: expected {exp_s['status']}, got {resp.get('status')}"

        # Check final payments state in DB
        conn = sqlite3.connect(str(db_file))
        cur = conn.cursor()
        cur.execute("SELECT payment_id, captured_paise, refunded_paise FROM payments")
        act_p = {row[0]: (row[1], row[2]) for row in cur.fetchall()}
        conn.close()

        exp_p = {p["payment_id"]: (p["captured_paise"], p["refunded_paise"]) for p in c["expected"]["final_state"]["payments"]}
        assert act_p == exp_p, f"Case {cid} final DB state mismatch: expected {exp_p}, got {act_p}"


def test_ref_handler_vs_worked_examples(tmp_path: Path):
    """Verify reference handler matches expected statuses for all worked_examples.jsonl."""
    we_file = Path("E:/PaySift/contract/worked_examples.jsonl")
    examples = [json.loads(line) for line in we_file.read_text(encoding="utf-8").splitlines()]
    schema_sql = Path("E:/PaySift/contract/schema.sql").read_text(encoding="utf-8")

    for ex in examples:
        eid = ex["id"]
        db_file = tmp_path / f"{eid}.db"
        conn = sqlite3.connect(str(db_file))
        conn.executescript(schema_sql)
        conn.close()

        for sidx, (st, exp_s) in enumerate(zip(ex["steps"], ex["expected"]["steps"])):
            raw, sig, _ = decode_step(st)
            resp = handle_event(str(db_file), raw, sig, TEST_SECRET)
            assert resp.get("status") == exp_s["status"], f"Example {eid} step {sidx} status mismatch: expected {exp_s['status']}, got {resp.get('status')}"
