import sqlite3
import hmac
import hashlib
import json
import time
from typing import Dict, Any, Optional
from contextlib import contextmanager

@contextmanager
def db_transaction(db_path: str):
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

def _ensure_aux_tables(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY,
            status TEXT NOT NULL
        )
    """)

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> dict:
    # Rule 1: Signature Verification
    try:
        if not signature or not isinstance(signature, str):
            return {"status": "rejected", "reason": "Missing or invalid signature format"}
        
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            return {"status": "rejected", "reason": "Invalid signature"}
    except Exception:
        return {"status": "rejected", "reason": "Signature verification error"}

    # Rule 2: Payload Validation (UTF-8, JSON, Object structure, fields)
    try:
        body_str = raw_body.decode("utf-8")
    except UnicodeDecodeError:
        return {"status": "rejected", "reason": "Invalid UTF-8 encoding"}

    try:
        data = json.loads(body_str)
    except json.JSONDecodeError:
        return {"status": "rejected", "reason": "Invalid JSON syntax"}

    if not isinstance(data, dict):
        return {"status": "rejected", "reason": "Payload must be a JSON object"}

    event_id = data.get("event_id")
    if not isinstance(event_id, str) or not event_id or len(event_id) > 64:
        return {"status": "rejected", "reason": "Invalid or missing event_id"}

    event_type = data.get("type")
    if event_type not in ("payment.captured", "refund.processed"):
        return {"status": "rejected", "reason": "Invalid or missing event type"}

    payment_id = data.get("payment_id")
    if not isinstance(payment_id, str) or not payment_id or len(payment_id) > 64:
        return {"status": "rejected", "reason": "Invalid or missing payment_id"}

    amount_paise = data.get("amount_paise")
    if isinstance(amount_paise, bool) or not isinstance(amount_paise, int):
        return {"status": "rejected", "reason": "amount_paise must be a strict integer"}
    if amount_paise < 1 or amount_paise > 10**12:
        return {"status": "rejected", "reason": "amount_paise out of bounds"}

    if event_type == "refund.processed":
        refund_id = data.get("refund_id")
        if not isinstance(refund_id, str) or not refund_id:
            return {"status": "rejected", "reason": "Missing refund_id for refund event"}

    # Database operations with concurrency control and strict check precedence
    try:
        with db_transaction(db_path) as conn:
            _ensure_aux_tables(conn)
            
            # Rule 3: Idempotency Check
            cursor = conn.execute("SELECT status FROM processed_events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if row is not None:
                # C2 / R3: Only previously 'applied' events return 'duplicate'
                if row[0] == "applied":
                    return {"status": "duplicate", "reason": "Event already applied"}
                else:
                    # Previously rejected event_id does not consume idempotency (R8)
                    pass

            # Business Logic Execution
            if event_type == "payment.captured":
                # Rule 4: Payment Capture
                cursor = conn.execute("SELECT 1 FROM payments WHERE payment_id = ?", (payment_id,))
                if cursor.fetchone() is not None:
                    # Record the rejection attempt for this event_id
                    conn.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Payment already captured"}

                conn.execute(
                    "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                    (payment_id, amount_paise)
                )
                conn.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )
                conn.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "applied"))
                return {"status": "applied", "reason": "Capture processed successfully"}

            elif event_type == "refund.processed":
                # Rule 5: Refund Target Existence
                cursor = conn.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                pay_row = cursor.fetchone()
                if pay_row is None:
                    conn.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Payment not found for refund"}

                captured_paise, refunded_paise = pay_row

                # Rule 6: Refund Balance Bound
                if refunded_paise + amount_paise > captured_paise:
                    conn.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Refund exceeds remaining balance"}

                conn.execute(
                    "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                    (amount_paise, payment_id)
                )
                conn.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )
                conn.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "applied"))
                return {"status": "applied", "reason": "Refund processed successfully"}

            return {"status": "rejected", "reason": "Unknown event type"}

    except Exception as e:
        return {"status": "rejected", "reason": f"Internal database error: {str(e)}"}
