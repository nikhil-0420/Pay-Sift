"""Validator for runs/grounding.json conforming to contract/grounding_schema.json."""

from __future__ import annotations

import re
from typing import Any, Dict, List

VALID_RULE_ID_PATTERN = re.compile(r"^R(10|[0-9])$")
VALID_LABELS = {"SUPPORTED", "PARTIAL", "NOT_FOUND", "CONFLICT", "NOT_JUDGED"}
REQUIRED_SOURCE_KEYS = {"id", "url", "title", "snippet", "rank", "query", "retrieved_at", "provider"}
REQUIRED_RULE_KEYS = {"label", "convention", "human_reviewed", "sources", "quote", "reason", "judge"}


def validate_grounding(data: Dict[str, Any]) -> List[str]:
    """Validate runs/grounding.json dictionary structure and integrity.
    
    Returns a list of error strings; an empty list indicates full compliance.
    """
    errors: List[str] = []

    if not isinstance(data, dict):
        return ["Grounding data must be a JSON object"]

    for top_key in ("generated_at", "spec_sha", "provider", "rules"):
        if top_key not in data:
            errors.append(f"Missing required top-level key: '{top_key}'")

    if data.get("provider") != "you.com":
        errors.append(f"Invalid provider: '{data.get('provider')}'; expected 'you.com'")

    rules = data.get("rules")
    if not isinstance(rules, dict):
        errors.append("'rules' field must be a JSON object mapping rule IDs to rule objects")
        return errors

    for rule_id, rdata in rules.items():
        if not VALID_RULE_ID_PATTERN.match(rule_id):
            errors.append(f"Invalid rule ID: '{rule_id}'; must match ^R(10|[0-9])$")
            continue

        if not isinstance(rdata, dict):
            errors.append(f"Rule data for '{rule_id}' must be an object")
            continue

        for rkey in REQUIRED_RULE_KEYS:
            if rkey not in rdata:
                errors.append(f"Rule '{rule_id}' missing required field: '{rkey}'")

        label = rdata.get("label")
        if label not in VALID_LABELS:
            errors.append(f"Rule '{rule_id}' has invalid label: '{label}'")

        if not isinstance(rdata.get("convention"), bool):
            errors.append(f"Rule '{rule_id}' field 'convention' must be a boolean")

        if not isinstance(rdata.get("human_reviewed"), bool):
            errors.append(f"Rule '{rule_id}' field 'human_reviewed' must be a boolean")

        sources = rdata.get("sources")
        if not isinstance(sources, list):
            errors.append(f"Rule '{rule_id}' field 'sources' must be an array")
        else:
            for idx, src in enumerate(sources):
                if not isinstance(src, dict):
                    errors.append(f"Rule '{rule_id}' source at index {idx} must be an object")
                    continue
                for skey in REQUIRED_SOURCE_KEYS:
                    if skey not in src:
                        errors.append(f"Rule '{rule_id}' source {idx} missing key '{skey}'")

        judge = rdata.get("judge")
        if not isinstance(judge, dict):
            errors.append(f"Rule '{rule_id}' field 'judge' must be an object")

    return errors
