"""Judge retrieved You.com web evidence against payment specification rules."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import yaml

from generate.providers import get_provider, ProviderAdapter


OVERRIDES_FILE = Path("grounding/overrides.yaml")
CACHE_DIR = Path("grounding/cache")
VALID_LABELS = {"SUPPORTED", "PARTIAL", "NOT_FOUND", "CONFLICT"}


def load_overrides(overrides_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load human reviewer overrides from grounding/overrides.yaml if present."""
    path = overrides_path or OVERRIDES_FILE
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", data)


def validate_judge_verdict(
    verdict: Dict[str, Any],
    sources: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Enforce hard code-level constraints on model-assigned evidence judgments."""
    label = str(verdict.get("label", "NOT_FOUND")).strip().upper()
    if label not in VALID_LABELS:
        label = "NOT_FOUND"

    sources_used = verdict.get("sources_used") or []
    if not isinstance(sources_used, list):
        sources_used = []
    sources_used = [str(s).strip() for s in sources_used if str(s).strip()]

    quote = str(verdict.get("quote", "")).strip()
    reason = str(verdict.get("reason", "")).strip()

    valid_source_ids = {s.get("id") for s in sources if s.get("id")}
    snippets = [s.get("snippet", "") for s in sources if s.get("snippet")]

    # 1. Every sources_used id must exist
    for sid in sources_used:
        if sid not in valid_source_ids:
            label = "NOT_FOUND"
            reason = f"[Downgraded: source id '{sid}' not in retrieved sources] " + reason
            quote = ""
            sources_used = []
            break

    # 2. Quote verbatim substring and word cap
    if quote:
        words = quote.split()
        if len(words) > 25:
            label = "NOT_FOUND"
            reason = f"[Downgraded: quote length {len(words)} exceeds 25 words] " + reason
            quote = ""
        elif not any(quote in snip for snip in snippets):
            label = "NOT_FOUND"
            reason = "[Downgraded: quote is not a verbatim substring of retrieved snippets] " + reason
            quote = ""

    # 3. Convention check: rules with NOT_FOUND or no sources get convention = True
    convention = (label == "NOT_FOUND") or (len(sources) == 0)

    return {
        "label": label,
        "sources_used": sources_used,
        "quote": quote,
        "reason": reason,
        "convention": convention,
    }


def build_judge_prompt(
    rule_id: str,
    title: str,
    description: str,
    sources: List[Dict[str, Any]],
) -> str:
    """Format prompt for evaluating web search snippets against a specification rule."""
    sources_text = ""
    for s in sources:
        sources_text += f"\n- Source [{s['id']}]: {s['title']} ({s['url']})\n  Snippet: {s['snippet']}\n"

    return f"""You are an expert evaluator verifying financial payment gateway specifications.
Evaluate whether the retrieved documentation snippets support or conflict with the following specification rule.

RULE {rule_id}: {title}
Specification text:
{description}

RETRIEVED SOURCES:
{sources_text if sources else "(No sources retrieved)"}

INSTRUCTIONS:
1. Determine if the rule is SUPPORTED, PARTIAL, NOT_FOUND, or CONFLICT by the retrieved snippets.
2. Select only source ids that directly substantiate your decision.
3. If citing a quote, it MUST be a verbatim substring (max 25 words) from one of the snippets.
4. If no snippet directly supports the requirement, return NOT_FOUND.

Respond with strict JSON matching this schema:
{{
  "label": "SUPPORTED" | "PARTIAL" | "NOT_FOUND" | "CONFLICT",
  "sources_used": ["{rule_id}_s1"],
  "quote": "exact excerpt under 25 words",
  "reason": "concise explanation"
}}
"""


def rebuild_grounding_json(
    cache_dir: Path = CACHE_DIR,
    overrides_file: Optional[Path] = OVERRIDES_FILE,
    spec_hash_file: Path = Path("contract/SPEC_HASH"),
    output_file: Path = Path("runs/grounding.json"),
    default_label: str = "NOT_JUDGED",
) -> Dict[str, Any]:
    """Rebuild runs/grounding.json from cached search files and human overrides without calling a model."""
    spec_sha = ""
    if spec_hash_file.is_file():
        spec_sha = spec_hash_file.read_text(encoding="utf-8").strip()

    overrides = load_overrides(overrides_file)
    cache_files = sorted(cache_dir.glob("R*.json"), key=lambda p: int(p.stem[1:]))

    rules_out: Dict[str, Any] = {}

    for cpath in cache_files:
        with open(cpath, "r", encoding="utf-8") as f:
            cdata = json.load(f)

        rule_id = cdata.get("rule_id", cpath.stem)
        sources = cdata.get("sources", [])
        raw_responses = cdata.get("raw_responses", [])

        # Assertion: every source url must appear in stored raw responses
        raw_urls = set()
        for rr in raw_responses:
            resp_body = rr.get("response", {})
            for w in resp_body.get("results", {}).get("web", []):
                u = w.get("url")
                if u:
                    raw_urls.add(u)

        for src in sources:
            src_url = src.get("url")
            if src_url and src_url not in raw_urls:
                raise AssertionError(
                    f"Integrity check failed: source URL '{src_url}' in rule {rule_id} does not trace to any raw response."
                )

        has_sources = len(sources) > 0
        rule_override = overrides.get(rule_id, {})

        if rule_override:
            label = rule_override.get("label", default_label)
            human_reviewed = True
            convention = rule_override.get("convention", (label == "NOT_FOUND" or not has_sources))
            reason = rule_override.get("note", "Human reviewed override")
            quote = rule_override.get("quote", "")
            sources_used = rule_override.get("sources_used", [s["id"] for s in sources[:1]])
            judge_meta = {"model": "human_override", "temperature": None}
        else:
            label = default_label
            human_reviewed = False
            convention = not has_sources
            reason = ""
            quote = ""
            sources_used = []
            judge_meta = {"model": None, "temperature": None}

        rules_out[rule_id] = {
            "title": cdata.get("title", ""),
            "label": label,
            "convention": convention,
            "human_reviewed": human_reviewed,
            "sources": sources,
            "sources_used": sources_used,
            "quote": quote,
            "reason": reason,
            "judge": judge_meta,
        }

    output_data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "spec_sha": spec_sha,
        "provider": "you.com",
        "rules": rules_out,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    return output_data
