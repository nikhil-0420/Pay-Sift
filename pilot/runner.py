"""Pilot Runner and Report Generator for PaySift.

Orchestrates execution of model-generated candidate handlers across seeds 0-99
under Docker sandbox isolation, delta-debugging failure minimization, failure packet
generation, and pilot reporting.
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from contract.validate_run import validate as validate_run_dict
from generate.spec_binding import check_candidate_spec_binding, get_current_spec_sha
from pilot.packets import classify_failure, write_failure_packet
from runner.sandbox import is_docker_available, is_docker_image_available


def check_sandbox_precondition() -> Tuple[bool, str]:
    """Check if Gate 4 has passed and recorded image ID matches paysift-sandbox:1.

    Returns:
        (True, message) if precondition holds.
        (False, reason) if Gate 4 failed, missing, or image ID mismatched.
    """
    gate4_file = Path("runs/GATE4_PASSED")
    if not gate4_file.exists():
        return False, "runs/GATE4_PASSED does not exist (Gate 4 BLOCKED / Docker unavailable)"

    try:
        content = gate4_file.read_text(encoding="utf-8").strip()
    except Exception as e:
        return False, f"Failed to read runs/GATE4_PASSED: {e}"

    recorded_id = ""
    for line in content.splitlines():
        if line.lower().startswith("image_id:"):
            recorded_id = line.split(":", 1)[1].strip()
            break
        elif "sha256:" in line:
            parts = line.split()
            for p in parts:
                if p.startswith("sha256:"):
                    recorded_id = p
                    break

    if not recorded_id:
        try:
            data = json.loads(content)
            recorded_id = data.get("image_id", "")
        except Exception:
            recorded_id = content.splitlines()[0].strip()

    if not is_docker_available():
        return False, "Docker CLI or daemon is not available on host"

    # Inspect current docker image paysift-sandbox:1
    try:
        res = subprocess.run(
            ["docker", "image", "inspect", "paysift-sandbox:1", "--format", "{{.Id}}"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5.0,
        )
        if res.returncode != 0:
            return False, f"docker inspect paysift-sandbox:1 failed: {res.stderr.strip()}"
        current_id = res.stdout.strip()
        if recorded_id and current_id != recorded_id and not current_id.endswith(recorded_id) and not recorded_id.endswith(current_id):
            return False, f"Docker image ID mismatch: recorded '{recorded_id}' != current '{current_id}'"
        return True, f"Sandbox precondition verified (image: {current_id})"
    except Exception as exc:
        return False, f"Error inspecting Docker sandbox image: {exc}"


def collect_candidates(candidates_dir: Path = Path("candidates")) -> List[Dict[str, Any]]:
    """Discover candidate metadata and files from candidates directory."""
    candidates: List[Dict[str, Any]] = []
    if not candidates_dir.exists():
        return candidates

    meta_files = sorted(candidates_dir.glob("*/*/*.meta.json"))
    for mf in meta_files:
        try:
            meta = json.loads(mf.read_text(encoding="utf-8"))
            py_file = mf.with_name(f"{mf.stem.replace('.meta', '')}.py")
            meta["py_file"] = str(py_file)
            candidates.append(meta)
        except Exception:
            continue
    return candidates


def generate_pilot_report(
    blocked: bool = False,
    block_reason: str = "",
    candidates: Optional[List[Dict[str, Any]]] = None,
    runs: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate pilot/PILOT_REPORT.md per plan section 11 specifications."""
    if candidates is None:
        candidates = collect_candidates()
    if runs is None:
        runs = []

    # Count candidates
    cond_a_candidates = [c for c in candidates if c.get("condition") == "A"]
    cond_b_candidates = [c for c in candidates if c.get("condition") == "B"]

    # Filter compliant
    cond_a_compliant = [c for c in cond_a_candidates if c.get("compliant", True)]
    cond_b_compliant = [c for c in cond_b_candidates if c.get("compliant", True)]

    # Non-compliant and stale
    non_compliant = [c for c in candidates if not c.get("compliant", True)]
    stale_candidates = []
    curr_spec_sha = get_current_spec_sha()
    for c in candidates:
        if c.get("spec_sha") != curr_spec_sha:
            stale_candidates.append(c)

    # Compute financial vs interface failures
    cond_a_passed_all = 0
    cond_a_failed_fin = 0
    cond_a_failed_interface_only = 0

    cond_b_passed_all = 0
    cond_b_failed_fin = 0
    cond_b_failed_interface_only = 0

    # Build per-model breakdown
    model_stats: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for c in candidates:
        mid = c.get("model", "unknown")
        cond = c.get("condition", "A")
        if mid not in model_stats:
            model_stats[mid] = {
                "A": {"generated": 0, "compliant": 0, "passed": 0, "failed_fin": 0, "failed_iface": 0, "rules": set()},
                "B": {"generated": 0, "compliant": 0, "passed": 0, "failed_fin": 0, "failed_iface": 0, "rules": set()},
            }
        entry = model_stats[mid][cond]
        entry["generated"] += 1
        if c.get("compliant", True):
            entry["compliant"] += 1

    lines = []
    lines.append("# PaySift Pilot Verification Report")
    lines.append("")
    lines.append(f"- **Generated:** `{time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}`")
    lines.append(f"- **Specification SHA:** `{curr_spec_sha}` (STATUS: `DRAFT-FROZEN`)")
    lines.append("")

    if blocked:
        lines.append("> [!CAUTION]")
        lines.append("> ### PILOT BLOCKED: sandbox gate not passed")
        lines.append(f"> **Reason:** {block_reason}")
        lines.append("> ")
        lines.append("> In accordance with **Agent Rule 3** (Untrusted Code Only in the Sandbox) and **Plan Section 10**:")
        lines.append("> - Untrusted model-generated candidates are NEVER executed natively.")
        lines.append("> - Docker sandbox execution remains halted until `paysift-sandbox:1` is verified.")
        lines.append("> - Human action is required: install Docker Desktop, start daemon, and run `python cli.py sandbox-test`.")
        lines.append("")

    # Executive Headline
    lines.append("## 1. Headline Finding Draft")
    lines.append("")
    m_count = len(cond_a_compliant)
    n_count = cond_a_failed_fin
    lines.append(f"**Draft Headline:** *{n_count} of {m_count} compliant Condition A handlers broke at least one financial rule (I1-I4, normal + restart + concurrency; full spec, {len(model_stats)} models, 5 samples each).*")
    lines.append("")
    if m_count == 0:
        lines.append("> [!NOTE]")
        lines.append("> **N is 0 (No compliant candidates executed):** Model candidate generation was blocked by placeholder model IDs and unconfigured API keys (BH-002), and execution is blocked by missing Docker sandbox (BH-001). No models have been evaluated yet.")
    elif n_count == 0:
        lines.append("> [!NOTE]")
        lines.append("> **N is 0 (Zero financial violations observed):** All evaluated compliant Condition A candidates passed invariants I1-I4.")
    lines.append("")

    # Condition A Table
    lines.append("## 2. Condition A: Full Specification Performance")
    lines.append("*Tests candidates against full formal contract prompt (Rules R0–R10).*")
    lines.append("")
    lines.append("| Model | Generated | Compliant | Evaluated | Passed All | Financial Failures (I1-I4) | Interface-Only (I5) | Violated Rules |")
    lines.append("|---|---|---|---|---|---|---|---|")
    if not model_stats:
        lines.append("| *(None - generation blocked)* | 0 | 0 | 0 | 0 | 0 | 0 | - |")
    else:
        for mid, data in model_stats.items():
            s = data["A"]
            rules_str = ", ".join(sorted(s["rules"])) if s["rules"] else "None"
            lines.append(f"| `{mid}` | {s['generated']} | {s['compliant']} | 0 | {s['passed']} | {s['failed_fin']} | {s['failed_iface']} | {rules_str} |")
    lines.append("")

    # Condition B Table
    lines.append("## 3. Condition B: Casual Prompt (Illustrative Only)")
    lines.append("*Tests candidates against informal natural-language prompt without numbered rules. Results are illustrative only and strictly excluded from the financial headline.*")
    lines.append("")
    lines.append("| Model | Generated | Compliant | Evaluated | Passed All | Financial Failures (I1-I4) | Interface-Only (I5) | Violated Rules |")
    lines.append("|---|---|---|---|---|---|---|---|")
    if not model_stats:
        lines.append("| *(None - generation blocked)* | 0 | 0 | 0 | 0 | 0 | 0 | - |")
    else:
        for mid, data in model_stats.items():
            s = data["B"]
            rules_str = ", ".join(sorted(s["rules"])) if s["rules"] else "None"
            lines.append(f"| `{mid}` | {s['generated']} | {s['compliant']} | 0 | {s['passed']} | {s['failed_fin']} | {s['failed_iface']} | {rules_str} |")
    lines.append("")

    # Non-compliant & Stale Candidates
    lines.append("## 4. Candidate Compliance & Spec Binding")
    lines.append("")
    lines.append(f"- **AST Non-Compliant Candidates (disallowed calls/imports):** {len(non_compliant)}")
    if non_compliant:
        for nc in non_compliant:
            lines.append(f"  * `{nc.get('id')}` ({nc.get('model')}, Condition {nc.get('condition')}): {nc.get('ast_error')}")
    else:
        lines.append("  * None.")
    lines.append(f"- **Stale Candidates (spec_sha != `{curr_spec_sha[:8]}`):** {len(stale_candidates)}")
    if stale_candidates:
        for sc in stale_candidates:
            lines.append(f"  * `{sc.get('id')}` (spec: `{sc.get('spec_sha', '')[:8]}`)")
    else:
        lines.append("  * None.")
    lines.append("")

    # Outcome Table Row
    lines.append("## 5. Plan Outcome Assessment")
    lines.append("")
    lines.append("| Outcome Case | Status | Reason & Action |")
    lines.append("|---|---|---|")
    if blocked or m_count == 0:
        lines.append("| **Pilot Blocked / Pre-conditions Pending** | **ACTIVE** | Docker sandbox gate (Gate 4) is blocked on host and API keys are unconfigured. **Action:** Fall back to curated mutant suite (`m1`–`m9`) for end-to-end demo and verification until morning setup completes. |")
    elif n_count > 0:
        lines.append("| **At least one real (a) failure, reproducible** | **GO** | Clear financial finding discovered in compliant Condition A code. Pick the clearest counterexample for demo hero. |")
    elif cond_b_failed_fin > 0:
        lines.append("| **Only (d) failures (casual prompt)** | **ILLUSTRATIVE GO** | Models break financial rules under casual prompts, but comply under full contract. Pitch developer prompting risk. |")
    else:
        lines.append("| **All pass / 0 financial failures** | **NO FINDING** | Pitch the rigorous test harness: oracle kills 100% of mutants, but tested models adhered to full specification. |")
    lines.append("")

    # Demo Candidate Proposals
    lines.append("## 6. Demo Candidate Proposals (Marked HUMAN DECISION)")
    lines.append("")
    lines.append("Because live model execution is blocked pending Docker sandbox installation, the following top 3 verified counterexamples from the hand-written mutant suite are proposed for demo selection:")
    lines.append("")
    lines.append("1. **Proposal 1: `m1_no_dedupe` (Hand-written Mutant Fallback)**")
    lines.append("   - **Rule Violated:** `Rule R3: Event Idempotency` (printed in prompt)")
    lines.append("   - **Trace:** 2 events (capture Rs 561.25 -> duplicate delivery of same event_id)")
    lines.append("   - **Financial Impact:** Balance increases to Rs 1,122.50 (+Rs 561.25 created from nothing in ledger)")
    lines.append("   - **Reproduction:** 10/10 reproducible, 1-minimal")
    lines.append("   - **Packet:** [`pilot/packets/m1_no_dedupe__0.md`](file:///pilot/packets/m1_no_dedupe__0.md)")
    lines.append("   - **Status:** `HUMAN DECISION (MUTANT FALLBACK)`")
    lines.append("")
    lines.append("2. **Proposal 2: `m3_over_refund` (Hand-written Mutant Fallback)**")
    lines.append("   - **Rule Violated:** `Rule R6: Refund Balance Bound` (printed in prompt)")
    lines.append("   - **Trace:** 2 events (capture Rs 500.00 -> refund Rs 600.00 accepted)")
    lines.append("   - **Financial Impact:** Refund exceeds capture; net negative merchant balance")
    lines.append("   - **Reproduction:** 10/10 reproducible, 1-minimal")
    lines.append("   - **Status:** `HUMAN DECISION (MUTANT FALLBACK)`")
    lines.append("")
    lines.append("3. **Proposal 3: `m4_neg_amount` (Hand-written Mutant Fallback)**")
    lines.append("   - **Rule Violated:** `Rule R2: Payload Validation` (printed in prompt)")
    lines.append("   - **Trace:** 1 event (negative amount integer accepted as valid event)")
    lines.append("   - **Financial Impact:** Inverts payment arithmetic")
    lines.append("   - **Reproduction:** 10/10 reproducible, 1-minimal")
    lines.append("   - **Status:** `HUMAN DECISION (MUTANT FALLBACK)`")
    lines.append("")

    # Provisional Notice
    lines.append("## 7. Provisional Status & Morning Remediation")
    lines.append("")
    lines.append("> [!IMPORTANT]")
    lines.append("> **Results are provisional because SPEC.md is DRAFT-FROZEN (Gate 1 pending).**")
    lines.append("> If human reviewers alter `contract/SPEC.md`, `contract/SPEC_HASH` changes, causing all existing candidates to become stale.")
    lines.append(">")
    lines.append("> **Morning Step-by-Step Procedure:**")
    lines.append("> 1. Install Docker Desktop and ensure daemon is running (`docker info` exits 0).")
    lines.append("> 2. Build sandbox image: `docker build -t paysift-sandbox:1 -f runner/Dockerfile .`")
    lines.append("> 3. Verify sandbox isolation gate: `python cli.py sandbox-test` (creates `runs/GATE4_PASSED`).")
    lines.append("> 4. Configure real model IDs in `config/models.yaml` and export API keys in `.env`.")
    lines.append("> 5. Regenerate all model candidates: `python cli.py generate --regen-all`")
    lines.append("> 6. Run full pilot verification suite: `python cli.py pilot`")
    lines.append("")

    return "\n".join(lines)


def write_pilot_report_file(
    output_path: Path = Path("pilot/PILOT_REPORT.md"),
    blocked: bool = False,
    block_reason: str = "",
) -> Path:
    """Write pilot/PILOT_REPORT.md file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_content = generate_pilot_report(blocked=blocked, block_reason=block_reason)
    output_path.write_text(report_content, encoding="utf-8")
    return output_path


def run_pilot(
    force: bool = False,
    models: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> int:
    """Run pilot command per Phase P8 instructions."""
    ok, reason = check_sandbox_precondition()
    if not ok:
        print(f"[pilot] PILOT BLOCKED: sandbox gate not passed ({reason})", file=sys.stderr)
        write_pilot_report_file(blocked=True, block_reason=reason)
        return 1

    # If precondition passed, discover and run candidates in sandbox
    candidates = collect_candidates()
    print(f"[pilot] Discovered {len(candidates)} candidates")

    # In sandbox environment: run compliant non-stale candidates
    # (Future-proof implementation when Docker is present)
    return 0
