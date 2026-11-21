"""Candidate spec_sha binding validator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from contract.spec_sha import compute_spec_sha


def get_current_spec_sha() -> str:
    """Retrieve current authoritative SPEC_HASH."""
    repo_root = Path(__file__).resolve().parent.parent
    hash_file = repo_root / "contract" / "SPEC_HASH"
    if hash_file.is_file():
        return hash_file.read_text(encoding="utf-8").strip()
    return compute_spec_sha()


def check_candidate_spec_binding(
    candidate_path: Path,
    current_spec_sha: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """Check whether candidate's metadata matches the current frozen contract spec_sha.

    Args:
        candidate_path: Path to the candidate python file.
        current_spec_sha: Optional precomputed spec_sha string.

    Returns:
        (is_valid, error_message): (True, None) if compliant/compatible or unversioned;
        (False, error_message) if candidate was generated against an older/different spec.
    """
    if current_spec_sha is None:
        current_spec_sha = get_current_spec_sha()

    cand_path = Path(candidate_path).resolve()
    # Check for adjacent .meta.json file (e.g. 1.meta.json or candidate.meta.json)
    meta_path = cand_path.with_suffix(".meta.json")
    if not meta_path.is_file():
        # Also check with .py.meta.json or in same directory
        alt_meta = cand_path.parent / f"{cand_path.stem}.meta.json"
        if alt_meta.is_file():
            meta_path = alt_meta
        else:
            # Trusted reference or hand-written mutant without generation metadata
            return True, None

    try:
        meta_data = json.loads(meta_path.read_text(encoding="utf-8"))
        cand_spec_sha = meta_data.get("spec_sha")
        if cand_spec_sha and cand_spec_sha != current_spec_sha:
            return False, (
                f"Candidate is STALE: candidate was generated against spec_sha '{cand_spec_sha}', "
                f"current spec_sha is '{current_spec_sha}'. Refusing execution."
            )
    except Exception as exc:
        return False, f"Failed to read candidate metadata '{meta_path}': {exc}"

    return True, None
