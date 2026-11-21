"""Contract event definitions, serialization, signing, and test fixtures."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any, Dict, Optional, Tuple, Union

TEST_SECRET = "paysift_secret_key_v1_offline_test"


def canonical_bytes(event: Dict[str, Any]) -> bytes:
    """Serialize dictionary to canonical UTF-8 JSON bytes.

    Uses sort_keys=True, separators=(',', ':'), ensure_ascii=False.
    Guarantees that identical data produces identical byte sequences.
    """
    return json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sign(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Compute lowercase hex HMAC-SHA256 signature over raw_body bytes."""
    secret_bytes = secret.encode("utf-8")
    return hmac.new(secret_bytes, raw_body, hashlib.sha256).hexdigest().lower()


def body_variant_canonical(event: Dict[str, Any]) -> bytes:
    """Canonical compact JSON body."""
    return canonical_bytes(event)


def body_variant_spaced(event: Dict[str, Any]) -> bytes:
    """Valid JSON body with spaces after separators (', ', ': ')."""
    return json.dumps(event, separators=(", ", ": "), ensure_ascii=False).encode("utf-8")


def body_variant_reordered(event: Dict[str, Any]) -> bytes:
    """Valid JSON body with explicitly reversed key ordering."""
    items = list(event.items())
    reversed_dict = dict(reversed(items))
    return json.dumps(reversed_dict, separators=(",", ":"), sort_keys=False).encode("utf-8")


def body_variant_unicode_escaped(event: Dict[str, Any]) -> bytes:
    """Valid JSON body using standard Unicode \\u escape sequences."""
    return json.dumps(event, ensure_ascii=True, separators=(",", ":")).encode("utf-8")


def body_variant_trailing_newline(event: Dict[str, Any]) -> bytes:
    """Valid JSON body with trailing newline."""
    return canonical_bytes(event) + b"\n"


def body_variant_pretty(event: Dict[str, Any]) -> bytes:
    """Valid multi-line indented pretty JSON body."""
    return json.dumps(event, indent=2, sort_keys=True).encode("utf-8")


def signature_variant_valid(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Valid lowercase hex HMAC-SHA256 signature."""
    return sign(raw_body, secret)


def signature_variant_empty(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Empty signature string."""
    return ""


def signature_variant_wrong_secret(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Signature computed with an invalid secret."""
    return sign(raw_body, secret + "_invalid_suffix")


def signature_variant_flipped_byte(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Valid signature with one hex character altered."""
    sig = sign(raw_body, secret)
    first_char = "0" if sig[0] != "0" else "1"
    return first_char + sig[1:]


def signature_variant_uppercase(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Signature formatted in uppercase hex."""
    return sign(raw_body, secret).upper()


def signature_variant_non_ascii(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Signature containing non-ASCII characters."""
    sig = sign(raw_body, secret)
    return "ñ" + sig[1:]


def signature_variant_reserialized(raw_body: bytes, secret: str = TEST_SECRET) -> str:
    """Signature computed over re-serialized JSON rather than exact raw bytes.

    If raw_body contains whitespace, signs over compact JSON.
    If raw_body is compact JSON, signs over spaced JSON.
    Guarantees signature mismatch with raw_body HMAC.
    """
    try:
        parsed = json.loads(raw_body.decode("utf-8"))
        compact = json.dumps(parsed, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if compact != raw_body:
            return sign(compact, secret)
        spaced = json.dumps(parsed, separators=(", ", ": "), ensure_ascii=False).encode("utf-8")
        return sign(spaced, secret)
    except Exception:
        return sign(raw_body, secret)


def encode_step(raw_body: bytes, signature: str, tag: str = "") -> Dict[str, str]:
    """Encode an event step for transmission or storage."""
    return {
        "raw_body_b64": base64.b64encode(raw_body).decode("ascii"),
        "signature": signature,
        "tag": tag,
    }


def decode_step(step: Dict[str, str]) -> Tuple[bytes, str, str]:
    """Decode an event step dictionary into (raw_body_bytes, signature, tag)."""
    raw_body = base64.b64decode(step["raw_body_b64"].encode("ascii"))
    signature = step.get("signature", "")
    tag = step.get("tag", "")
    return raw_body, signature, tag


def make_capture_event(
    event_id: str = "evt_001",
    payment_id: str = "pay_1",
    amount_paise: Any = 50000,
    **extra: Any,
) -> Dict[str, Any]:
    """Helper to construct a payment.captured event payload."""
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "type": "payment.captured",
        "payment_id": payment_id,
        "amount_paise": amount_paise,
    }
    payload.update(extra)
    return payload


def make_refund_event(
    event_id: str = "evt_002",
    payment_id: str = "pay_1",
    refund_id: str = "rfd_1",
    amount_paise: Any = 20000,
    **extra: Any,
) -> Dict[str, Any]:
    """Helper to construct a refund.processed event payload."""
    payload: Dict[str, Any] = {
        "event_id": event_id,
        "type": "refund.processed",
        "payment_id": payment_id,
        "refund_id": refund_id,
        "amount_paise": amount_paise,
    }
    payload.update(extra)
    return payload
