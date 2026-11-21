"""Candidate generation orchestrator adhering to plan sections 10 & 11."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml

from contract.spec_sha import prompt_hash
from generate.intake import intake_candidate
from generate.providers import (
    GenerationResult,
    ProviderAdapter,
    get_provider,
    load_env_file,
    scrub_secrets,
)
from generate.spec_binding import get_current_spec_sha


def load_models_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load and parse config/models.yaml."""
    if config_path is None:
        config_path = Path(__file__).resolve().parent.parent / "config" / "models.yaml"

    if not config_path.is_file():
        return {
            "max_total_api_calls": 120,
            "repair_reserved_calls": 10,
            "samples_per_model_per_condition": 5,
            "temperature": None,
            "max_output_tokens": 4000,
            "models": [],
        }

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def get_model_status(model_cfg: Dict[str, Any]) -> Tuple[bool, str]:
    """Check if a model configuration is usable.

    Returns (is_usable, reason).
    """
    model_id = str(model_cfg.get("model_id", "")).strip()
    if not model_id or model_id == "FILL_ME":
        return False, "model_id is FILL_ME or empty"

    key_env = model_cfg.get("api_key_env", "")
    if key_env:
        val = os.environ.get(key_env, "").strip()
        if not val or val == "FILL_ME":
            return False, f"environment variable '{key_env}' is unset"

    return True, "usable"


def record_needs_human_missing_configs(unusable_models: List[Tuple[Dict[str, Any], str]]) -> None:
    """Record missing model configurations in NEEDS_HUMAN.md without leaking secrets."""
    repo_root = Path(__file__).resolve().parent.parent
    nh_path = repo_root / "NEEDS_HUMAN.md"

    if not unusable_models:
        return

    content = nh_path.read_text(encoding="utf-8") if nh_path.is_file() else ""

    lines_to_add = []
    for model_cfg, reason in unusable_models:
        name = model_cfg.get("name", "unknown")
        key_var = model_cfg.get("api_key_env", "UNKNOWN_KEY_VAR")
        marker = f"NH-CFG-{name.upper()}"
        if marker not in content:
            lines_to_add.append(
                f"- [{marker}] Model '{name}': {reason}. Please set environment variable `{key_var}` "
                f"or configure a valid model_id in config/models.yaml."
            )

    if lines_to_add:
        block = "\n### Model Configuration Notice (P7)\n" + "\n".join(lines_to_add) + "\n"
        nh_path.write_text(content.rstrip() + "\n" + block, encoding="utf-8")


