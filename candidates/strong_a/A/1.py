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

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, Any]:
    try:
        # R1: Signature Verification
        if not signature or not isinstance(signature, str):
            return {"status": "rejected", "reason": "Missing or invalid signature"}
        
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_sig):
            # Check if event_id exists to satisfy C3/R1 precedence rule:
            # "A bad signature on an already-applied event_id must return 'rejected', not 'duplicate'."
            try:
                body_str = raw_body.decode("utf-8")
                parsed = json.loads(body_str)
                if isinstance(parsed, dict) and "event_id" in parsed:
                    eid = parsed["event_id"]
                    if isinstance(eid, str) and eid:
                        with get_db(db_path) as conn:
                            init_aux(conn)
                            cur = conn.cursor()
                            cur.execute("SELECT status FROM processed_events WHERE event_id = ?", (eid,))
                            row = cur.fetchone()
                            if row and row[0] == "applied":
                                return {"status": "rejected", "reason": "Invalid signature on applied event"}
            except Exception:
                pass
            return {"status": "rejected", "reason": "Signature mismatch"}

        # R2: Payload Validation (UTF-8 and JSON syntax)
        try:
            body_str = raw_body.decode("utf-8")
        except UnicodeDecodeError:
            return {"status": "rejected", "reason": "Invalid UTF-8 encoding"}

        try:
            payload = json.loads(body_str)
        except json.JSONDecodeError:
            return {"status": "rejected", "reason": "Invalid JSON syntax"}

        if not isinstance(payload, dict):
            return {"status": "rejected", "reason": "Payload must be a JSON object"}

        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id or len(event_id) > 64:
            return {"status": "rejected", "reason": "Invalid or missing event_id"}

        event_type = payload.get("type")
        if event_type not in ("payment.captured", "refund.processed"):
            return {"status": "rejected", "reason": "Invalid or missing event type"}

        payment_id = payload.get("payment_id")
        if not isinstance(payment_id, str) or not payment_id or len(payment_id) > 64:
            return {"status": "rejected", "reason": "Invalid or missing payment_id"}

        amount_paise = payload.get("amount_paise")
        if isinstance(amount_paise, bool) or not isinstance(amount_paise, int):
            return {"status": "rejected", "reason": "amount_paise must be an integer"}
        if amount_paise < 1 or amount_paise > 10**12:
            return {"status": "rejected", "reason": "amount_paise out of bounds"}

        if event_type == "refund.processed":
            refund_id = payload.get("refund_id")
            if not isinstance(refund_id, str) or not refund_id:
                return {"status": "rejected", "reason": "Missing or invalid refund_id"}

        with get_db(db_path) as conn:
            init_aux(conn)
            cur = conn.cursor()

            # R3: Idempotency Check
            cur.execute("SELECT status FROM processed_events WHERE event_id = ?", (event_id,))
            row = cur.fetchone()
            if row:
                if row[0] == "applied":
                    return {"status": "duplicate", "reason": "Event already applied"}
                elif row[0] == "rejected":
                    # R8: Rejection Non-Consumption. If previously rejected, we allow reprocessing.
                    pass

            # R4, R5, R6: Business Logic Execution
            if event_type == "payment.captured":
                cur.execute("SELECT captured_paise FROM payments WHERE payment_id = ?", (payment_id,))
                p_row = cur.fetchone()
                if p_row is not None:
                    cur.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Payment already captured"}
                
                cur.execute("INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)", (payment_id, amount_paise))
                cur.execute("INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)", (payment_id, amount_paise, event_id))
                cur.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "applied"))
                return {"status": "applied", "reason": "Capture processed successfully"}

            elif event_type == "refund.processed":
                cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                p_row = cur.fetchone()
                if p_row is None:
                    cur.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Payment not found for refund"}

                captured_paise, refunded_paise = p_row
                if refunded_paise + amount_paise > captured_paise:
                    cur.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "rejected"))
                    return {"status": "rejected", "reason": "Refund exceeds captured balance"}

                cur.execute("UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?", (amount_paise, payment_id))
                cur.execute("INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)", (payment_id, amount_paise, event_id))
                cur.execute("INSERT OR REPLACE INTO processed_events (event_id, status) VALUES (?, ?)", (event_id, "applied"))
                return {"status": "applied", "reason": "Refund processed successfully"}

        return {"status": "rejected", "reason": "Unknown event type"}

    except Exception as e:
        return {"status": "rejected", "reason": f"Internal error: {str(e)}"}
