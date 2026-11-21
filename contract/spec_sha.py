"""Contract specification SHA-256 and prompt hash computations."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional


def compute_spec_sha(spec_path: Optional[Path] = None, schema_path: Optional[Path] = None) -> str:
    """Compute deterministic SHA-256 over LF-normalized bytes of SPEC.md then schema.sql."""
    root = Path(__file__).resolve().parent
    if spec_path is None:
        spec_path = root / "SPEC.md"
    if schema_path is None:
        schema_path = root / "schema.sql"

    spec_text = spec_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    schema_text = schema_path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")

    hasher = hashlib.sha256()
    hasher.update(spec_text.encode("utf-8"))
    hasher.update(schema_text.encode("utf-8"))
    return hasher.hexdigest()


def prompt_hash(prompt_text: str) -> str:
    """Compute deterministic SHA-256 over LF-normalized prompt text."""
    normalized = prompt_text.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def update_spec_hash_file() -> str:
    """Compute spec_sha and write to contract/SPEC_HASH."""
    root = Path(__file__).resolve().parent
    spec_path = root / "SPEC.md"
    schema_path = root / "schema.sql"
    hash_file = root / "SPEC_HASH"

    sha = compute_spec_sha(spec_path, schema_path)
    hash_file.write_text(sha.strip() + "\n", encoding="utf-8")
    return sha


if __name__ == "__main__":
    sha = update_spec_hash_file()
    print(f"Updated contract/SPEC_HASH: {sha}")
