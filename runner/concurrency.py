"""PaySift Concurrency Testing Harness (R10 Verification).

Evaluates Scenario A (duplicate capture race) and Scenario B (concurrent refund bound race)
using multiprocessing with the spawn context and barrier synchronization.
"""

from __future__ import annotations

import importlib.util
import json
import multiprocessing as mp
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from contract.events import canonical_bytes, sign


def _init_db(db_path: Path, schema_path: Path) -> None:
    schema_sql = schema_path.read_text(encoding="utf-8")
    with sqlite3.connect(db_path, timeout=5.0) as conn:
        conn.executescript(schema_sql)
        conn.commit()


def _worker_deliver_task(
    candidate_file_str: str,
    db_path_str: str,
    raw_body: bytes,
    signature: str,
    secret: str,
    barrier: Any,
    result_queue: Any,
) -> None:
    """Worker task executing in separate process released by barrier."""
    # Wait for all processes to be ready
    try:
        barrier.wait(timeout=10.0)
    except Exception as exc:
        result_queue.put({"status": "barrier_error", "error": str(exc)})
        return

    # Load candidate dynamically
    cand_path = Path(candidate_file_str).resolve()
    spec = importlib.util.spec_from_file_location("candidate_handler", cand_path)
    if spec is None or spec.loader is None:
        result_queue.put({"status": "import_error", "error": "Cannot load candidate"})
        return
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        fn = getattr(mod, "handle_event")
    except Exception as exc:
        result_queue.put({"status": "exec_error", "error": str(exc)})
        return

    # Execute handle_event
    try:
        resp = fn(db_path_str, raw_body, signature, secret)
        result_queue.put({"status": "success", "response": resp})
    except Exception as exc:
        # Check for locked database
        err_msg = str(exc)
        if "locked" in err_msg.lower() or "busy" in err_msg.lower():
            result_queue.put({"status": "warning", "warning": err_msg})
        else:
            result_queue.put({"status": "exception", "error": err_msg})


def run_scenario_a(
    candidate_path: Path,
    trials: int = 50,
    processes: int = 8,
    secret: str = "paysift_secret_key_v1_offline_test",
) -> Dict[str, Any]:
    """Execute Scenario A: 8 concurrent deliveries of the same capture event.

    Expects: exactly 1 capture ledger entry, and captured_paise == amount.
    """
    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / "contract" / "schema.sql"

    # Define capture event
    amount_paise = 50000  # ₹500
    payment_id = "pay_conc_a"
    event_id = "evt_conc_a_dup"
    event_dict = {
        "event_id": event_id,
        "type": "payment.captured",
        "payment_id": payment_id,
        "amount_paise": amount_paise,
    }
    raw_body = canonical_bytes(event_dict)
    signature = sign(raw_body, secret)

    failed_trials = 0
    warning_count = 0
    first_evidence: Optional[Dict[str, Any]] = None

    ctx = mp.get_context("spawn")

    for _ in range(trials):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
            db_path = Path(tmp_dir_str) / "harness.db"
            _init_db(db_path, schema_path)

            barrier = ctx.Barrier(processes)
            queue = ctx.Queue()

            procs = []
            for _ in range(processes):
                p = ctx.Process(
                    target=_worker_deliver_task,
                    args=(
                        str(candidate_path),
                        str(db_path),
                        raw_body,
                        signature,
                        secret,
                        barrier,
                        queue,
                    ),
                )
                p.start()
                procs.append(p)

            for p in procs:
                p.join(timeout=10.0)
                if p.is_alive():
                    p.kill()

            # Inspect queue results for warnings
            while not queue.empty():
                item = queue.get()
                if item.get("status") == "warning":
                    warning_count += 1
                elif isinstance(item.get("response"), dict):
                    resp = item["response"]
                    if "locked" in str(resp.get("reason", "")).lower():
                        warning_count += 1

            # Inspect final DB state
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*), COALESCE(SUM(amount_paise), 0) FROM ledger WHERE kind = 'capture'")
                cap_count, cap_sum = cur.fetchone()

                cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                p_row = cur.fetchone()
                captured_paise = p_row[0] if p_row else 0

                cur.execute("SELECT entry_id, payment_id, kind, amount_paise, event_id FROM ledger")
                ledger_rows = [
                    {"entry_id": r[0], "payment_id": r[1], "kind": r[2], "amount_paise": r[3], "event_id": r[4]}
                    for r in cur.fetchall()
                ]

            # Violation: more than 1 capture entry or captured_paise != amount
            is_fail = (cap_count != 1) or (captured_paise != amount_paise)
            if is_fail:
                failed_trials += 1
                if first_evidence is None:
                    first_evidence = {
                        "scenario": "scenario_A",
                        "expected": {"captures_count": 1, "captured_paise": amount_paise},
                        "observed": {
                            "captures_count": cap_count,
                            "captured_paise": captured_paise,
                            "ledger": ledger_rows,
                        },
                    }

    return {
        "trials": trials,
        "failed": failed_trials,
        "warnings": warning_count,
        "evidence": first_evidence,
    }


