import sqlite3
import hmac
import hashlib
import json
import time
from typing import Dict, Any
from contextlib import contextmanager

def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, Any]:
    expected_sig = hmac.new(
        secret.encode('utf-8') if isinstance(secret, str) else secret,
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(expected_sig, signature):
        return {"status": "error", "reason": "invalid_signature"}
    
    try:
        event = json.loads(raw_body.decode('utf-8'))
    except Exception:
        return {"status": "error", "reason": "invalid_json"}
    
    event_id = event.get("event_id")
    event_type = event.get("type")
    payment_id = event.get("payment_id")
    amount_paise = event.get("amount_paise")
    
    if not event_id or not event_type or not payment_id or amount_paise is None:
        return {"status": "error", "reason": "missing_fields"}
    
    if event_type not in ("payment.captured", "refund.processed"):
        return {"status": "ignored", "reason": "unsupported_event_type"}
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("BEGIN IMMEDIATE")
        
        cursor.execute("SELECT 1 FROM ledger WHERE event_id = ?", (event_id,))
        if cursor.fetchone():
            conn.rollback()
            return {"status": "ignored", "reason": "duplicate_event"}
        
        if event_type == "payment.captured":
            cursor.execute(
                "SELECT payment_id FROM payments WHERE payment_id = ?", 
                (payment_id,)
            )
            row = cursor.fetchone()
            if row:
                conn.rollback()
                return {"status": "error", "reason": "payment_already_exists"}
            
            cursor.execute(
                "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                (payment_id, amount_paise)
            )
            cursor.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                (payment_id, amount_paise, event_id)
            )
            
        elif event_type == "refund.processed":
            cursor.execute(
                "SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?",
                (payment_id,)
            )
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return {"status": "error", "reason": "payment_not_found"}
            
            captured_paise, refunded_paise = row
            if refunded_paise + amount_paise > captured_paise:
                conn.rollback()
                return {"status": "error", "reason": "refund_exceeds_capture"}
            
            cursor.execute(
                "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                (amount_paise, payment_id)
            )
            cursor.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                (payment_id, amount_paise, event_id)
            )
            
        conn.commit()
        
    return {"status": "success", "reason": "processed"}
