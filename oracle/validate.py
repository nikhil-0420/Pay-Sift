"""Independent contract validator written strictly from SPEC.md.

Does NOT import anything from ref/ or mutants/.
Never raises exceptions.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Dict, Optional, Tuple


def check_signature(raw: Any, sig: Any, secret: Any) -> bool:
    """Validate signature according to Rule R1.

    Requirements:
    - secret: UTF-8 string
    - raw: bytes
    - sig: string, exact lowercase ASCII hex HMAC-SHA256 of raw bytes
    - Uses constant-time comparison (hmac.compare_digest)
    - Returns False for any deviation or malformed input, never raises.
    """
    try:
        if not isinstance(raw, (bytes, bytearray)):
            return False
        if not isinstance(sig, str) or not isinstance(secret, str):
            return False
        if not sig.isascii():
            return False
        if len(sig) != 64:
            return False
        # Must be strictly lowercase hex (R1: lowercase hex only)
        for ch in sig:
            if ch not in "0123456789abcdef":
                return False

        secret_bytes = secret.encode("utf-8")
        expected_sig = hmac.new(secret_bytes, bytes(raw), hashlib.sha256).hexdigest().lower()
        return hmac.compare_digest(sig.encode("ascii"), expected_sig.encode("ascii"))
    except Exception:
        return False


def validate_payload(raw: Any) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """Validate raw payload according to Rule R2.

    Requirements:
    - raw: valid UTF-8 bytes encoding a JSON object
    - event_id: non-empty string, length <= 64
    - type: "payment.captured" or "refund.processed"
    - payment_id: non-empty string, length <= 64
    - amount_paise: strict JSON integer from 1 to 10^12 inclusive
      (reject bool, reject float including 5.0 and 1e3, reject string, reject null, reject <= 0)
    - refund_id: non-empty string for refunds
    - Extra unrecognized fields are ignored.
    - Returns (is_valid, parsed_event_or_None, reason), never raises.
    """
    try:
        if not isinstance(raw, (bytes, bytearray)):
            return False, None, "Payload must be bytes"

        try:
            text = bytes(raw).decode("utf-8")
        except UnicodeDecodeError as exc:
            return False, None, f"Invalid UTF-8 encoding: {exc}"

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return False, None, f"Invalid JSON syntax: {exc}"

        if not isinstance(parsed, dict):
            return False, None, "JSON root must be an object"

        # event_id
        if "event_id" not in parsed:
            return False, None, "Missing event_id"
        event_id = parsed["event_id"]
        if not isinstance(event_id, str) or len(event_id) == 0:
            return False, None, "event_id must be a non-empty string"
        if len(event_id) > 64:
            return False, None, "event_id exceeds maximum length of 64 characters"

        # type
        if "type" not in parsed:
            return False, None, "Missing type"
        ev_type = parsed["type"]
        if ev_type not in ("payment.captured", "refund.processed"):
            return False, None, f"Unsupported event type: '{ev_type}'"

        # payment_id
        if "payment_id" not in parsed:
            return False, None, "Missing payment_id"
        payment_id = parsed["payment_id"]
        if not isinstance(payment_id, str) or len(payment_id) == 0:
            return False, None, "payment_id must be a non-empty string"
        if len(payment_id) > 64:
            return False, None, "payment_id exceeds maximum length of 64 characters"

        # amount_paise (must be strict integer, reject bool, reject float, reject string/null)
        if "amount_paise" not in parsed:
            return False, None, "Missing amount_paise"
        amount = parsed["amount_paise"]
        if isinstance(amount, bool):
            return False, None, "amount_paise cannot be a boolean"
        if not isinstance(amount, int) or isinstance(amount, float):
            return False, None, "amount_paise must be a JSON integer"
        if amount < 1 or amount > 10**12:
            return False, None, f"amount_paise {amount} out of bounds [1, 10^12]"

        # refund_id for refunds
        if ev_type == "refund.processed":
            if "refund_id" not in parsed:
                return False, None, "Missing refund_id for refund.processed"
            refund_id = parsed["refund_id"]
            if not isinstance(refund_id, str) or len(refund_id) == 0:
                return False, None, "refund_id must be a non-empty string"

        return True, parsed, "ok"

    except Exception as exc:
        return False, None, f"Unexpected validation error: {exc}"
