import sqlite3
import hmac
import hashlib
import json
from typing import Dict, Any
from contextlib import contextmanager

@contextmanager
def get_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, Any]:
    expected_signature = hmac.new(
        secret.encode('utf-8') if isinstance(secret, str) else secret,
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        return {"status": "error", "reason": "invalid_signature"}

    try:
        event = json.loads(raw_body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "error", "reason": "invalid_json"}

    event_type = event.get("type")
    payment_id = event.get("payment_id")
    amount_paise = event.get("amount_paise")
    event_id = event.get("event_id")

    if not event_type or not payment_id or amount_paise is None or not event_id:
        return {"status": "error", "reason": "missing_fields"}

    try:
        with get_db(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT 1 FROM ledger WHERE event_id = ?", (event_id,))
            if cursor.fetchone():
                return {"status": "ignored", "reason": "duplicate_event"}

            if event_type == "payment.captured":
                cursor.execute(
                    "INSERT OR IGNORE INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, 0, 0)",
                    (payment_id,)
                )
                cursor.execute(
                    "UPDATE payments SET captured_paise = captured_paise + ? WHERE payment_id = ?",
                    (amount_paise, payment_id)
                )
                cursor.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )

            elif event_type == "refund.processed":
                cursor.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                row = cursor.fetchone()
                if not row:
                    return {"status": "error", "reason": "payment_not_found"}

                captured_paise, refunded_paise = row
                if refunded_paise + amount_paise > captured_paise:
                    return {"status": "error", "reason": "refund_exceeds_captured"}

                cursor.execute(
                    "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                    (amount_paise, payment_id)
                )
                cursor.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )

            else:
                return {"status": "ignored", "reason": "unknown_event_type"}

    except Exception as e:
        return {"status": "error", "reason": str(e)}

    return {"status": "success", "reason": "processed"}
