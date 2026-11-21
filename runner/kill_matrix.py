"""Kill matrix evaluation runner for reference implementation and mutants."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple

from contract.spec_sha import compute_spec_sha
from contract.validate_run import validate_kill_matrix
from oracle.checks import compute_oracle_sha
from runner.run_candidate import run_candidate


def run_kill_matrix(
    seed_range: Tuple[int, int] = (0, 99),
    output_json_path: Optional[Path] = None,
    output_md_path: Optional[Path] = None,
    print_table: bool = True,
) -> Dict[str, Any]:
    """Execute kill matrix against reference and mutants."""
    root = Path(__file__).resolve().parent.parent
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    if output_json_path is None:
        output_json_path = runs_dir / "kill_matrix.json"
    if output_md_path is None:
        output_md_path = runs_dir / "kill_matrix.md"

    spec_sha = compute_spec_sha()
    oracle_sha = compute_oracle_sha()
    now_iso = datetime.now(timezone.utc).isoformat()

    manifest_path = root / "mutants" / "MANIFEST.json"
    manifest: List[Dict[str, Any]] = []
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    rows: List[Dict[str, Any]] = []
    assertion_errors: List[str] = []

    # 1. Run Reference Implementation
    ref_file = root / "ref" / "handler_ref.py"
    ref_run = run_candidate(ref_file, seed_range=seed_range, mode="normal", sandbox=False)
    ref_failures = ref_run.get("failures", [])
    ref_rules_hit = sorted(list(set(f["rule"] for f in ref_failures)))
    ref_clean = (len(ref_failures) == 0)

    # Concurrency for reference
    from runner.concurrency import run_concurrency_suite
    ref_conc = run_concurrency_suite(ref_file, trials=50)
    if ref_conc["scenario_A"]["failed"] > 0 or ref_conc["scenario_B"]["failed"] > 0:
        ref_clean = False
        assertion_errors.append("Reference implementation failed concurrency trials")

    if not ref_clean:
        assertion_errors.append(f"Reference implementation failed: rules hit {ref_rules_hit}")

    ref_row = {
        "id": "ref",
        "label": "handler_ref.py",
        "source": "reference",
        "expected_rule": "none",
        "expected_invariant": "none",
        "results": ref_run.get("results", {}),
        "concurrency": ref_conc,
        "killed": False,
        "rules_hit": ref_rules_hit,
        "notes": "Reference implementation clean across all invariants and concurrency trials" if ref_clean else "Reference failed",
    }
    rows.append(ref_row)

    # 2. Run Mutants from Manifest
    for item in manifest:
        mid = item["id"]
        mfile = root / item["file"]
        expected_rule = item.get("must_fail_rule", "none")
        expected_inv = item.get("must_fail_invariant", "none")
        source = "extra-mutant" if mid.startswith("x") else "mutant"
        modes_needed = item.get("modes_needed", ["normal"])

        if not mfile.is_file():
            rows.append({
                "id": mid,
                "label": item.get("bug", mid),
                "source": source,
                "expected_rule": expected_rule,
                "expected_invariant": expected_inv,
                "results": {},
                "concurrency": {},
                "killed": False,
                "rules_hit": [],
                "notes": f"Pending implementation in P5 (requires mode: {modes_needed})",
            })
            continue

        if "concurrency" in modes_needed:
            conc_res = run_concurrency_suite(mfile, trials=50)
            if mid == "m8":
                is_killed = conc_res["scenario_A"]["failed"] > 0
            elif mid == "m9":
                is_killed = conc_res["scenario_B"]["failed"] > 0
            else:
                is_killed = (conc_res["scenario_A"]["failed"] > 0 or conc_res["scenario_B"]["failed"] > 0)
            m_rules_hit = ["R10"] if is_killed else []
            m_results = {}
        elif "restart" in modes_needed:
            m_run = run_candidate(mfile, mode="restart", sandbox=False)
            m_failures = m_run.get("failures", [])
            m_rules_hit = sorted(list(set(f["rule"] for f in m_failures)))
            is_killed = expected_rule in m_rules_hit
            conc_res = {}
            m_results = m_run.get("results", {})
        else:
            m_run = run_candidate(mfile, seed_range=seed_range, mode="normal", sandbox=False)
            m_failures = m_run.get("failures", [])
            m_rules_hit = sorted(list(set(f["rule"] for f in m_failures)))
            is_killed = expected_rule in m_rules_hit
            conc_res = {}
            m_results = m_run.get("results", {})

        if not is_killed:
            assertion_errors.append(
                f"Mutant {mid} was NOT killed by expected rule '{expected_rule}'. Rules hit: {m_rules_hit}"
            )

        rows.append({
            "id": mid,
            "label": item.get("bug", mid),
            "source": source,
            "expected_rule": expected_rule,
            "expected_invariant": expected_inv,
            "results": m_results,
            "concurrency": conc_res,
            "killed": is_killed,
            "rules_hit": m_rules_hit,
            "notes": item.get("notes", ""),
        })

    # 3. Special Verification for x4
    # Assertion: x4 is caught on family 8 seeds and NOT caught on seeds excluding family 8
    x4_file = root / "mutants" / "x4_sig_canonical_reserialized.py"
    x4_fam8_caught = False
    x4_non_fam8_clean = True

    if x4_file.is_file():
        # Check from full run
        x4_run = run_candidate(x4_file, seed_range=seed_range, mode="normal", sandbox=False)
        fam8_fails = [f for f in x4_run.get("failures", []) if (f["seed"] % 10 == 8)]
        non_fam8_fails = [f for f in x4_run.get("failures", []) if (f["seed"] % 10 != 8)]

        x4_fam8_caught = len(fam8_fails) > 0
        x4_non_fam8_clean = len(non_fam8_fails) == 0

        if not x4_fam8_caught:
            assertion_errors.append("Mutant x4 was NOT caught on family 8 seeds")
        if not x4_non_fam8_clean:
            non_fam8_seeds = [f["seed"] for f in non_fam8_fails]
            assertion_errors.append(f"Mutant x4 unexpectedly caught on non-family 8 seeds: {non_fam8_seeds}")

    # Build Kill Matrix dictionary
    km_data: Dict[str, Any] = {
        "oracle_sha": oracle_sha,
        "spec_sha": spec_sha,
        "created_at": now_iso,
        "rows": rows,
    }

    # Validate schema
    schema_errors = validate_kill_matrix(km_data)
    if schema_errors:
        assertion_errors.extend([f"Kill matrix schema error: {e}" for e in schema_errors])

    # Save JSON
    output_json_path.write_text(json.dumps(km_data, indent=2), encoding="utf-8")

    # Generate Markdown Table
    md_lines: List[str] = [
        "# PaySift Kill Matrix Report",
        "",
        f"- **Spec SHA:** `{spec_sha}`",
        f"- **Oracle SHA:** `{oracle_sha}`",
        f"- **Generated At:** `{now_iso}`",
        f"- **Seeds Range:** `{seed_range[0]}..{seed_range[1]}`",
        "",
        "| ID | Label | Source | Expected Rule | Expected Invariant | Status | Rules Hit | Notes |",
        "|---|---|---|---|---|---|---|---|",
    ]

    for r in rows:
        status_badge = "PENDING"
        if r["id"] == "ref":
            status_badge = "PASS (Clean)" if not r["rules_hit"] else "FAIL"
        elif r["killed"]:
            status_badge = "KILLED"
        elif "Pending" in r.get("notes", ""):
            status_badge = "PENDING"
        else:
            status_badge = "SURVIVED"

        rules_str = ", ".join(r["rules_hit"]) if r["rules_hit"] else "-"
        md_lines.append(
            f"| `{r['id']}` | {r['label']} | {r['source']} | `{r['expected_rule']}` | "
            f"`{r['expected_invariant']}` | **{status_badge}** | `{rules_str}` | {r['notes']} |"
        )

    md_lines.extend([
        "",
        "## Invariant Sensitivity Verification",
        "",
        f"- **Reference Fully Green:** `{'PASS' if ref_clean else 'FAIL'}`",
        f"- **x4 Caught on Family 8 Seeds:** `{'PASS' if x4_fam8_caught else 'FAIL'}`",
        f"- **x4 Clean on Non-Family 8 Seeds:** `{'PASS' if x4_non_fam8_clean else 'FAIL'}`",
        "",
    ])

    if assertion_errors:
        md_lines.append("## Assertion Failures")
        md_lines.append("")
        for err in assertion_errors:
            md_lines.append(f"- ❌ {err}")
        md_lines.append("")

    output_md_path.write_text("\n".join(md_lines), encoding="utf-8")

    # Console output table
    if print_table:
        print("\n" + "=" * 90)
        print(" PaySift Kill Matrix")
        print("=" * 90)
        print(f" Spec SHA   : {spec_sha[:16]}... | Oracle SHA: {oracle_sha[:16]}...")
        print(f" Timestamp  : {now_iso} | Seeds: {seed_range[0]}..{seed_range[1]}")
        print("-" * 90)
        print(f"{'ID':<6} | {'Label':<30} | {'Expected':<10} | {'Status':<10} | {'Rules Hit':<15} | {'Source'}")
        print("-" * 90)
        for r in rows:
            if r["id"] == "ref":
                status = "CLEAN" if not r["rules_hit"] else "FAILED"
            elif r["killed"]:
                status = "KILLED"
            elif "Pending" in r.get("notes", ""):
                status = "PENDING"
            else:
                status = "SURVIVED"
            rules_str = ",".join(r["rules_hit"]) if r["rules_hit"] else "-"
            print(f"{r['id']:<6} | {r['label'][:30]:<30} | {r['expected_rule']:<10} | {status:<10} | {rules_str:<15} | {r['source']}")
        print("=" * 90)
        print(f" Reference Clean      : {'PASS' if ref_clean else 'FAIL'}")
        print(f" x4 Family 8 Caught   : {'PASS' if x4_fam8_caught else 'FAIL'}")
        print(f" x4 Non-Family 8 Clean: {'PASS' if x4_non_fam8_clean else 'FAIL'}")
        print("=" * 90 + "\n")

    if assertion_errors:
        km_data["assertion_errors"] = assertion_errors

    return km_data
