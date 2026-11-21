def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> dict:
    import sqlite3
    import hmac
    import hashlib
    import json
    import time
    import typing
    import contextlib

    try:
        # R1: Signature Verification (Strict precedence)
        # Must be lowercase hex HMAC-SHA256
        if not isinstance(signature, str):
            return {"status": "rejected", "reason": "signature not a string"}
        
        # Check for non-ASCII characters or invalid hex characters
        # Spec says "uppercase hex" is rejected. So signature must be strictly lowercase hex.
        try:
            if not signature:
                return {"status": "rejected", "reason": "empty signature"}
            if not all(c in "0123456789abcdef" for c in signature):
                return {"status": "rejected", "reason": "invalid signature format"}
        except UnicodeDecodeError:
            return {"status": "rejected", "reason": "invalid signature encoding"}

        expected_sig = hmac.new(
            secret.encode('utf-8'),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return {"status": "rejected", "reason": "signature mismatch"}

        # R2: Payload Validation
        try:
            decoded_str = raw_body.decode('utf-8')
        except UnicodeDecodeError:
            return {"status": "rejected", "reason": "invalid utf-8"}

        try:
            payload = json.loads(decoded_str)
        except json.JSONDecodeError:
            return {"status": "rejected", "reason": "invalid json"}

        if not isinstance(payload, dict):
            return {"status": "rejected", "reason": "payload not an object"}

        # Check event_id
        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id or len(event_id) > 64:
            return {"status": "rejected", "reason": "invalid event_id"}

        # Check type
        event_type = payload.get("type")
        if event_type not in ("payment.captured", "refund.processed"):
            return {"status": "rejected", "reason": "invalid type"}

        # Check payment_id
        payment_id = payload.get("payment_id")
        if not isinstance(payment_id, str) or not payment_id or len(payment_id) > 64:
            return {"status": "rejected", "reason": "invalid payment_id"}

        # Check amount_paise
        amount = payload.get("amount_paise")
        # Strict integer: not bool, not float, not string, not null
        if isinstance(amount, bool):
            return {"status": "rejected", "reason": "amount is boolean"}
        if not isinstance(amount, int):
            return {"status": "rejected", "reason": "amount not integer"}
        if amount < 1 or amount > 10**12:
            return {"status": "rejected", "reason": "amount out of bounds"}

        # Check refund_id if refund
        if event_type == "refund.processed":
            refund_id = payload.get("refund_id")
            if not isinstance(refund_id, str) or not refund_id:
                return {"status": "rejected", "reason": "invalid refund_id"}

    except Exception:
        return {"status": "rejected", "reason": "internal error during validation"}

    # Prepare database connection
    # We need to handle concurrent access safely.
    # Use a short timeout to avoid hanging indefinitely.
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("BEGIN IMMEDIATE")
        
        # Ensure auxiliary table exists for idempotency (R3)
        # This table tracks event_ids that have been successfully applied.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_events (
                event_id TEXT PRIMARY KEY
            )
        """)

        # R3: Idempotency Check
        cursor = conn.execute("SELECT 1 FROM processed_events WHERE event_id = ?", (event_id,))
        if cursor.fetchone():
            conn.rollback()
            conn.close()
            return {"status": "duplicate", "reason": "event already processed"}

        # Business Logic
        if event_type == "payment.captured":
            # R4: Capture
            cursor = conn.execute("SELECT 1 FROM payments WHERE payment_id = ?", (payment_id,))
            if cursor.fetchone():
                # Payment already captured
                conn.rollback()
                conn.close()
                return {"status": "rejected", "reason": "payment already captured"}
            
            # Insert into payments
            conn.execute(
                "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                (payment_id, amount)
            )
            # Insert into ledger
            conn.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                (payment_id, amount, event_id)
            )
            # Record event as processed
            conn.execute(
                "INSERT INTO processed_events (event_id) VALUES (?)",
                (event_id,)
            )
            
            conn.commit()
            conn.close()
            return {"status": "applied", "reason": "capture applied"}

        elif event_type == "refund.processed":
            # R5: Refund Target Existence
            cursor = conn.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                conn.close()
                return {"status": "rejected", "reason": "payment not found"}
            
            captured_paise = row[0]
            refunded_paise = row[1]
            
            # R6: Refund Balance Bound
            if refunded_paise + amount > captured_paise:
                conn.rollback()
                conn.close()
                return {"status": "rejected", "reason": "insufficient balance for refund"}
            
            # Update payments
            conn.execute(
                "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                (amount, payment_id)
            )
            # Insert into ledger
            conn.execute(
                "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                (payment_id, amount, event_id)
            )
            # Record event as processed
            conn.execute(
                "INSERT INTO processed_events (event_id) VALUES (?)",
                (event_id,)
            )
            
            conn.commit()
            conn.close()
            return {"status": "applied", "reason": "refund applied"}
        
        else:
            # Should not happen due to R2 validation
            conn.rollback()
            conn.close()
            return {"status": "rejected", "reason": "unknown event type"}

    except sqlite3.IntegrityError:
        # Fallback for race conditions if BEGIN IMMEDIATE didn't serialize enough
        # Although BEGIN IMMEDIATE should prevent write races, if there's a conflict
        # on processed_events (should be unique), it means a concurrent process beat us?
        # Actually, if we are inside a transaction, and another process inserted the same event_id
        # it would wait for our transaction to finish if it also did BEGIN IMMEDIATE.
        # If we get an IntegrityError here, it might be a unique constraint violation on payments.payment_id
        # which we checked manually, but a race could have inserted a payment with the same ID?
        # No, we checked existence in the same transaction.
        # If IntegrityError occurs, it's likely due to a constraint we didn't handle explicitly or a deeper conflict.
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "rejected", "reason": "integrity error"}
    except sqlite3.OperationalError as e:
        # Likely "database is locked" if timeout hit or other busy errors
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "rejected", "reason": "database locked"}
    except Exception as e:
        # Unhandled exceptions must not propagate (R0)
        try:
            if 'conn' in locals():
                try:
                    conn.rollback()
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
        except Exception:
            pass
        return {"status": "rejected", "reason": f"internal error: {str(e)}"}
