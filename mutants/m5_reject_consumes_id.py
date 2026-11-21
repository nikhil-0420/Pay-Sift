# HAND-WRITTEN MUTANT
# Mutant m5: rejected events marked processed (violates Rule R8, Invariant I2_idempotency)
"""Mutant m5: records rejected event_ids into applied dedupe table."""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from typing import Any, Dict, Optional


def _verify_sig(raw_body: bytes, signature: str, secret: str) -> bool:
    if not isinstance(raw_body, (bytes, bytearray)):
        return False
    if not isinstance(signature, str) or not isinstance(secret, str):
        return False
    if not signature.isascii() or len(signature) != 64:
        return False
    for ch in signature:
        if ch not in "0123456789abcdef":
            return False

    expected = hmac.new(secret.encode("utf-8"), bytes(raw_body), hashlib.sha256).hexdigest().lower()
    return hmac.compare_digest(signature.encode("ascii"), expected.encode("ascii"))


def _mark_rejected_id_processed(db_path: str, event_id: str) -> None:
    """BUG (m5): Marks rejected event_id as processed in dedupe table."""
    try:
        with sqlite3.connect(db_path, timeout=5.0) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS _paysift_applied_events (event_id TEXT PRIMARY KEY)")
            conn.execute("INSERT OR IGNORE INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
            conn.commit()
    except Exception:
        pass


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    # Extract event_id if present for bug demonstration
    extracted_event_id: Optional[str] = None
    try:
        parsed = json.loads(bytes(raw_body).decode("utf-8"))
        if isinstance(parsed, dict) and isinstance(parsed.get("event_id"), str):
            extracted_event_id = parsed["event_id"]
    except Exception:
        pass

    if not _verify_sig(raw_body, signature, secret):
        if extracted_event_id:
            _mark_rejected_id_processed(db_path, extracted_event_id)
        return {"status": "rejected", "reason": "Invalid signature (R1)"}

    try:
        text = bytes(raw_body).decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "rejected", "reason": "Payload is not valid UTF-8 (R2)"}

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"status": "rejected", "reason": "Payload is not valid JSON (R2)"}

    if not isinstance(data, dict):
        return {"status": "rejected", "reason": "Payload must be a JSON object (R2)"}

    if "event_id" not in data:
        return {"status": "rejected", "reason": "Missing event_id (R2)"}
    event_id = data["event_id"]
    if not isinstance(event_id, str) or len(event_id) == 0 or len(event_id) > 64:
        return {"status": "rejected", "reason": "Invalid event_id (R2)"}

    if "type" not in data:
        _mark_rejected_id_processed(db_path, event_id)
        return {"status": "rejected", "reason": "Missing type (R2)"}
    ev_type = data["type"]
    if ev_type not in ("payment.captured", "refund.processed"):
        _mark_rejected_id_processed(db_path, event_id)
        return {"status": "rejected", "reason": f"Invalid type '{ev_type}' (R2)"}

    if "payment_id" not in data:
        _mark_rejected_id_processed(db_path, event_id)
        return {"status": "rejected", "reason": "Missing payment_id (R2)"}
    payment_id = data["payment_id"]
    if not isinstance(payment_id, str) or len(payment_id) == 0 or len(payment_id) > 64:
        _mark_rejected_id_processed(db_path, event_id)
        return {"status": "rejected", "reason": "Invalid payment_id (R2)"}

    if "amount_paise" not in data:
        _mark_rejected_id_processed(db_path, event_id)
        return {"status": "rejected", "reason": "Missing amount_paise (R2)"}
    amount = data["amount_paise"]
    if isinstance(amount, bool) or not isinstance(amount, int) or isinstance(amount, float):
        _mark_rejected_id_processed(db_path, event_id)
        return {"status": "rejected", "reason": "amount_paise must be integer (R2)"}
    if amount < 1 or amount > 10**12:
        _mark_rejected_id_processed(db_path, event_id)
        return {"status": "rejected", "reason": "amount_paise out of range [1, 10^12] (R2)"}

    if ev_type == "refund.processed":
        if "refund_id" not in data:
            _mark_rejected_id_processed(db_path, event_id)
            return {"status": "rejected", "reason": "Missing refund_id for refund (R2)"}
        refund_id = data["refund_id"]
        if not isinstance(refund_id, str) or len(refund_id) == 0:
            _mark_rejected_id_processed(db_path, event_id)
            return {"status": "rejected", "reason": "Invalid refund_id (R2)"}

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.isolation_level = None
        cur = conn.cursor()

        cur.execute("BEGIN IMMEDIATE")
        cur.execute("CREATE TABLE IF NOT EXISTS _paysift_applied_events (event_id TEXT PRIMARY KEY)")

        cur.execute("SELECT 1 FROM _paysift_applied_events WHERE event_id = ?", (event_id,))
        if cur.fetchone() is not None:
            cur.execute("ROLLBACK")
            return {"status": "duplicate", "reason": "Event already applied (R3)"}

        if ev_type == "payment.captured":
            cur.execute("SELECT 1 FROM payments WHERE payment_id = ?", (payment_id,))
            if cur.fetchone() is not None:
                # BUG (m5): Records rejected event_id into applied table
                cur.execute("INSERT OR IGNORE INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
                cur.execute("COMMIT")
                return {"status": "rejected", "reason": "Payment already captured (R4)"}

            cur.execute(
                "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                (payment_id, amount),
            )
            cur.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                (payment_id, amount, event_id),
            )
            cur.execute("INSERT INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
            cur.execute("COMMIT")
            return {"status": "applied", "reason": "Payment captured successfully"}

        else:
            cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
            row = cur.fetchone()
            if row is None:
                # BUG (m5): Records rejected event_id into applied table
                cur.execute("INSERT OR IGNORE INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
                cur.execute("COMMIT")
                return {"status": "rejected", "reason": "Payment does not exist (R5)"}

            captured_paise, refunded_paise = row
            if refunded_paise + amount > captured_paise:
                # BUG (m5): Records rejected event_id into applied table
                cur.execute("INSERT OR IGNORE INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
                cur.execute("COMMIT")
                return {"status": "rejected", "reason": "Refund exceeds captured balance (R6)"}

            cur.execute(
                "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                (amount, payment_id),
            )
            cur.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                (payment_id, amount, event_id),
            )
            cur.execute("INSERT INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
            cur.execute("COMMIT")
            return {"status": "applied", "reason": "Refund processed successfully"}

    except Exception as exc:
        if conn is not None:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        return {"status": "rejected", "reason": f"Internal database error: {exc}"}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
