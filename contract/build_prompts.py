"""Build benchmark prompts deterministically from contract specification."""

from __future__ import annotations

from pathlib import Path
import sys

# Ensure root directory is on sys.path for relative imports when executed directly
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from contract.spec_sha import update_spec_hash_file


def build_prompts() -> None:
    """Generate prompt_full.txt (Condition A) and prompt_casual.txt (Condition B)."""
    contract_dir = Path(__file__).resolve().parent
    spec_path = contract_dir / "SPEC.md"
    schema_path = contract_dir / "schema.sql"

    spec_text = spec_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").strip()
    schema_sql = schema_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n").strip()

    # Condition A: Full specification prompt (the fair test)
    full_prompt_lines = [
        "Write a single-file Python implementation of handle_event according to the following strict specification.",
        "single file, no explanation, allowed imports: sqlite3, hmac, hashlib, json, time, typing, contextlib",
        "",
        "--- SPECIFICATION ---",
        "",
        spec_text,
        "",
        "--- HARNESS SCHEMA (schema.sql) ---",
        "",
        schema_sql,
        "",
        "--- END SPECIFICATION ---",
        "",
        "Return only the Python code. No markdown fences, no explanatory text.",
    ]
    full_prompt_text = "\n".join(full_prompt_lines) + "\n"

    # Condition B: Casual prompt verbatim from plan section 5 (illustrative test)
    casual_prompt_lines = [
        "Write a Python function `handle_event(db_path, raw_body, signature, secret)` for a payment gateway webhook. "
        "It receives `payment.captured` and `refund.processed` events as JSON, verifies the HMAC-SHA256 signature, "
        "and records them in the SQLite tables `payments` and `ledger` (schema and event examples below). "
        "Return `{\"status\": ..., \"reason\": ...}`. Single file, no explanation. "
        "Allowed imports: sqlite3, hmac, hashlib, json, time, typing, contextlib.",
        "",
        "### Database Schema",
        "```sql",
        schema_sql,
        "```",
        "",
        "### Event Examples",
        "```json",
        '{"event_id": "evt_001", "type": "payment.captured", "payment_id": "pay_1", "amount_paise": 50000}',
        '{"event_id": "evt_002", "type": "refund.processed", "payment_id": "pay_1", "refund_id": "rfd_1", "amount_paise": 20000}',
        "```",
        "",
        "Return only the Python code. No markdown fences, no explanatory text.",
    ]
    casual_prompt_text = "\n".join(casual_prompt_lines) + "\n"

    out_full = contract_dir / "prompt_full.txt"
    out_casual = contract_dir / "prompt_casual.txt"

    out_full.write_text(full_prompt_text, encoding="utf-8")
    out_casual.write_text(casual_prompt_text, encoding="utf-8")

    # Update SPEC_HASH
    sha = update_spec_hash_file()
    print(f"Generated {out_full} and {out_casual}")
    print(f"Updated SPEC_HASH: {sha}")


if __name__ == "__main__":
    build_prompts()
