def handle_event(db_path: str, raw_body: str, signature: str, secret: str) -> dict:
    import sqlite3
    import hmac
    import hashlib
    import json
    import contextlib

    expected_sig = hmac.new(
        secret.encode('utf-8'),
        raw_body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return {"status": "error", "reason": "invalid_signature"}

    try:
        event = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "reason": "invalid_body"}

    event_type = event.get('type')
    event_id = event.get('event_id')
    payment_id = event.get('payment_id')
    amount_paise = event.get('amount_paise')

    if not payment_id or not isinstance(amount_paise, int) or amount_paise <= 0:
        return {"status": "error", "reason": "invalid_payload"}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with contextlib.closing(conn):
            cur = conn.cursor()

            if event_type == 'payment.captured':
                cur.execute("SELECT captured_paise FROM payments WHERE payment_id = ?", (payment_id,))
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        "INSERT INTO payments (payment_id, captured_paise, refunded_paise) VALUES (?, ?, 0)",
                        (payment_id, amount_paise)
                    )
                    conn.commit()
                    cur.execute(
                        "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                        (payment_id, amount_paise, event_id)
                    )
                    conn.commit()
                else:
                    cur.execute(
                        "UPDATE payments SET captured_paise = captured_paise + ? WHERE payment_id = ?",
                        (amount_paise, payment_id)
                    )
                    conn.commit()
                    cur.execute(
                        "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'capture', ?, ?)",
                        (payment_id, amount_paise, event_id)
                    )
                    conn.commit()

            elif event_type == 'refund.processed':
                cur.execute("SELECT captured_paise, refunded_paise FROM payments WHERE payment_id = ?", (payment_id,))
                row = cur.fetchone()
                if row is None:
                    return {"status": "error", "reason": "payment_not_found"}

                current_refunded = row['refunded_paise']
                if current_refunded + amount_paise > row['captured_paise']:
                    return {"status": "error", "reason": "insufficient_fund_for_refund"}

                cur.execute(
                    "UPDATE payments SET refunded_paise = refunded_paise + ? WHERE payment_id = ?",
                    (amount_paise, payment_id)
                )
                conn.commit()
                cur.execute(
                    "INSERT INTO ledger (payment_id, kind, amount_paise, event_id) VALUES (?, 'refund', ?, ?)",
                    (payment_id, amount_paise, event_id)
                )
                conn.commit()

            else:
                return {"status": "error", "reason": "unknown_event_type"}

    except Exception as e:
        return {"status": "error", "reason": f"database_error: {str(e)}"}
    finally:
        if conn:
            conn.close()

    return {"status": "success", "reason": "processed"}
