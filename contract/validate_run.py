"""Run JSON and Kill Matrix validator for PaySift contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def validate(run_dict: Dict[str, Any]) -> List[str]:
    """Validate a Run JSON dictionary against v1.1 contract schema.

    Returns a list of validation error messages. An empty list indicates success.
    """
    errors: List[str] = []

    if not isinstance(run_dict, dict):
        return ["Run data must be a JSON object"]

    # Top-level required keys
    required_keys = [
        "run_id",
        "contract_version",
        "spec_sha",
        "oracle_sha",
        "created_at",
        "candidate",
        "harness",
        "seeds",
        "results",
        "concurrency",
        "failures",
        "noncompliant",
        "repair_of",
    ]
    for key in required_keys:
        if key not in run_dict:
            errors.append(f"Missing required top-level key: '{key}'")

    # Candidate object
    cand = run_dict.get("candidate")
    if isinstance(cand, dict):
        for ckey in ["id", "model", "condition", "sample", "sha256", "source", "label"]:
            if ckey not in cand:
                errors.append(f"Missing candidate field: '{ckey}'")
        if cand.get("condition") not in ["A", "B", "-"]:
            errors.append(f"Invalid candidate condition: {cand.get('condition')}")
        valid_sources = ["live", "pre-run", "reference", "mutant", "extra-mutant", "stub"]
        if cand.get("source") not in valid_sources:
            errors.append(f"Invalid candidate source: {cand.get('source')}")
    elif cand is not None:
        errors.append("Field 'candidate' must be an object")

    # Harness object
    harness = run_dict.get("harness")
    if isinstance(harness, dict):
        if "mode_set" not in harness or not isinstance(harness["mode_set"], list):
            errors.append("Field 'harness.mode_set' must be a list of modes")
        if "docker" not in harness or not isinstance(harness["docker"], bool):
            errors.append("Field 'harness.docker' must be a boolean")
        if "cpus" not in harness or not isinstance(harness["cpus"], int):
            errors.append("Field 'harness.cpus' must be an integer")
    elif harness is not None:
        errors.append("Field 'harness' must be an object")

    # Seeds
    seeds = run_dict.get("seeds")
    if not (isinstance(seeds, list) and len(seeds) == 2 and all(isinstance(s, int) for s in seeds)):
        errors.append("Field 'seeds' must be a list of two integers [start, end]")

    # Results
    results = run_dict.get("results")
    if isinstance(results, dict):
        for inv in ["I1_signature", "I2_idempotency", "I3_conservation", "I4_bounds", "I5_interface"]:
            if inv not in results:
                errors.append(f"Missing invariant in results: '{inv}'")
            elif not isinstance(results[inv], dict):
                errors.append(f"Invariant '{inv}' in results must be an object")
    elif results is not None:
        errors.append("Field 'results' must be an object")

    # Concurrency
    conc = run_dict.get("concurrency")
    if isinstance(conc, dict):
        for sc in ["scenario_A", "scenario_B"]:
            if sc not in conc or not isinstance(conc[sc], dict):
                errors.append(f"Missing or invalid concurrency '{sc}'")
            else:
                for fld in ["trials", "failed", "warnings"]:
                    if fld not in conc[sc] or not isinstance(conc[sc][fld], int):
                        errors.append(f"Missing or invalid field '{fld}' in concurrency '{sc}'")
    elif conc is not None:
        errors.append("Field 'concurrency' must be an object")

    # Failures array
    failures = run_dict.get("failures")
    if isinstance(failures, list):
        for idx, fail in enumerate(failures):
            if not isinstance(fail, dict):
                errors.append(f"Failure at index {idx} must be an object")
                continue
            for fkey in [
                "invariant",
                "severity",
                "rule",
                "mode",
                "seed",
                "first_bad_step",
                "stream",
                "minimal_stream",
                "one_minimal",
                "shrink_history",
                "expected",
                "observed",
                "explanation",
                "classification",
            ]:
                if fkey not in fail:
                    errors.append(f"Failure at index {idx} missing field: '{fkey}'")

            if fail.get("severity") not in ["financial", "interface"]:
                errors.append(f"Failure at index {idx} has invalid severity: {fail.get('severity')}")

            classification = fail.get("classification")
            if isinstance(classification, dict):
                if classification.get("label") not in ["a", "b", "c", "d", "unreviewed"]:
                    errors.append(f"Failure at index {idx} classification label invalid")
                if classification.get("by") not in ["agent-proposed", "human"]:
                    errors.append(f"Failure at index {idx} classification by invalid")
            else:
                errors.append(f"Failure at index {idx} classification must be an object")
    elif failures is not None:
        errors.append("Field 'failures' must be a list")

    return errors


def validate_kill_matrix(km_dict: Dict[str, Any]) -> List[str]:
    """Validate a Kill Matrix JSON dictionary against specification.

    Kill Matrix shape:
      {
        "oracle_sha": str,
        "spec_sha": str,
        "created_at": str,
        "rows": [
          {
            "id": str,
            "label": str,
            "source": "reference" | "mutant" | "extra-mutant",
            "expected_rule": str,
            "expected_invariant": str,
            "results": dict,
            "concurrency": dict,
            "killed": bool,
            "rules_hit": list[str],
            "notes": str
          }
        ]
      }
    """
    errors: List[str] = []
    if not isinstance(km_dict, dict):
        return ["Kill matrix must be a JSON object"]

    for k in ["oracle_sha", "spec_sha", "created_at", "rows"]:
        if k not in km_dict:
            errors.append(f"Kill matrix missing required key: '{k}'")

    rows = km_dict.get("rows")
    if isinstance(rows, list):
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                errors.append(f"Kill matrix row {idx} must be an object")
                continue
            for rkey in [
                "id",
                "label",
                "source",
                "expected_rule",
                "expected_invariant",
                "results",
                "concurrency",
                "killed",
                "rules_hit",
                "notes",
            ]:
                if rkey not in row:
                    errors.append(f"Kill matrix row {idx} missing key '{rkey}'")
            if not isinstance(row.get("killed"), bool):
                errors.append(f"Kill matrix row {idx} 'killed' must be boolean")
            if not isinstance(row.get("rules_hit"), list):
                errors.append(f"Kill matrix row {idx} 'rules_hit' must be a list")
    elif rows is not None:
        errors.append("Kill matrix 'rows' must be a list")

    return errors
