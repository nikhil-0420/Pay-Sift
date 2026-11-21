import sqlite3
import hmac
import hashlib
import json
from typing import Dict, Any
from contextlib import contextmanager

@contextmanager
def get_db_cursor(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn.cursor()
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, Any]:
    expected_sig = hmac.new(
        secret.encode('utf-8'),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        return {"status": "error", "reason": "invalid_signature"}

    try:
        event = json.loads(raw_body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "error", "reason": "invalid_json"}

    event_type = event.get("type")
    payment_id = event.get("payment_id")
    event_id = event.get("event_id")
    amount_paise = event.get("amount_paise")

    if not all([event_type, payment_id, event_id, isinstance(amount_paise, int)]):
        return {"status": "error", "reason": "missing_fields"}

    with get_db_cursor(db_path) as cursor:
        cursor.execute("SELECT event_id FROM ledger WHERE event_id = ?", (event_id,))
        if cursor.fetchone():
            return {"status": "ignored", "reason": "duplicate_event"}

        if event_type == "payment.captured":
            cursor.execute(
                "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0) "
                "ON CONFLICT(payment_id) DO UPDATE SET captured_paise = captured_paise + ?",
                (payment_id, amount_paise, amount_paise)
            )
            cursor.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                (payment_id, amount_paise, event_id)
            )
            return {"status": "success", "reason": "payment_captured"}

        elif event_type == "refund.processed":
            cursor.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
            row = cursor.fetchone()
            if not row:
                return {"status": "error", "reason": "payment_not_found"}

            captured, refunded = row
            if refunded + amount_paise > captured:
                return {"status": "error", "reason": "refund_exceeds_capture"}

            cursor.execute(
                "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                (amount_paise, payment_id)
            )
            cursor.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                (payment_id, amount_paise, event_id)
            )
            return {"status": "success", "reason": "refund_processed"}

        else:
            return {"status": "ignored", "reason": "unknown_event_type"}
