# HAND-WRITTEN MUTANT
# Mutant m3: no refund bound (violates Rule R6)
"""Mutant m3: omits refund upper-bound checks."""

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


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    if not _verify_sig(raw_body, signature, secret):
        return {"status": "rejected", "reason": "Invalid signature (R1)"}

    try:
        data = json.loads(bytes(raw_body).decode("utf-8"))
    except Exception:
        return {"status": "rejected", "reason": "Invalid JSON/UTF-8 (R2)"}

    if not isinstance(data, dict):
        return {"status": "rejected", "reason": "Payload must be object (R2)"}

    event_id = data.get("event_id")
    ev_type = data.get("type")
    payment_id = data.get("payment_id")
    amount = data.get("amount_paise")

    if not isinstance(event_id, str) or not event_id or len(event_id) > 64:
        return {"status": "rejected", "reason": "Invalid event_id (R2)"}
    if ev_type not in ("payment.captured", "refund.processed"):
        return {"status": "rejected", "reason": "Invalid type (R2)"}
    if not isinstance(payment_id, str) or not payment_id or len(payment_id) > 64:
        return {"status": "rejected", "reason": "Invalid payment_id (R2)"}
    if isinstance(amount, bool) or not isinstance(amount, int) or isinstance(amount, float) or amount < 1 or amount > 10**12:
        return {"status": "rejected", "reason": "Invalid amount_paise (R2)"}

    if ev_type == "refund.processed":
        refund_id = data.get("refund_id")
        if not isinstance(refund_id, str) or not refund_id:
            return {"status": "rejected", "reason": "Missing refund_id (R2)"}

    conn = None
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
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Payment already captured (R4)"}

            cur.execute("INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)", (payment_id, amount))
            cur.execute("INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)", (payment_id, amount, event_id))
            cur.execute("INSERT INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
            cur.execute("COMMIT")
            return {"status": "applied", "reason": "Payment captured"}

        else:
            cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
            row = cur.fetchone()
            if row is None:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Payment does not exist (R5)"}

            # BUG (m3): Omits the check `if refunded_paise + amount > captured_paise:`
            # Allows unbounded refunds exceeding captured amount (R6 violation)

            cur.execute("UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?", (amount, payment_id))
            cur.execute("INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)", (payment_id, amount, event_id))
            cur.execute("INSERT INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
            cur.execute("COMMIT")
            return {"status": "applied", "reason": "Refund processed"}
    except Exception as exc:
        if conn:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        return {"status": "rejected", "reason": str(exc)}
    finally:
        if conn:
            conn.close()
