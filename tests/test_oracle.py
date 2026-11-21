"""Unit and integration tests for oracle/validate.py, oracle/model.py, and oracle/checks.py."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from contract.events import TEST_SECRET, canonical_bytes, decode_step, make_capture_event, sign
from oracle.checks import compute_oracle_sha, verify_step
from oracle.model import Model
from oracle.validate import check_signature, validate_payload


def test_validate_signature_classes():
    """Test check_signature across valid and invalid variants."""
    ev = make_capture_event("evt_sig", "pay_sig", 20000)
    raw = canonical_bytes(ev)
    valid_sig = sign(raw, TEST_SECRET)

    # Valid
    assert check_signature(raw, valid_sig, TEST_SECRET) is True

    # Bad secret
    assert check_signature(raw, valid_sig, "wrong_secret") is False

    # Empty string
    assert check_signature(raw, "", TEST_SECRET) is False

    # Uppercase hex
    assert check_signature(raw, valid_sig.upper(), TEST_SECRET) is False

    # Non-ASCII
    assert check_signature(raw, "ñ" + valid_sig[1:], TEST_SECRET) is False

    # Corrupted byte
    flipped = ("1" if valid_sig[0] == "0" else "0") + valid_sig[1:]
    assert check_signature(raw, flipped, TEST_SECRET) is False

    # Wrong types / none
    assert check_signature(None, valid_sig, TEST_SECRET) is False
    assert check_signature(raw, None, TEST_SECRET) is False
    assert check_signature(raw, 12345, TEST_SECRET) is False


def test_validate_payload_classes():
    """Test validate_payload across valid and invalid payload variants."""
    # Valid capture
    ev_c = make_capture_event("evt_c", "pay_c", 30000)
    ok, parsed, _ = validate_payload(canonical_bytes(ev_c))
    assert ok is True
    assert parsed["event_id"] == "evt_c"

    # Valid refund
    ev_r = {"event_id": "evt_r", "type": "refund.processed", "payment_id": "pay_c", "refund_id": "rfd_1", "amount_paise": 10000}
    ok, parsed, _ = validate_payload(canonical_bytes(ev_r))
    assert ok is True
    assert parsed["refund_id"] == "rfd_1"

    # Bad amounts: boolean
    ok, _, reason = validate_payload(canonical_bytes({"event_id": "e", "type": "payment.captured", "payment_id": "p", "amount_paise": True}))
    assert ok is False
    assert "boolean" in reason

    # Bad amounts: float
    ok, _, reason = validate_payload(canonical_bytes({"event_id": "e", "type": "payment.captured", "payment_id": "p", "amount_paise": 500.0}))
    assert ok is False

    # Bad amounts: zero and negative
    ok, _, _ = validate_payload(canonical_bytes({"event_id": "e", "type": "payment.captured", "payment_id": "p", "amount_paise": 0}))
    assert ok is False
    ok, _, _ = validate_payload(canonical_bytes({"event_id": "e", "type": "payment.captured", "payment_id": "p", "amount_paise": -100}))
    assert ok is False

    # Bad amounts: overflow (> 10^12)
    ok, _, _ = validate_payload(canonical_bytes({"event_id": "e", "type": "payment.captured", "payment_id": "p", "amount_paise": 10**12 + 1}))
    assert ok is False

    # Exact max bound (10^12)
    ok, _, _ = validate_payload(canonical_bytes({"event_id": "e", "type": "payment.captured", "payment_id": "p", "amount_paise": 10**12}))
    assert ok is True

    # Missing refund_id for refund
    ok, _, _ = validate_payload(canonical_bytes({"event_id": "e", "type": "refund.processed", "payment_id": "p", "amount_paise": 1000}))
    assert ok is False

    # Non-object / malformed JSON
    ok, _, _ = validate_payload(b"[1, 2, 3]")
    assert ok is False
    ok, _, _ = validate_payload(b"invalid json")
    assert ok is False
    ok, _, _ = validate_payload(b"\xff\xfe\x00")
    assert ok is False


def test_model_vs_cases():
    """Verify Model agrees with every case in contract/cases.jsonl."""
    cases_file = Path("E:/PaySift/contract/cases.jsonl")
    cases = [json.loads(line) for line in cases_file.read_text(encoding="utf-8").splitlines()]

    for c in cases:
        cid = c["id"]
        m = Model()
        for sidx, (st, exp_s) in enumerate(zip(c["steps"], c["expected"]["steps"])):
            raw, sig, _ = decode_step(st)
            sig_ok = check_signature(raw, sig, TEST_SECRET)
            payload_ok, parsed, _ = validate_payload(raw)
            status, rule = m.apply(raw, sig_ok, payload_ok, parsed)
            assert status == exp_s["status"], f"Case {cid} step {sidx} status mismatch: expected {exp_s['status']}, got {status}"

        # Check final payments state
        m_snap = m.get_snapshot()
        exp_p = {p["payment_id"]: (p["captured_paise"], p["refunded_paise"]) for p in c["expected"]["final_state"]["payments"]}
        act_p = {p["payment_id"]: (p["captured_paise"], p["refunded_paise"]) for p in m_snap["payments"]}
        assert act_p == exp_p, f"Case {cid} final payments mismatch: expected {exp_p}, got {act_p}"


def test_model_vs_worked_examples():
    """Verify Model agrees with every example in contract/worked_examples.jsonl."""
    we_file = Path("E:/PaySift/contract/worked_examples.jsonl")
    examples = [json.loads(line) for line in we_file.read_text(encoding="utf-8").splitlines()]

    for ex in examples:
        eid = ex["id"]
        m = Model()
        for sidx, (st, exp_s) in enumerate(zip(ex["steps"], ex["expected"]["steps"])):
            raw, sig, _ = decode_step(st)
            sig_ok = check_signature(raw, sig, TEST_SECRET)
            payload_ok, parsed, _ = validate_payload(raw)
            status, rule = m.apply(raw, sig_ok, payload_ok, parsed)
            assert status == exp_s["status"], f"Example {eid} step {sidx} status mismatch"


def test_oracle_sha_determinism():
    """Verify compute_oracle_sha is deterministic and returns 64-char hex."""
    sha1 = compute_oracle_sha()
    sha2 = compute_oracle_sha()
    assert sha1 == sha2
    assert len(sha1) == 64