def generate_candidate(
    provider: ProviderAdapter,
    prompt: str,
    model_id: str,
    condition: str,
    sample_num: int,
    output_dir: Path,
    spec_sha: str,
    p_hash: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: Optional[float] = None,
    max_output_tokens: int = 4000,
    call_counter: Optional[List[int]] = None,
    max_allowed_calls: int = 110,
) -> Dict[str, Any]:
    """Generate a single candidate with up to 2 extra AST gate regenerations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    py_path = output_dir / f"{sample_num}.py"
    raw_path = output_dir / f"{sample_num}.raw.txt"
    meta_path = output_dir / f"{sample_num}.meta.json"

    regeneration_count = 0
    all_attempts: List[Dict[str, Any]] = []
    total_token_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    final_code = ""
    final_raw = ""
    is_compliant = False
    violations: List[Dict[str, Any]] = []

    while regeneration_count <= 2:
        if call_counter is not None:
            if call_counter[0] >= max_allowed_calls:
                raise RuntimeError(
                    f"Global API call cap reached ({call_counter[0]}/{max_allowed_calls} calls). Halting."
                )
            call_counter[0] += 1

        gen_res = provider.generate(
            prompt=prompt,
            model_id=model_id,
            temperature=temperature,
            max_tokens=max_output_tokens,
            api_key=api_key,
            base_url=base_url,
        )

        all_attempts.extend(gen_res.attempts)
        for k in total_token_usage:
            total_token_usage[k] += gen_res.token_usage.get(k, 0)

        final_raw = gen_res.raw_text
        intake_res = intake_candidate(final_raw)
        final_code = intake_res["code"]
        is_compliant = intake_res["compliant"]
        violations = intake_res["violations"]

        if is_compliant:
            break

        if regeneration_count < 2:
            regeneration_count += 1
        else:
            break

    # Write files
    py_path.write_text(final_code, encoding="utf-8")
    raw_path.write_text(final_raw, encoding="utf-8")

    code_sha = hashlib.sha256(final_code.encode("utf-8")).hexdigest()
    now_iso = datetime.now(timezone.utc).isoformat()

    meta_dict = {
        "model": model_id,
        "provider": provider.provider_name,
        "condition": condition,
        "sample": sample_num,
        "attempt_log": all_attempts,
        "sha256": code_sha,
        "timestamp": now_iso,
        "spec_sha": spec_sha,
        "prompt_hash": p_hash,
        "temperature": temperature,
        "token_usage": total_token_usage,
        "compliant": is_compliant,
        "violations": violations,
        "regeneration_count": regeneration_count,
    }

    meta_path.write_text(json.dumps(meta_dict, indent=2), encoding="utf-8")
    return meta_dict


def run_generation_pipeline(
    config: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
    limit: Optional[int] = None,
    filter_models: Optional[List[str]] = None,
    stale_only: bool = False,
    regen_all: bool = False,
    custom_provider: Optional[ProviderAdapter] = None,
) -> Dict[str, Any]:
    """Execute candidate generation pipeline across all configured and usable models."""
    repo_root = Path(__file__).resolve().parent.parent
    load_env_file(repo_root / ".env")

    if config is None:
        config = load_models_config()

    spec_sha = get_current_spec_sha()

    prompt_full_file = repo_root / "contract" / "prompt_full.txt"
    prompt_casual_file = repo_root / "contract" / "prompt_casual.txt"
    prompt_full = prompt_full_file.read_text(encoding="utf-8") if prompt_full_file.is_file() else ""
    prompt_casual = prompt_casual_file.read_text(encoding="utf-8") if prompt_casual_file.is_file() else ""

    p_hash_a = prompt_hash(prompt_full)
    p_hash_b = prompt_hash(prompt_casual)

    max_total_calls = config.get("max_total_api_calls", 120)
    repair_reserved = config.get("repair_reserved_calls", 10)
    max_gen_calls = max_total_calls - repair_reserved
    samples_per = config.get("samples_per_model_per_condition", 5)
    default_temp = config.get("temperature", None)
    max_tokens = config.get("max_output_tokens", 4000)

    models = config.get("models", [])
    if filter_models:
        models = [m for m in models if m.get("name") in filter_models or m.get("model_id") in filter_models]

    usable_models = []
    unusable_models = []
    for m in models:
        usable, reason = get_model_status(m)
        if usable:
            usable_models.append(m)
        else:
            unusable_models.append((m, reason))

    # Log missing models to NEEDS_HUMAN.md
    if unusable_models:
        record_needs_human_missing_configs(unusable_models)

    candidates_dir = repo_root / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    if regen_all and not dry_run:
        # Move existing candidates to candidates/_stale/<old_spec_sha>/
        stale_dir = candidates_dir / "_stale" / spec_sha[:12]
        stale_dir.mkdir(parents=True, exist_ok=True)
        for child in list(candidates_dir.iterdir()):
            if child.is_dir() and child.name != "_stale":
                shutil.move(str(child), str(stale_dir / child.name))

    # Prepare execution plan
    plan: List[Dict[str, Any]] = []
    for m in usable_models:
        m_name = m.get("name", m.get("model_id", "unnamed"))
        m_id = m.get("model_id", "")
        prov_name = m.get("provider", "openai")
        key_var = m.get("api_key_env", "")
        api_key = os.environ.get(key_var, "") if key_var else None
        base_url = m.get("base_url")

        for cond, prompt_text, p_hash in [("A", prompt_full, p_hash_a), ("B", prompt_casual, p_hash_b)]:
            out_dir = candidates_dir / m_name / cond
            for s_idx in range(1, samples_per + 1):
                py_f = out_dir / f"{s_idx}.py"
                meta_f = out_dir / f"{s_idx}.meta.json"

                if stale_only and py_f.is_file() and meta_f.is_file():
                    try:
                        m_data = json.loads(meta_f.read_text(encoding="utf-8"))
                        if m_data.get("spec_sha") == spec_sha:
                            continue
                    except Exception:
                        pass

                plan.append({
                    "model_cfg": m,
                    "model_name": m_name,
                    "model_id": m_id,
                    "provider_name": prov_name,
                    "condition": cond,
                    "sample": s_idx,
                    "prompt": prompt_text,
                    "prompt_hash": p_hash,
                    "api_key": api_key,
                    "base_url": base_url,
                    "out_dir": out_dir,
                })

    if limit is not None and limit > 0:
        plan = plan[:limit]

    print("=================================================================")
    print(" PaySift Candidate Generation Plan")
    print("=================================================================")
    print(f" Usable Models        : {len(usable_models)} ({', '.join(m.get('name', '') for m in usable_models) or 'none'})")
    print(f" Unusable Models      : {len(unusable_models)} (details logged to NEEDS_HUMAN.md)")
    print(f" Planned Candidates   : {len(plan)}")
    print(f" Global Call Cap      : {max_gen_calls} calls ({repair_reserved} reserved for repair)")
    print(f" Dry Run Mode         : {dry_run}")
    print("-----------------------------------------------------------------")

    call_counter = [0]
    results: List[Dict[str, Any]] = []

    if dry_run or not plan:
        summary_md = generate_summary_markdown(usable_models, unusable_models, plan, results, call_counter[0], max_gen_calls, dry_run=True)
        summary_path = candidates_dir / "GENERATION_SUMMARY.md"
        summary_path.write_text(summary_md, encoding="utf-8")
        return {
            "usable_models": usable_models,
            "unusable_models": unusable_models,
            "plan_length": len(plan),
            "generated": 0,
            "calls_used": 0,
        }

    for item in plan:
        if call_counter[0] >= max_gen_calls:
            print(f"Warning: Global call cap of {max_gen_calls} reached. Halting generation.")
            break

        prov = custom_provider or get_provider(item["provider_name"])
        try:
            meta = generate_candidate(
                provider=prov,
                prompt=item["prompt"],
                model_id=item["model_id"],
                condition=item["condition"],
                sample_num=item["sample"],
                output_dir=item["out_dir"],
                spec_sha=spec_sha,
                p_hash=item["prompt_hash"],
                api_key=item["api_key"],
                base_url=item["base_url"],
                temperature=default_temp,
                max_output_tokens=max_tokens,
                call_counter=call_counter,
                max_allowed_calls=max_gen_calls,
            )
            results.append(meta)
            status_str = "COMPLIANT" if meta["compliant"] else f"NON-COMPLIANT ({len(meta['violations'])} violations)"
            print(f"[{item['model_name']}][Cond {item['condition']}][Sample {item['sample']}] -> {status_str} (calls used: {call_counter[0]}/{max_gen_calls})")
        except Exception as exc:
            scrubbed_err = scrub_secrets(str(exc), [item["api_key"] or ""])
            print(f"Error generating [{item['model_name']}][Cond {item['condition']}][Sample {item['sample']}]: {scrubbed_err}", file=sys.stderr)

    summary_md = generate_summary_markdown(usable_models, unusable_models, plan, results, call_counter[0], max_gen_calls, dry_run=False)
    summary_path = candidates_dir / "GENERATION_SUMMARY.md"
    summary_path.write_text(summary_md, encoding="utf-8")

    return {
        "usable_models": usable_models,
        "unusable_models": unusable_models,
        "plan_length": len(plan),
        "generated": len(results),
        "calls_used": call_counter[0],
    }


def generate_summary_markdown(
    usable_models: List[Dict[str, Any]],
    unusable_models: List[Tuple[Dict[str, Any], str]],
    plan: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    calls_used: int,
    max_calls: int,
    dry_run: bool = False,
) -> str:
    """Render markdown table summarizing candidate generation results."""
    now_iso = datetime.now(timezone.utc).isoformat()
    lines = [
        "# PaySift Candidate Generation Summary",
        "",
        f"- **Timestamp:** `{now_iso}`",
        f"- **API Calls Used:** `{calls_used} / {max_calls}`",
        f"- **Dry Run:** `{dry_run}`",
        "",
        "## Model Configuration Status",
        "",
        "| Model Name | Provider | Model ID | Status | Reason |",
        "|---|---|---|---|---|",
    ]

    for m in usable_models:
        lines.append(f"| `{m.get('name')}` | `{m.get('provider')}` | `{m.get('model_id')}` | **USABLE** | Configured and ready |")
    for m, reason in unusable_models:
        lines.append(f"| `{m.get('name')}` | `{m.get('provider')}` | `{m.get('model_id')}` | **UNUSABLE** | {reason} |")

    lines.extend([
        "",
        "## Generation Results by Model & Condition",
        "",
        "| Model | Condition | Planned | Generated | Compliant | Non-Compliant | Regenerations |",
        "|---|---|---|---|---|---|---|",
    ])

    # Tally by (model, condition)
    tally: Dict[Tuple[str, str], Dict[str, int]] = {}
    for p in plan:
        key = (p["model_name"], p["condition"])
        if key not in tally:
            tally[key] = {"planned": 0, "generated": 0, "compliant": 0, "noncompliant": 0, "regens": 0}
        tally[key]["planned"] += 1

    for r in results:
        key = (r["model"], r["condition"])
        if key not in tally:
            tally[key] = {"planned": 0, "generated": 0, "compliant": 0, "noncompliant": 0, "regens": 0}
        tally[key]["generated"] += 1
        if r["compliant"]:
            tally[key]["compliant"] += 1
        else:
            tally[key]["noncompliant"] += 1
        tally[key]["regens"] += r.get("regeneration_count", 0)

    if not tally:
        lines.append("| `-` | `-` | 0 | 0 | 0 | 0 | 0 |")
    else:
        for (m_name, cond), stats in sorted(tally.items()):
            lines.append(
                f"| `{m_name}` | `{cond}` | {stats['planned']} | {stats['generated']} | {stats['compliant']} | {stats['noncompliant']} | {stats['regens']} |"
            )

    lines.append("")
    return "\n".join(lines)
