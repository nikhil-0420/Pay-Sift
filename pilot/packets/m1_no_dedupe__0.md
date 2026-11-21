# Failure Packet: `m1_no_dedupe` (Failure #0)

## 1. Candidate Metadata
- **Candidate ID:** `m1_no_dedupe`
- **Model:** `reference`
- **Condition:** `-`
- **Sample:** `None`
- **SHA-256:** `dc2c16deef610589d358dd4636a85babe73f1c3d8b785bc13adc81b5cbc9ee65`
- **Spec SHA:** `289fa48f542ffcf36eb6f27ba4fd513c97312f8c987396b8a2e98e1cdaea230a`
- **Source Label:** `hand-written mutant, not model output`
- **Run JSON:** [`runs\real_example.json`](file:///runs/real_example.json)
- **Failing Seed:** `0` (mode: `normal`)
- **Reproduction:** `10 of 10 runs` (1-minimal: `True`)

## 2. Violated Contract Rule
### **Rule R3** (Invariant `I2_idempotency`)
> Event Idempotency: An event_id takes effect at most once. Redelivery of an already-applied event (with valid signature and payload): return status 'duplicate' and commit no database state change.

## 3. Minimal Counterexample Trace
1. `payment.captured s0_cap_0 (Rs 561.25)` [tag: capture_s0_cap_0]
2. `payment.captured s0_cap_0 (Rs 561.25)` [tag: capture_s0_cap_0_duplicate]

## 4. Expected vs Observed State
- **Explanation:** capture s0_cap_0 (Rs 561.25) delivered twice: the ledger shows 2 capture entries totaling Rs 1,122.50; the model expects 1 entry totaling Rs 561.25. Rule R3.
- **Expected State:** `N/A`
- **Observed State:** `N/A`

## 5. Candidate Source Code
*Full file (112 lines)*
```python
# HAND-WRITTEN MUTANT
# Mutant m1: no deduplication (violates Rule R3)
"""Mutant m1: omits event deduplication checks."""

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

        # BUG (m1): Omits deduplication check entirely.
        # It never checks if event_id was previously applied.

        if ev_type == "payment.captured":
            cur.execute("SELECT 1 FROM payments WHERE payment_id = ?", (payment_id,))
            if cur.fetchone() is not None:
                # If payment already captured, but if duplicate capture with same event_id:
                # Still inserts second ledger entry in this buggy handler!
                cur.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                    (payment_id, amount, event_id),
                )
                cur.execute("UPDATE payments SET captured_paise = captured_paise + ? WHERE payment_id = ?", (amount, payment_id))
                cur.execute("COMMIT")
                return {"status": "applied", "reason": "Duplicate capture applied incorrectly"}

            cur.execute("INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)", (payment_id, amount))
            cur.execute("INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)", (payment_id, amount, event_id))
            cur.execute("COMMIT")
            return {"status": "applied", "reason": "Payment captured"}

        else:
            cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
            row = cur.fetchone()
            if row is None:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Payment does not exist (R5)"}
            cap, ref = row
            if ref + amount > cap:
                cur.execute("ROLLBACK")
                return {"status": "rejected", "reason": "Refund exceeds balance (R6)"}

            cur.execute("UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?", (amount, payment_id))
            cur.execute("INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)", (payment_id, amount, event_id))
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

```

## 6. Classification
- **Proposed Class:** `(a)`
- **Classified By:** `agent-proposed`
- **Justification / Note:** Hand-written mutant m1_no_dedupe: duplicate capture accepted violating Rule R3
- **Human Decision:** `PENDING HUMAN REVIEW`
