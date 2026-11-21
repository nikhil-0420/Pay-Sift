"""Judge retrieved You.com web evidence against payment specification rules."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
import yaml

from generate.providers import get_provider, load_env_file, ProviderAdapter
from grounding.validator import validate_grounding


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
        sources_text += f"\n- Source [{s.get('id', '')}]: {s.get('title', '')} ({s.get('url', '')})\n  Snippet: {s.get('snippet', '')}\n"

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


REQUIRED_JUDGE_KEYS = {"label", "sources_used", "quote", "reason"}
RETRY_INSTRUCTION = "\n\nCRITICAL: reply with only the JSON object, no prose, no code fences."


def extract_first_balanced_json(text: str) -> Optional[str]:
    """Find and return the substring of the first balanced {...} block in text."""
    start_idx = text.find("{")
    if start_idx == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start_idx, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if not in_string:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start_idx : i + 1]
    return None


def parse_judge_output(raw_text: str) -> Optional[Dict[str, Any]]:
    """Parse and validate required structure from LLM judge output."""
    if not raw_text or not isinstance(raw_text, str):
        return None

    cleaned = raw_text.strip()
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
    candidate_text = fence_match.group(1).strip() if fence_match else cleaned

    # Extract first balanced JSON object
    json_str = extract_first_balanced_json(candidate_text)
    if not json_str:
        json_str = extract_first_balanced_json(cleaned)
        if not json_str:
            return None

    try:
        data = json.loads(json_str)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    # Verify required keys
    if not REQUIRED_JUDGE_KEYS.issubset(data.keys()):
        return None

    label = str(data.get("label", "")).strip().upper()
    if label not in VALID_LABELS:
        return None

    if not isinstance(data.get("sources_used"), list):
        return None

    if not isinstance(data.get("quote"), str):
        return None

    if not isinstance(data.get("reason"), str):
        return None

    return {
        "label": label,
        "sources_used": [str(s).strip() for s in data["sources_used"] if str(s).strip()],
        "quote": data["quote"].strip(),
        "reason": data["reason"].strip(),
    }


def extract_json_verdict(raw_text: str) -> Dict[str, Any]:
    """Extract and parse JSON object from raw LLM output text, returning fallback dict on failure."""
    parsed = parse_judge_output(raw_text)
    if parsed is not None:
        return parsed
    return {
        "label": "NOT_FOUND",
        "sources_used": [],
        "quote": "",
        "reason": "Failed to parse model JSON output",
    }


def judge_single_rule(
    adapter: Any,
    rule_id: str,
    title: str,
    description: str,
    sources: List[Dict[str, Any]],
    model_id: str,
    api_key: str,
    base_url: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 1000,
    cache_dir: Optional[Path] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any], int]:
    """Execute model evaluation for a single rule with single-retry fallback on parse failure."""
    prompt = build_judge_prompt(rule_id, title, description, sources)
    calls_made = 1

    res = adapter.generate(
        prompt=prompt,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        api_key=api_key,
        base_url=base_url,
    )
    final_res = res

    # Save debug raw file if cache_dir is provided
    if cache_dir:
        raw_debug_file = cache_dir / f"{rule_id}.judge_raw.txt"
        try:
            raw_debug_file.write_text(res.raw_text, encoding="utf-8")
        except Exception:
            pass

    verdict = parse_judge_output(res.raw_text)

    # Retry once if parsing failed
    if verdict is None:
        retry_prompt = prompt + RETRY_INSTRUCTION
        retry_res = adapter.generate(
            prompt=retry_prompt,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
        )
        calls_made += 1
        final_res = retry_res

        if cache_dir:
            raw_debug_file = cache_dir / f"{rule_id}.judge_raw.txt"
            try:
                raw_debug_file.write_text(retry_res.raw_text, encoding="utf-8")
            except Exception:
                pass

        verdict = parse_judge_output(retry_res.raw_text)
        if verdict is None:
            verdict = {
                "label": "NOT_FOUND",
                "sources_used": [],
                "quote": "",
                "reason": "Judge output unparseable after retry",
            }

    validated = validate_judge_verdict(verdict, sources)
    meta = {
        "model": model_id,
        "temperature": temperature,
        "token_usage": getattr(final_res, "token_usage", None),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return validated, meta, calls_made


def run_judge(
    rules: Optional[List[str]] = None,
    models_config_path: Path = Path("config/models.yaml"),
    cache_dir: Path = CACHE_DIR,
    output_file: Path = Path("runs/grounding.json"),
    spec_hash_file: Path = Path("contract/SPEC_HASH"),
) -> Dict[str, Any]:
    """Execute LLM evidence judge across rules using the configured model."""
    load_env_file()
    if not models_config_path.is_file():
        raise FileNotFoundError(f"Models config file not found: {models_config_path}")

    with open(models_config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    # Determine judge model and provider
    judge_model_id = cfg.get("judge_model_id") or "gemini-3.5-flash-lite"
    provider_name = "google"
    api_key_env = "GEMINI_API_KEY"
    base_url = None

    for m in cfg.get("models", []):
        if m.get("model_id") == judge_model_id or m.get("name") == "strong_a":
            provider_name = m.get("provider", "google")
            judge_model_id = m.get("model_id", judge_model_id)
            api_key_env = m.get("api_key_env", "GEMINI_API_KEY")
            base_url = m.get("base_url")
            break

    api_key = os.environ.get(api_key_env, "").strip()
    if not api_key:
        raise ValueError(f"API key {api_key_env} is not set in environment or .env.")

    adapter = get_provider(provider_name)

    cache_files = sorted(cache_dir.glob("R*.json"), key=lambda p: int(p.stem[1:]))
    if rules:
        target_rule_set = set(rules)
        cache_files = [cf for cf in cache_files if cf.stem in target_rule_set]

    label_counts: Dict[str, int] = {"SUPPORTED": 0, "PARTIAL": 0, "NOT_FOUND": 0, "CONFLICT": 0}
    model_calls_used = 0

    for cf in cache_files:
        with open(cf, "r", encoding="utf-8") as f:
            cdata = json.load(f)

        rule_id = cdata.get("rule_id", cf.stem)
        title = cdata.get("title", "")
        description = cdata.get("description", "")
        sources = cdata.get("sources", [])

        validated_verdict, judge_meta, calls = judge_single_rule(
            adapter=adapter,
            rule_id=rule_id,
            title=title,
            description=description,
            sources=sources,
            model_id=judge_model_id,
            api_key=api_key,
            base_url=base_url,
            temperature=0.0,
            max_tokens=1000,
            cache_dir=cache_dir,
        )
        model_calls_used += calls

        cdata["judge_verdict"] = validated_verdict
        cdata["judge_meta"] = judge_meta

        # Write back to cache file
        with open(cf, "w", encoding="utf-8") as f:
            json.dump(cdata, f, indent=2)

        lbl = validated_verdict["label"]
        label_counts[lbl] = label_counts.get(lbl, 0) + 1

    # Rebuild runs/grounding.json
    grounding_data = rebuild_grounding_json(
        cache_dir=cache_dir,
        spec_hash_file=spec_hash_file,
        output_file=output_file,
    )

    errs = validate_grounding(grounding_data)
    if errs:
        raise ValueError(f"Grounding validation failed after judge execution: {errs}")

    return {
        "judge_model": judge_model_id,
        "label_counts": label_counts,
        "model_calls_used": model_calls_used,
        "data": grounding_data,
    }


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
        cached_verdict = cdata.get("judge_verdict")
        cached_judge_meta = cdata.get("judge_meta")

        if rule_override:
            label = rule_override.get("label", default_label)
            human_reviewed = True
            convention = rule_override.get("convention", (label == "NOT_FOUND" or not has_sources))
            reason = rule_override.get("note", "Human reviewed override")
            quote = rule_override.get("quote", "")
            sources_used = rule_override.get("sources_used", [s["id"] for s in sources[:1]])
            judge_meta = {"model": "human_override", "temperature": None}
        elif cached_verdict:
            label = cached_verdict.get("label", default_label)
            human_reviewed = False
            convention = cached_verdict.get("convention", (label == "NOT_FOUND" or not has_sources))
            reason = cached_verdict.get("reason", "")
            quote = cached_verdict.get("quote", "")
            sources_used = cached_verdict.get("sources_used", [])
            judge_meta = cached_judge_meta or {"model": None, "temperature": None}
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