def run_scenario_b(
    candidate_path: Path,
    trials: int = 50,
    processes: int = 8,
    secret: str = "paysift_secret_key_v1_offline_test",
) -> Dict[str, Any]:
    """Execute Scenario B: 4 deliver refund X (₹600) and 4 deliver refund Y (₹600) against ₹1000 balance.

    Expects: exactly 1 refund applied, refunded_paise == 60000, 1 refund ledger entry.
    """
    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / "contract" / "schema.sql"

    payment_id = "pay_conc_b"
    cap_amount = 100000  # ₹1,000

    # Refund X
    ref_x_dict = {
        "event_id": "evt_ref_x",
        "type": "refund.processed",
        "payment_id": payment_id,
        "amount_paise": 60000,
        "refund_id": "ref_x",
    }
    raw_body_x = canonical_bytes(ref_x_dict)
    sig_x = sign(raw_body_x, secret)

    # Refund Y
    ref_y_dict = {
        "event_id": "evt_ref_y",
        "type": "refund.processed",
        "payment_id": payment_id,
        "amount_paise": 60000,
        "refund_id": "ref_y",
    }
    raw_body_y = canonical_bytes(ref_y_dict)
    sig_y = sign(raw_body_y, secret)

    failed_trials = 0
    warning_count = 0
    first_evidence: Optional[Dict[str, Any]] = None

    ctx = mp.get_context("spawn")

    for _ in range(trials):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
            db_path = Path(tmp_dir_str) / "harness.db"
            _init_db(db_path, schema_path)

            # Pre-apply capture of ₹1,000
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                conn.execute(
                    "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                    (payment_id, cap_amount),
                )
                conn.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                    (payment_id, cap_amount, "evt_cap_init"),
                )
                # Also record in dedupe table if reference table is used
                try:
                    conn.execute("CREATE TABLE IF NOT EXISTS _paysift_applied_events (event_id TEXT PRIMARY KEY)")
                    conn.execute("INSERT OR IGNORE INTO _paysift_applied_events (event_id) VALUES (?)", ("evt_cap_init",))
                except Exception:
                    pass
                conn.commit()

            barrier = ctx.Barrier(processes)
            queue = ctx.Queue()

            procs = []
            half = processes // 2
            # 4 deliver X, 4 deliver Y
            for i in range(processes):
                rb = raw_body_x if i < half else raw_body_y
                sg = sig_x if i < half else sig_y
                p = ctx.Process(
                    target=_worker_deliver_task,
                    args=(
                        str(candidate_path),
                        str(db_path),
                        rb,
                        sg,
                        secret,
                        barrier,
                        queue,
                    ),
                )
                p.start()
                procs.append(p)

            for p in procs:
                p.join(timeout=10.0)
                if p.is_alive():
                    p.kill()

            while not queue.empty():
                item = queue.get()
                if item.get("status") == "warning":
                    warning_count += 1
                elif isinstance(item.get("response"), dict):
                    resp = item["response"]
                    if "locked" in str(resp.get("reason", "")).lower():
                        warning_count += 1

            # Inspect final DB state
            with sqlite3.connect(db_path, timeout=5.0) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*), COALESCE(SUM(amount_paise), 0) FROM ledger WHERE kind = 'refund'")
                ref_count, ref_sum = cur.fetchone()

                cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                p_row = cur.fetchone()
                refunded_paise = p_row[1] if p_row else 0

                cur.execute("SELECT entry_id, payment_id, kind, amount_paise, event_id FROM ledger")
                ledger_rows = [
                    {"entry_id": r[0], "payment_id": r[1], "kind": r[2], "amount_paise": r[3], "event_id": r[4]}
                    for r in cur.fetchall()
                ]

            # Violation: more than 1 refund entry or refunded_paise != 60000 (exceeds bounds)
            is_fail = (ref_count != 1) or (refunded_paise != 60000)
            if is_fail:
                failed_trials += 1
                if first_evidence is None:
                    first_evidence = {
                        "scenario": "scenario_B",
                        "expected": {"refunds_count": 1, "refunded_paise": 60000},
                        "observed": {
                            "refunds_count": ref_count,
                            "refunded_paise": refunded_paise,
                            "ledger": ledger_rows,
                        },
                    }

    return {
        "trials": trials,
        "failed": failed_trials,
        "warnings": warning_count,
        "evidence": first_evidence,
    }


def run_concurrency_suite(
    candidate_path: Path,
    trials: int = 50,
    processes: int = 8,
) -> Dict[str, Any]:
    """Execute complete concurrency evaluation (Scenarios A and B)."""
    cand = Path(candidate_path).resolve()
    sc_a = run_scenario_a(cand, trials=trials, processes=processes)
    sc_b = run_scenario_b(cand, trials=trials, processes=processes)
    return {
        "scenario_A": sc_a,
        "scenario_B": sc_b,
    }
