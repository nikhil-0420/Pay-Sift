"""Comprehensive tests for contract specifications, cases, prompts, and sample runs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contract.build_prompts import build_prompts
from contract.events import (
    TEST_SECRET,
    body_variant_canonical,
    body_variant_pretty,
    body_variant_spaced,
    canonical_bytes,
    decode_step,
    encode_step,
    make_capture_event,
    make_refund_event,
    sign,
    signature_variant_flipped_byte,
    signature_variant_uppercase,
    signature_variant_wrong_secret,
)
from contract.spec_sha import compute_spec_sha, prompt_hash, update_spec_hash_file
from contract.validate_run import validate, validate_kill_matrix


def test_jsonl_validity_and_case_count():
    """Verify JSON validity of cases.jsonl, check >= 40 cases, and unique IDs."""
    cases_file = Path("E:/PaySift/contract/cases.jsonl")
    assert cases_file.is_file(), "cases.jsonl does not exist"

    lines = cases_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 40, f"Expected >= 40 cases, got {len(lines)}"

    seen_ids = set()
    cited_rules = set()

    for line in lines:
        case = json.loads(line)
        cid = case["id"]
        assert cid not in seen_ids, f"Duplicate case ID: {cid}"
        seen_ids.add(cid)

        # Check steps and expected outcome
        assert "steps" in case and len(case["steps"]) > 0
        assert "expected" in case
        assert "steps" in case["expected"]
        assert "final_state" in case["expected"]

        for s in case["expected"]["steps"]:
            rule = s.get("rule")
            if rule:
                cited_rules.add(rule)

    # Verify every rule R0..R10 is cited by at least one case
    expected_rules = {f"R{i}" for i in range(11)}
    missing_rules = expected_rules - cited_rules
    assert not missing_rules, f"Rules not cited in cases.jsonl: {missing_rules}"


def test_worked_examples_validity():
    """Verify JSON validity and structure of worked_examples.jsonl."""
    we_file = Path("E:/PaySift/contract/worked_examples.jsonl")
    assert we_file.is_file(), "worked_examples.jsonl does not exist"

    lines = we_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) >= 15, f"Expected >= 15 worked examples, got {len(lines)}"

    for line in lines:
        ex = json.loads(line)
        assert "id" in ex
        assert "steps" in ex
        assert "expected" in ex


def test_hash_determinism():
    """Verify compute_spec_sha is strictly deterministic."""
    root = Path("E:/PaySift/contract")
    spec_path = root / "SPEC.md"
    schema_path = root / "schema.sql"

    sha1 = compute_spec_sha(spec_path, schema_path)
    sha2 = compute_spec_sha(spec_path, schema_path)
    assert sha1 == sha2
    assert len(sha1) == 64

    # Verify SPEC_HASH file matches
    hash_file = root / "SPEC_HASH"
    assert hash_file.is_file()
    assert hash_file.read_text(encoding="utf-8").strip() == sha1


def test_prompt_build_determinism(tmp_path: Path):
    """Verify prompt generation is strictly byte-identical across repeated runs."""
    contract_dir = Path("E:/PaySift/contract")
    full_prompt = contract_dir / "prompt_full.txt"
    casual_prompt = contract_dir / "prompt_casual.txt"

    content_full_before = full_prompt.read_text(encoding="utf-8")
    content_casual_before = casual_prompt.read_text(encoding="utf-8")

    # Re-run build_prompts
    build_prompts()

    content_full_after = full_prompt.read_text(encoding="utf-8")
    content_casual_after = casual_prompt.read_text(encoding="utf-8")

    assert content_full_before == content_full_after
    assert content_casual_before == content_casual_after

    # Verify hashes match
    assert prompt_hash(content_full_before) == prompt_hash(content_full_after)
    assert prompt_hash(content_casual_before) == prompt_hash(content_casual_after)


def test_sample_run_validates():
    """Verify runs/sample.json validates against Run JSON v1.1 schema."""
    sample_path = Path("E:/PaySift/runs/sample.json")
    assert sample_path.is_file()

    data = json.loads(sample_path.read_text(encoding="utf-8"))
    errors = validate(data)
    assert not errors, f"sample.json validation errors: {errors}"

    # Verify specific hero bug contents
    assert data["candidate"]["source"] == "stub"
    assert data["candidate"]["label"] == "FAKE SAMPLE FOR UI DEVELOPMENT"
    assert len(data["failures"]) == 1
    fail = data["failures"][0]
    assert fail["invariant"] == "I2_idempotency"
    assert fail["rule"] == "R3"
    assert len(fail["stream"]) == 40
    assert len(fail["minimal_stream"]) == 2
    assert fail["one_minimal"] is True
    assert len(fail["shrink_history"]) >= 4
    assert fail["classification"]["label"] == "unreviewed"
    assert fail["classification"]["by"] == "agent-proposed"


def test_kill_matrix_sample_validates():
    """Verify runs/kill_matrix.sample.json validates against kill matrix specification."""
    km_path = Path("E:/PaySift/runs/kill_matrix.sample.json")
    assert km_path.is_file()

    data = json.loads(km_path.read_text(encoding="utf-8"))
    errors = validate_kill_matrix(data)
    assert not errors, f"kill_matrix.sample.json validation errors: {errors}"

    # Check reference row is clean (not killed)
    ref_rows = [r for r in data["rows"] if r["id"] == "ref"]
    assert len(ref_rows) == 1
    assert ref_rows[0]["killed"] is False

    # Check mutants are present (m1..m9, x1..x4)
    mutant_ids = {r["id"] for r in data["rows"]}
    for m in [f"m{i}" for i in range(1, 10)] + [f"x{i}" for i in range(1, 5)]:
        assert m in mutant_ids, f"Missing mutant {m} in sample kill matrix"


def test_events_module_helpers():
    """Verify serialization, signing, and encode/decode helpers in contract.events."""
    ev = make_capture_event("evt_test", "pay_test", 10000)
    raw = canonical_bytes(ev)
    sig = sign(raw)
    assert len(sig) == 64

    # Different key orders produce identical canonical bytes
    ev_reordered = {"amount_paise": 10000, "payment_id": "pay_test", "type": "payment.captured", "event_id": "evt_test"}
    assert canonical_bytes(ev_reordered) == raw

    # Signature variants
    assert signature_variant_uppercase(raw) == sig.upper()
    assert signature_variant_wrong_secret(raw) != sig
    assert signature_variant_flipped_byte(raw) != sig

    # Step encoding/decoding
    step = encode_step(raw, sig, "test_tag")
    decoded_raw, decoded_sig, decoded_tag = decode_step(step)
    assert decoded_raw == raw
    assert decoded_sig == sig
    assert decoded_tag == "test_tag"
