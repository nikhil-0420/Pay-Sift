"""Deterministic seeded stream generator according to plan section 8.

Generates 10 distinct families of streams (seed % 10) for seeds 0-99.
Each step contains raw_body_b64, signature, and debug tag.
"""

from __future__ import annotations

import base64
import json
import random
from typing import Any, Dict, List, Optional, Tuple

from contract.events import (
    TEST_SECRET,
    body_variant_canonical,
    body_variant_pretty,
    body_variant_reordered,
    body_variant_spaced,
    body_variant_trailing_newline,
    body_variant_unicode_escaped,
    canonical_bytes,
    decode_step,
    encode_step,
    make_capture_event,
    make_refund_event,
    sign,
    signature_variant_empty,
    signature_variant_flipped_byte,
    signature_variant_non_ascii,
    signature_variant_reserialized,
    signature_variant_uppercase,
    signature_variant_wrong_secret,
)


def _step(raw_body: bytes, signature: str, tag: str) -> Dict[str, str]:
    return encode_step(raw_body, signature, tag)


def generate_stream(seed: int, secret: str = TEST_SECRET) -> List[Dict[str, str]]:
    """Generate a deterministic stream of 3 to 40 events based on seed."""
    rng = random.Random(seed)
    family = seed % 10
    steps: List[Dict[str, str]] = []

    if family == 0:
        # Family 0: Captures with injected duplicates
        n_events = rng.randint(4, 12)
        applied_events: List[Tuple[bytes, str, str]] = []
        for i in range(n_events):
            if applied_events and rng.random() < 0.4:
                # Inject a duplicate of a previously generated capture
                dup_body, dup_sig, dup_tag = rng.choice(applied_events)
                steps.append(_step(dup_body, dup_sig, f"{dup_tag}_duplicate"))
            else:
                eid = f"s{seed}_cap_{i}"
                pid = f"pay_{seed}_{i}"
                amt = rng.randint(1000, 100000)
                ev = make_capture_event(eid, pid, amt)
                b = canonical_bytes(ev)
                s = sign(b, secret)
                tag = f"capture_{eid}"
                applied_events.append((b, s, tag))
                steps.append(_step(b, s, tag))

    elif family == 1:
        # Family 1: Multiple payments, second-capture attempts
        n_payments = rng.randint(3, 6)
        payment_ids = [f"pay_{seed}_{i}" for i in range(n_payments)]
        for i, pid in enumerate(payment_ids):
            ev = make_capture_event(f"s{seed}_cap_{i}", pid, rng.randint(5000, 50000))
            b = canonical_bytes(ev)
            steps.append(_step(b, sign(b, secret), f"capture_{pid}"))

        # Injected second-capture attempts on existing payments
        n_second = rng.randint(2, 5)
        for j in range(n_second):
            target_pid = rng.choice(payment_ids)
            ev2 = make_capture_event(f"s{seed}_sec_cap_{j}", target_pid, rng.randint(1000, 20000))
            b2 = canonical_bytes(ev2)
            steps.append(_step(b2, sign(b2, secret), f"second_capture_{target_pid}"))

    elif family == 2:
        # Family 2: Partial, exact-bound and over-bound refunds
        pid = f"pay_{seed}_rfd"
        cap_amt = 100000  # ₹1000
        ev_c = make_capture_event(f"s{seed}_cap_base", pid, cap_amt)
        b_c = canonical_bytes(ev_c)
        steps.append(_step(b_c, sign(b_c, secret), "capture_base"))

        current_refunded = 0
        rfd_idx = 0
        while current_refunded < cap_amt and rfd_idx < 4:
            remaining = cap_amt - current_refunded
            action = rng.choice(["partial", "exact", "over"])
            if action == "partial" and remaining > 20000:
                amt = 20000
                current_refunded += amt
                ev_r = make_refund_event(f"s{seed}_rfd_{rfd_idx}", pid, f"r_{rfd_idx}", amt)
                b_r = canonical_bytes(ev_r)
                steps.append(_step(b_r, sign(b_r, secret), f"partial_refund_{amt}"))
            elif action == "exact" or remaining <= 20000:
                amt = remaining
                current_refunded += amt
                ev_r = make_refund_event(f"s{seed}_rfd_{rfd_idx}", pid, f"r_{rfd_idx}", amt)
                b_r = canonical_bytes(ev_r)
                steps.append(_step(b_r, sign(b_r, secret), f"exact_bound_refund_{amt}"))
            else:
                amt = remaining + 10000
                ev_r = make_refund_event(f"s{seed}_rfd_{rfd_idx}", pid, f"r_{rfd_idx}", amt)
                b_r = canonical_bytes(ev_r)
                steps.append(_step(b_r, sign(b_r, secret), f"over_bound_refund_{amt}"))
            rfd_idx += 1

        # Final over-bound attempt
        ev_over = make_refund_event(f"s{seed}_final_over", pid, "r_over", 5000)
        b_over = canonical_bytes(ev_over)
        steps.append(_step(b_over, sign(b_over, secret), "final_over_bound"))

    elif family == 3:
        # Family 3: Refund before capture, unknown payment
        ev_pre = make_refund_event(f"s{seed}_premature", f"pay_{seed}_future", "r_pre", 15000)
        b_pre = canonical_bytes(ev_pre)
        steps.append(_step(b_pre, sign(b_pre, secret), "refund_before_capture"))

        ev_unk = make_refund_event(f"s{seed}_unknown", f"pay_nonexistent_{seed}", "r_unk", 10000)
        b_unk = canonical_bytes(ev_unk)
        steps.append(_step(b_unk, sign(b_unk, secret), "refund_unknown_payment"))

        # Valid capture
        ev_ok = make_capture_event(f"s{seed}_ok_cap", f"pay_{seed}_ok", 50000)
        b_ok = canonical_bytes(ev_ok)
        steps.append(_step(b_ok, sign(b_ok, secret), "valid_capture"))

    elif family == 4:
        # Family 4: Invalid payloads (R2)
        bad_payloads = [
            (b"[1, 2, 3]", "non_object_array"),
            (b'{"event_id": "broken",', "invalid_json_syntax"),
            (b'{"event_id": \x80\x81, "type": "payment.captured"}', "invalid_utf8"),
            (canonical_bytes(make_capture_event(f"s{seed}_neg", "pay_neg", -5000)), "negative_amount"),
            (canonical_bytes(make_capture_event(f"s{seed}_zero", "pay_zero", 0)), "zero_amount"),
            (canonical_bytes(make_capture_event(f"s{seed}_flt", "pay_flt", 500.0)), "float_amount"),
            (canonical_bytes(make_capture_event(f"s{seed}_str", "pay_str", "50000")), "str_amount"),
            (canonical_bytes(make_capture_event(f"s{seed}_bool", "pay_bool", True)), "bool_amount"),
            (canonical_bytes(make_capture_event(f"s{seed}_null", "pay_null", None)), "null_amount"),
            (canonical_bytes(make_capture_event(f"s{seed}_huge", "pay_huge", 10**13)), "huge_amount"),
            (canonical_bytes({"type": "payment.captured", "payment_id": "p", "amount_paise": 100}), "missing_eid"),
            (canonical_bytes({"event_id": "e", "payment_id": "p", "amount_paise": 100}), "missing_type"),
            (canonical_bytes({"event_id": "e", "type": "payment.captured", "amount_paise": 100}), "missing_pid"),
            (canonical_bytes({"event_id": "e", "type": "refund.processed", "payment_id": "p", "amount_paise": 100}), "missing_rid"),
        ]
        sample_bads = rng.sample(bad_payloads, k=rng.randint(5, 8))
        for raw, tag in sample_bads:
            sig = sign(raw, secret)
            steps.append(_step(raw, sig, tag))

        # Interleave one valid capture
        ev_c = make_capture_event(f"s{seed}_f4_valid", "pay_f4", 25000)
        b_c = canonical_bytes(ev_c)
        steps.append(_step(b_c, sign(b_c, secret), "valid_capture_f4"))

    elif family == 5:
        # Family 5: Signature variants (R1)
        ev_base = make_capture_event(f"s{seed}_sig_test", "pay_sig", 30000)
        raw_c = canonical_bytes(ev_base)
        raw_sp = body_variant_spaced(ev_base)

        sig_tests = [
            (raw_c, signature_variant_empty(raw_c), "empty_signature"),
            (raw_c, signature_variant_wrong_secret(raw_c, secret), "wrong_secret_signature"),
            (raw_c, signature_variant_flipped_byte(raw_c, secret), "flipped_byte_signature"),
            (raw_c, signature_variant_uppercase(raw_c, secret), "uppercase_hex_signature"),
            (raw_c, signature_variant_non_ascii(raw_c, secret), "non_ascii_signature"),
            (raw_sp, signature_variant_reserialized(raw_sp, secret), "reserialized_signature_mismatch"),
        ]
        for raw, sig, tag in sig_tests:
            steps.append(_step(raw, sig, tag))

        # Valid capture
        steps.append(_step(raw_c, sign(raw_c, secret), "valid_signature_capture"))

    elif family == 6:
        # Family 6: Rejected-then-redelivered (R8)
        pid = f"pay_{seed}_r8"
        ev_c = make_capture_event(f"s{seed}_cap_r8", pid, 60000)
        b_c = canonical_bytes(ev_c)

        # 1. Premature refund (rejected R5)
        ev_r = make_refund_event(f"s{seed}_rfd_r8", pid, "r_r8", 25000)
        b_r = canonical_bytes(ev_r)
        steps.append(_step(b_r, sign(b_r, secret), "premature_refund_r5"))

        # 2. Capture applied (R4)
        steps.append(_step(b_c, sign(b_c, secret), "capture_applied_r4"))

        # 3. Same refund redelivered (applied R8)
        steps.append(_step(b_r, sign(b_r, secret), "redelivered_refund_applied_r8"))

        # 4. Bad signature rejected (R1), then valid signature with same event ID (R8)
        ev_bad_sig = make_capture_event(f"s{seed}_badsig_then_good", f"pay_bsg_{seed}", 40000)
        b_bsg = canonical_bytes(ev_bad_sig)
        s_bad = signature_variant_flipped_byte(b_bsg, secret)
        steps.append(_step(b_bsg, s_bad, "bad_signature_r1"))
        steps.append(_step(b_bsg, sign(b_bsg, secret), "good_signature_redelivery_r8"))

    elif family == 7:
        # Family 7: Duplicate refunds, same refund_id on distinct events, same event_id different payload
        pid = f"pay_{seed}_f7"
        ev_c = make_capture_event(f"s{seed}_cap_f7", pid, 80000)
        b_c = canonical_bytes(ev_c)
        steps.append(_step(b_c, sign(b_c, secret), "capture_f7"))

        # Refund 1
        ev_r1 = make_refund_event(f"s{seed}_r1_f7", pid, "shared_rfd_id", 20000)
        b_r1 = canonical_bytes(ev_r1)
        steps.append(_step(b_r1, sign(b_r1, secret), "refund_1_f7"))

        # Duplicate of Refund 1
        steps.append(_step(b_r1, sign(b_r1, secret), "refund_1_duplicate_f7"))

        # Refund 2 with same refund_id but distinct event_id (C1)
        ev_r2 = make_refund_event(f"s{seed}_r2_f7", pid, "shared_rfd_id", 20000)
        b_r2 = canonical_bytes(ev_r2)
        steps.append(_step(b_r2, sign(b_r2, secret), "refund_2_shared_rfd_id_f7"))

        # Same event_id with different payload after first applied (C5/R3)
        ev_alt = make_capture_event(f"s{seed}_cap_f7", pid, 999999)
        b_alt = canonical_bytes(ev_alt)
        steps.append(_step(b_alt, sign(b_alt, secret), "capture_same_eid_altered_payload"))

    elif family == 8:
        # Family 8: Non-canonical valid bodies signed correctly over raw bytes
        body_builders = [
            (body_variant_spaced, "spaced_separators"),
            (body_variant_reordered, "reordered_keys"),
            (body_variant_unicode_escaped, "unicode_escaped"),
            (body_variant_trailing_newline, "trailing_newline"),
            (body_variant_pretty, "pretty_printed"),
        ]
        for idx, (builder, tag) in enumerate(body_builders):
            ev = make_capture_event(f"s{seed}_nc_{idx}", f"pay_nc_{seed}_{idx}", 35000 + idx * 1000)
            raw = builder(ev)
            steps.append(_step(raw, sign(raw, secret), f"non_canonical_{tag}"))

    elif family == 9:
        # Family 9: Long mixed streams (30 to 40 events) for shrinker demos
        n_events = rng.randint(30, 40)
        payments: List[str] = []
        captured_events: List[Tuple[bytes, str, str]] = []

        for i in range(n_events):
            choice = rng.random()
            if choice < 0.4 or not payments:
                # New capture
                pid = f"pay_long_{seed}_{len(payments)}"
                payments.append(pid)
                amt = rng.randint(20000, 100000)
                ev = make_capture_event(f"s{seed}_long_{i}", pid, amt)
                b = canonical_bytes(ev)
                s = sign(b, secret)
                tag = f"capture_{pid}"
                captured_events.append((b, s, tag))
                steps.append(_step(b, s, tag))
            elif choice < 0.7:
                # Valid or over refund
                pid = rng.choice(payments)
                amt = rng.randint(5000, 40000)
                ev = make_refund_event(f"s{seed}_long_{i}", pid, f"r_{i}", amt)
                b = canonical_bytes(ev)
                s = sign(b, secret)
                steps.append(_step(b, s, f"refund_{pid}"))
            elif choice < 0.85 and captured_events:
                # Injected duplicate
                dup_b, dup_s, dup_t = rng.choice(captured_events)
                steps.append(_step(dup_b, dup_s, f"{dup_t}_dup"))
            else:
                # Signature variant or bad amount
                pid = rng.choice(payments)
                ev = make_capture_event(f"s{seed}_long_{i}", pid, 10000)
                b = canonical_bytes(ev)
                s_bad = signature_variant_flipped_byte(b, secret)
                steps.append(_step(b, s_bad, f"bad_sig_{pid}"))

    return steps


def render_stream(steps: List[Dict[str, str]]) -> str:
    """Render a human-readable summary of an event stream."""
    lines = [f"Stream contains {len(steps)} steps:"]
    for idx, step in enumerate(steps):
        raw_body, sig, tag = decode_step(step)
        preview = ""
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
            preview = f"type={parsed.get('type')}, eid={parsed.get('event_id')}, pid={parsed.get('payment_id')}, amt={parsed.get('amount_paise')}"
        except Exception:
            preview = f"raw={raw_body[:30]!r}"
        lines.append(f"  [{idx:02d}] tag='{tag}' sig='{sig[:8]}...' | {preview}")
    return "\n".join(lines)
