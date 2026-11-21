import sqlite3
import hmac
import hashlib
import json
from typing import Dict, Any
from contextlib import contextmanager

@contextmanager
def get_db_cursor(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, Any]:
    expected_sig = hmac.new(
        secret.encode('utf-8') if isinstance(secret, str) else secret,
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, signature):
        return {"status": "error", "reason": "invalid_signature"}

    try:
        data = json.loads(raw_body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"status": "error", "reason": "invalid_json"}

    event_type = data.get("type")
    payment_id = data.get("payment_id")
    event_id = data.get("event_id")
    amount_paise = data.get("amount_paise")

    if not all([event_type, payment_id, event_id, isinstance(amount_paise, int)]):
        return {"status": "error", "reason": "missing_fields"}

    if event_type not in ("payment.captured", "refund.processed"):
        return {"status": "ignored", "reason": "unsupported_event_type"}

    try:
        with get_db_cursor(db_path) as cur:
            cur.execute(
                "SELECT 1 FROM ledger WHERE event_id = ? LIMIT 1",
                (event_id,)
            )
            if cur.fetchone():
                return {"status": "ignored", "reason": "duplicate_event"}

            if event_type == "payment.captured":
                cur.execute(
                    "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0) "
                    "ON CONFLICT(payment_id) DO UPDATE SET captured_paise = captured_paise + ?",
                    (payment_id, amount_paise, amount_paise)
                )
                cur.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )

            elif event_type == "refund.processed":
                cur.execute(
                    "SELECT captured_paise FROM payments WHERE payment_id = ?",
                    (payment_id,)
                )
                row = cur.fetchone()
                if not row:
                    return {"status": "error", "reason": "payment_not_found"}

                cur.execute(
                    "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                    (amount_paise, payment_id)
                )
                cur.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )

        return {"status": "success", "reason": "processed"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
