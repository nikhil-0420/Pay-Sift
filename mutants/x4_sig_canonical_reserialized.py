# HAND-WRITTEN MUTANT
# Mutant x4: verifies over canonical re-serialized JSON (violates Rule R1, Invariant I1_integrity)
"""Mutant x4: re-serializes payload canonically before verification. Fails only on non-canonical valid bodies (Family 8)."""

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

    # BUG (x4): Computes HMAC over canonically re-serialized JSON rather than raw_body bytes.
    # Passes on canonical payloads, but rejects valid non-canonical payloads (Family 8).
    try:
        parsed = json.loads(bytes(raw_body).decode("utf-8"))
        body_to_verify = json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except Exception:
        body_to_verify = bytes(raw_body)

    expected = hmac.new(secret.encode("utf-8"), body_to_verify, hashlib.sha256).hexdigest().lower()
    return hmac.compare_digest(signature.encode("ascii"), expected.encode("ascii"))


def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> Dict[str, str]:
    if not _verify_sig(raw_body, signature, secret):
        return {"status": "rejected", "reason": "Invalid signature (R1)"}

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

    if "event_id" not in data:
        return {"status": "rejected", "reason": "Missing event_id (R2)"}
    event_id = data["event_id"]
    if not isinstance(event_id, str) or len(event_id) == 0 or len(event_id) > 64:
        return {"status": "rejected", "reason": "Invalid event_id (R2)"}

    if "type" not in data:
        return {"status": "rejected", "reason": "Missing type (R2)"}
    ev_type = data["type"]
    if ev_type not in ("payment.captured", "refund.processed"):
        return {"status": "rejected", "reason": f"Invalid type '{ev_type}' (R2)"}

    if "payment_id" not in data:
        return {"status": "rejected", "reason": "Missing payment_id (R2)"}
    payment_id = data["payment_id"]
    if not isinstance(payment_id, str) or len(payment_id) == 0 or len(payment_id) > 64:
        return {"status": "rejected", "reason": "Invalid payment_id (R2)"}

    if "amount_paise" not in data:
        return {"status": "rejected", "reason": "Missing amount_paise (R2)"}
    amount = data["amount_paise"]
    if isinstance(amount, bool) or not isinstance(amount, int) or isinstance(amount, float):
        return {"status": "rejected", "reason": "amount_paise must be integer (R2)"}
    if amount < 1 or amount > 10**12:
        return {"status": "rejected", "reason": "amount_paise out of range [1, 10^12] (R2)"}

    if ev_type == "refund.processed":
        if "refund_id" not in data:
            return {"status": "rejected", "reason": "Missing refund_id for refund (R2)"}
        refund_id = data["refund_id"]
        if not isinstance(refund_id, str) or len(refund_id) == 0:
            return {"status": "rejected", "reason": "Invalid refund_id (R2)"}

    conn: Optional[sqlite3.Connection] = None
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

            cur.execute(
                "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                (payment_id, amount),
            )
            cur.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                (payment_id, amount, event_id),
            )
            cur.execute("INSERT INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
            cur.execute("COMMIT")
            return {"status": "applied", "reason": "Payment captured successfully"}

        else:
            cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
            row = cur.fetchone()
            if row is None:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Payment does not exist (R5)"}

            captured_paise, refunded_paise = row
            if refunded_paise + amount > captured_paise:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Refund exceeds captured balance (R6)"}

            cur.execute(
                "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                (amount, payment_id),
            )
            cur.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                (payment_id, amount, event_id),
            )
            cur.execute("INSERT INTO _paysift_applied_events (event_id) VALUES (?)", (event_id,))
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
