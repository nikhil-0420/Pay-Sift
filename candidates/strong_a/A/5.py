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
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("BEGIN IMMEDIATE;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, Any]:
    try:
        if not signature or not isinstance(signature, str):
            return {"status": "rejected", "reason": "Missing or invalid signature format"}
        
        computed_sig = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(computed_sig, signature):
            return {"status": "rejected", "reason": "Invalid signature"}

        try:
            body_str = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            return {"status": "rejected", "reason": "Invalid UTF-8 encoding"}

        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            return {"status": "rejected", "reason": "Invalid JSON"}

        if not isinstance(payload, dict):
            return {"status": "rejected", "reason": "Payload must be a JSON object"}

        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id or len(event_id) > 64:
            return {"status": "rejected", "reason": "Invalid event_id"}

        event_type = payload.get("type")
        if event_type not in ("payment.captured", "refund.processed"):
            return {"status": "rejected", "reason": "Invalid event type"}

        payment_id = payload.get("payment_id")
        if not isinstance(payment_id, str) or not payment_id or len(payment_id) > 64:
            return {"status": "rejected", "reason": "Invalid payment_id"}

        amount_paise = payload.get("amount_paise")
        if isinstance(amount_paise, bool) or not isinstance(amount_paise, int):
            return {"status": "rejected", "reason": "amount_paise must be an integer"}
        if amount_paise < 1 or amount_paise > 1_000_000_000_000:
            return {"status": "rejected", "reason": "amount_paise out of bounds"}

        refund_id = None
        if event_type == "refund.processed":
            refund_id = payload.get("refund_id")
            if not isinstance(refund_id, str) or not refund_id:
                return {"status": "rejected", "reason": "Missing refund_id for refund event"}

        with get_db(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY
                )
            """)
            
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,))
            if cursor.fetchone():
                return {"status": "duplicate", "reason": "Event already applied"}

            if event_type == "payment.captured":
                cursor.execute("SELECT captured_paise FROM payments WHERE payment_id = ?", (payment_id,))
                row = cursor.fetchone()
                if row is not None:
                    return {"status": "rejected", "reason": "Payment already captured"}
                
                cursor.execute(
                    "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                    (payment_id, amount_paise)
                )
                cursor.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )
            elif event_type == "refund.processed":
                cursor.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                row = cursor.fetchone()
                if row is None:
                    return {"status": "rejected", "reason": "Payment not found for refund"}
                
                captured_paise, refunded_paise = row
                if refunded_paise + amount_paise > captured_paise:
                    return {"status": "rejected", "reason": "Refund exceeds captured balance"}
                
                cursor.execute(
                    "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                    (amount_paise, payment_id)
                )
                cursor.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )

            cursor.execute("INSERT INTO processed_events (event_id) VALUES (?)", (event_id,))

        return {"status": "applied", "reason": "Event applied successfully"}

    except Exception as e:
        return {"status": "rejected", "reason": f"Internal error: {str(e)}"}
