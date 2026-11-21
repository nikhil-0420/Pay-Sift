"""Reference implementation of PaySift payment webhook handler.

Strictly follows contract/SPEC.md (v1.0).
Does not import from oracle/ or mutants/.
Never raises an uncaught exception (R0).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from typing import Any, Dict, Optional


def _verify_sig(raw_body: bytes, signature: str, secret: str) -> bool:
    """Validate signature according to Rule R1."""
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
    """Processes a webhook event according to SPEC.md v1.0.

    Returns:
        {"status": "applied" | "duplicate" | "rejected", "reason": str}
    """
    # R1: Signature Verification
    if not _verify_sig(raw_body, signature, secret):
        return {"status": "rejected", "reason": "Invalid signature (R1)"}

    # R2: Payload Validation
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

    # Validate event_id
    if "event_id" not in data:
        return {"status": "rejected", "reason": "Missing event_id (R2)"}
    event_id = data["event_id"]
    if not isinstance(event_id, str) or len(event_id) == 0 or len(event_id) > 64:
        return {"status": "rejected", "reason": "Invalid event_id (R2)"}

    # Validate type
    if "type" not in data:
        return {"status": "rejected", "reason": "Missing type (R2)"}
    ev_type = data["type"]
    if ev_type not in ("payment.captured", "refund.processed"):
        return {"status": "rejected", "reason": f"Invalid type '{ev_type}' (R2)"}

    # Validate payment_id
    if "payment_id" not in data:
        return {"status": "rejected", "reason": "Missing payment_id (R2)"}
    payment_id = data["payment_id"]
    if not isinstance(payment_id, str) or len(payment_id) == 0 or len(payment_id) > 64:
        return {"status": "rejected", "reason": "Invalid payment_id (R2)"}

    # Validate amount_paise (reject bool, reject float, check bounds)
    if "amount_paise" not in data:
        return {"status": "rejected", "reason": "Missing amount_paise (R2)"}
    amount = data["amount_paise"]
    if isinstance(amount, bool) or not isinstance(amount, int) or isinstance(amount, float):
        return {"status": "rejected", "reason": "amount_paise must be integer (R2)"}
    if amount < 1 or amount > 10**12:
        return {"status": "rejected", "reason": "amount_paise out of range [1, 10^12] (R2)"}

    # Validate refund_id for refunds
    if ev_type == "refund.processed":
        if "refund_id" not in data:
            return {"status": "rejected", "reason": "Missing refund_id for refund (R2)"}
        refund_id = data["refund_id"]
        if not isinstance(refund_id, str) or len(refund_id) == 0:
            return {"status": "rejected", "reason": "Invalid refund_id (R2)"}

    # Database operations (C7, BEGIN IMMEDIATE transaction)
    conn: Optional[sqlite3.Connection] = None
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.isolation_level = None  # Explicit transaction control
        cur = conn.cursor()

        cur.execute("BEGIN IMMEDIATE")

        # Auxiliary deduplication table (C6)
        cur.execute(
            "CREATE TABLE IF NOT EXISTS _paysift_applied_events (event_id TEXT PRIMARY KEY)"
        )

        # R3: Deduplication check
        cur.execute(
            "SELECT 1 FROM _paysift_applied_events WHERE event_id = ?",
            (event_id,),
        )
        if cur.fetchone() is not None:
            cur.execute("ROLLBACK")
            return {"status": "duplicate", "reason": "Event already applied (R3)"}

        if ev_type == "payment.captured":
            # R4: Capture logic
            cur.execute(
                "SELECT 1 FROM payments WHERE payment_id = ?",
                (payment_id,),
            )
            if cur.fetchone() is not None:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Payment already captured (R4)"}

            # Insert payment record and ledger entry
            cur.execute(
                "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                (payment_id, amount),
            )
            cur.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                (payment_id, amount, event_id),
            )
            cur.execute(
                "INSERT INTO _paysift_applied_events (event_id) VALUES (?)",
                (event_id,),
            )
            cur.execute("COMMIT")
            return {"status": "applied", "reason": "Payment captured successfully"}

        else:  # refund.processed
            # R5: Refund target existence
            cur.execute(
                "SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?",
                (payment_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Payment does not exist (R5)"}

            captured_paise, refunded_paise = row

            # R6: Refund balance bound
            if refunded_paise + amount > captured_paise:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Refund exceeds captured balance (R6)"}

            # Apply refund
            cur.execute(
                "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                (amount, payment_id),
            )
            cur.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                (payment_id, amount, event_id),
            )
            cur.execute(
                "INSERT INTO _paysift_applied_events (event_id) VALUES (?)",
                (event_id,),
            )
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
