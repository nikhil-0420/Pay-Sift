"""Unit tests for candidate generation, intake, AST gate, fake providers, and stale binding."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from generate.intake import extract_code, intake_candidate
from generate.generate import generate_candidate, run_generation_pipeline
from generate.providers import FakeProviderAdapter, scrub_secrets
from generate.spec_binding import check_candidate_spec_binding
from runner.run_candidate import run_candidate


def test_fence_extraction_python_block():
    """Verify code is extracted from markdown ```python ... ``` fences."""
    raw = """Here is the implementation:
```python
import sqlite3

def handle_event(db_path, raw_body, signature, secret):
    return {"status": "applied"}
```
Hope this helps!"""
    code = extract_code(raw)
    assert code.startswith("import sqlite3")
    assert "Hope this helps" not in code
    assert "Here is the implementation" not in code


def test_fence_extraction_generic_block():
    """Verify code is extracted from generic ``` ... ``` fences."""
    raw = """```
import json
def handle_event(db_path, raw_body, signature, secret):
    return {"status": "duplicate"}
```"""
    code = extract_code(raw)
    assert code.startswith("import json")
    assert code.strip().endswith('return {"status": "duplicate"}')


def test_raw_fallback():
    """Verify code without markdown fences falls back to untouched raw text."""
    raw = """import hashlib
def handle_event(db_path, raw_body, signature, secret):
    return {"status": "rejected"}"""
    code = extract_code(raw)
    assert code.strip() == raw.strip()


def test_key_scrubbing():
    """Verify API keys are scrubbed and replaced with [REDACTED_API_KEY]."""
    fake_secret = "sample_test_secret_key_dummy_998877"
    raw_error = f"Failed to connect to API with key {fake_secret}: 401 Unauthorized"
    scrubbed = scrub_secrets(raw_error, [fake_secret])
    assert fake_secret not in scrubbed
    assert "[REDACTED_API_KEY]" in scrubbed
    assert "401 Unauthorized" in scrubbed


def test_intake_compliant():
    """Verify intake marks code using only allowed modules as compliant."""
    code = """
import sqlite3
import hmac
import hashlib
import json

def handle_event(db_path, raw_body, signature, secret):
    return {"status": "applied"}
"""
    res = intake_candidate(code)
    assert res["compliant"] is True
    assert len(res["violations"]) == 0


def test_intake_non_compliant():
    """Verify intake detects disallowed imports (e.g. requests, os) and forbidden calls (eval)."""
    bad_code = """
import os
import requests

def handle_event(db_path, raw_body, signature, secret):
    eval("1+1")
    return {"status": "applied"}
"""
    res = intake_candidate(bad_code)
    assert res["compliant"] is False
    kinds = [v["kind"] for v in res["violations"]]
    assert "disallowed_import" in kinds
    assert "forbidden_call" in kinds


def test_candidate_generation_with_fake_provider(tmp_path: Path):
    """Verify generate_candidate writes .py, .raw.txt, and compliant .meta.json."""
    fake_code = """```python
import sqlite3
import json

def handle_event(db_path, raw_body, signature, secret):
    return {"status": "applied"}
```"""
    provider = FakeProviderAdapter(canned_responses=[fake_code])
    out_dir = tmp_path / "test_model" / "A"

    meta = generate_candidate(
        provider=provider,
        prompt="Write a webhook handler",
        model_id="test_model_v1",
        condition="A",
        sample_num=1,
        output_dir=out_dir,
        spec_sha="test_spec_sha_12345",
        p_hash="test_prompt_hash_67890",
    )

    assert meta["compliant"] is True
    assert meta["regeneration_count"] == 0
    assert meta["spec_sha"] == "test_spec_sha_12345"

    py_file = out_dir / "1.py"
    raw_file = out_dir / "1.raw.txt"
    meta_file = out_dir / "1.meta.json"

    assert py_file.is_file()
    assert raw_file.is_file()
    assert meta_file.is_file()

    loaded_meta = json.loads(meta_file.read_text(encoding="utf-8"))
    assert loaded_meta["sha256"] == meta["sha256"]


def test_regeneration_limit_on_non_compliant(tmp_path: Path):
    """Verify non-compliant output triggers up to 2 regenerations and stops marked non-compliant."""
    bad_code = "import os\ndef handle_event(a, b, c, d): return {}"
    provider = FakeProviderAdapter(canned_responses=[bad_code])
    out_dir = tmp_path / "bad_model" / "B"

    meta = generate_candidate(
        provider=provider,
        prompt="Write a webhook handler",
        model_id="bad_model_v1",
        condition="B",
        sample_num=1,
        output_dir=out_dir,
        spec_sha="test_spec_sha",
        p_hash="test_prompt_hash",
    )

    assert meta["compliant"] is False
    assert meta["regeneration_count"] == 2
    assert len(meta["violations"]) > 0
    assert provider.call_count == 3  # Initial + 2 regenerations


def test_global_call_cap_enforcement(tmp_path: Path):
    """Verify global call cap halts generation when reached."""
    provider = FakeProviderAdapter()
    out_dir = tmp_path / "cap_model" / "A"
    counter = [2]  # Already reached cap of 2

    with pytest.raises(RuntimeError) as exc:
        generate_candidate(
            provider=provider,
            prompt="Prompt",
            model_id="m",
            condition="A",
            sample_num=1,
            output_dir=out_dir,
            spec_sha="s",
            p_hash="p",
            call_counter=counter,
            max_allowed_calls=2,
        )
    assert "Global API call cap reached" in str(exc.value)


def test_spec_sha_stale_detection(tmp_path: Path):
    """Verify that candidates with mismatched spec_sha are flagged as stale and refused."""
    cand_file = tmp_path / "stale_cand.py"
    cand_file.write_text("import sqlite3\ndef handle_event(a, b, c, d): return {'status': 'applied'}\n", encoding="utf-8")
    meta_file = tmp_path / "stale_cand.meta.json"
    meta_file.write_text(json.dumps({
        "model": "stale_model",
        "spec_sha": "old_outdated_spec_sha_00000000",
    }), encoding="utf-8")

    is_valid, err_msg = check_candidate_spec_binding(cand_file, current_spec_sha="new_current_spec_sha_11111111")
    assert is_valid is False
    assert "Candidate is STALE" in (err_msg or "")

    with pytest.raises(ValueError) as exc:
        run_candidate(cand_file, mode="normal", seed_range=(0, 0))
    assert "Candidate is STALE" in str(exc.value)
