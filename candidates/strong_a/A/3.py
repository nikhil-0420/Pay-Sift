import sqlite3
import hmac
import hashlib
import json
import time
from typing import Dict, Any
from contextlib import contextmanager

@contextmanager
def get_db(db_path: str):
    conn = sqlite3.connect(db_path, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_aux(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY,
            status TEXT NOT NULL
        )
    """)

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> dict:
    try:
        if not isinstance(signature, str):
            return {"status": "rejected", "reason": "Invalid signature type"}
        
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_sig, signature):
            return {"status": "rejected", "reason": "Signature mismatch"}

        try:
            body_str = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            return {"status": "rejected", "reason": "Invalid UTF-8"}

        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            return {"status": "rejected", "reason": "Invalid JSON"}

        if not isinstance(payload, dict):
            return {"status": "rejected", "reason": "Payload must be object"}

        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id or len(event_id) > 64:
            return {"status": "rejected", "reason": "Invalid event_id"}

        event_type = payload.get("type")
        if event_type not in ("payment.captured", "refund.processed"):
            return {"status": "rejected", "reason": "Invalid type"}

        payment_id = payload.get("payment_id")
        if not isinstance(payment_id, str) or not payment_id or len(payment_id) > 64:
            return {"status": "rejected", "reason": "Invalid payment_id"}

        amount_paise = payload.get("amount_paise")
        if isinstance(amount_paise, bool) or not isinstance(amount_paise, int):
            return {"status": "rejected", "reason": "amount_paise must be integer"}
        if amount_paise < 1 or amount_paise > 10**12:
            return {"status": "rejected", "reason": "amount_paise out of bounds"}

        if event_type == "refund.processed":
            refund_id = payload.get("refund_id")
            if not isinstance(refund_id, str) or not refund_id:
                return {"status": "rejected", "reason": "Missing refund_id"}

        with get_db(db_path) as conn:
            init_aux(conn)
            cursor = conn.cursor()
            
            cursor.execute("SELECT status FROM processed_events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if row:
                return {"status": "duplicate", "reason": "Event already processed"}

            if event_type == "payment.captured":
                cursor.execute("SELECT captured_paise FROM payments WHERE payment_id = ?", (payment_id,))
                p_row = cursor.fetchone()
                if p_row is not None:
                    cursor.execute("INSERT INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Payment already captured"}

                cursor.execute(
                    "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                    (payment_id, amount_paise)
                )
                cursor.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )
                cursor.execute("INSERT INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "applied"))
                return {"status": "applied", "reason": "Payment captured successfully"}

            elif event_type == "refund.processed":
                cursor.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                p_row = cursor.fetchone()
                if p_row is None:
                    cursor.execute("INSERT INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Payment not found"}

                captured, refunded = p_row
                if refunded + amount_paise > captured:
                    cursor.execute("INSERT INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Refund exceeds capture"}

                cursor.execute(
                    "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                    (amount_paise, payment_id)
                )
                cursor.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )
                cursor.execute("INSERT INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "applied"))
                return {"status": "applied", "reason": "Refund processed successfully"}

        return {"status": "rejected", "reason": "Unknown error"}
    except Exception as e:
        return {"status": "rejected", "reason": f"Internal error: {str(e)}"}
