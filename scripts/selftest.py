"""End-to-End Self-Test Suite for PaySift (Gate G8).

Executes all verification checks:
1. Environment & configuration (check-env)
2. Spec SHA consistency (contract/SPEC_HASH)
3. Schema validation of all runs/*.json
4. Kill matrix sensitivity assertions
5. Counterexample delta debugging & shrinking (m1, m2)
6. Fixed break-it scenarios (6 scenarios)
7. Static HTML reports generation
8. Unit and integration tests (pytest)
9. Docker sandbox isolation (Gate 4)
10. Git baseline integrity (check-git)
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from contract.spec_sha import compute_spec_sha
from contract.validate_run import validate as validate_run_dict
from generate.spec_binding import get_current_spec_sha
from oracle.checks import compute_oracle_sha
from report.generate import build_reports
from runner.sandbox import is_docker_available, is_docker_image_available
from scenarios.scenarios import SCENARIOS, run_scenario
from shrink.ddmin import ddmin


class CheckResult:
    def __init__(self, name: str, passed: bool, skipped: bool = False, message: str = "", duration: float = 0.0):
        self.name = name
        self.passed = passed
        self.skipped = skipped
        self.message = message
        self.duration = duration


def run_selftest(full: bool = False) -> int:
    """Execute Gate 8 self-test pipeline."""
    repo_root = Path(__file__).resolve().parent.parent
    results: List[CheckResult] = []
    t_start = time.monotonic()

    print("=================================================================")
    print(" PaySift End-to-End Self-Test Pipeline (Gate G8)")
    print(f" Mode: {'FULL' if full else 'FAST'} | Target: Complete System Verification")
    print("=================================================================")

    # 1. Check Env
    t0 = time.monotonic()
    try:
        res = subprocess.run([sys.executable, str(repo_root / "cli.py"), "check-env"], capture_output=True, text=True)
        results.append(CheckResult("1. Environment Checks (check-env)", res.returncode == 0, False, "Environment scanned", time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("1. Environment Checks (check-env)", False, False, str(exc), time.monotonic() - t0))

    # 2. Spec SHA Consistency
    t0 = time.monotonic()
    try:
        spec_hash_file = repo_root / "contract" / "SPEC_HASH"
        recorded_sha = spec_hash_file.read_text(encoding="utf-8").strip() if spec_hash_file.exists() else ""
        computed_sha = compute_spec_sha(repo_root / "contract" / "SPEC.md", repo_root / "contract" / "schema.sql")
        match = (recorded_sha == computed_sha)
        msg = f"Hash: {computed_sha[:16]}..." if match else f"Mismatch: {recorded_sha[:8]} != {computed_sha[:8]}"
        results.append(CheckResult("2. Spec SHA Consistency (SPEC_HASH)", match, False, msg, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("2. Spec SHA Consistency (SPEC_HASH)", False, False, str(exc), time.monotonic() - t0))

    # 3. Schema Validation of All runs/*.json
    t0 = time.monotonic()
    try:
        runs_dir = repo_root / "runs"
        skip_files = {"scenario_verdicts.json", "kill_matrix.json", "kill_matrix.sample.json"}
        invalid_runs = []
        total_runs = 0
        for rf in runs_dir.glob("*.json"):
            if rf.name in skip_files:
                continue
            total_runs += 1
            data = json.loads(rf.read_text(encoding="utf-8"))
            errs = validate_run_dict(data)
            if errs:
                invalid_runs.append((rf.name, errs))
        passed = (len(invalid_runs) == 0 and total_runs > 0)
        msg = f"All {total_runs} runs valid" if passed else f"{len(invalid_runs)}/{total_runs} invalid"
        results.append(CheckResult("3. Schema Validation (runs/*.json)", passed, False, msg, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("3. Schema Validation (runs/*.json)", False, False, str(exc), time.monotonic() - t0))

    # 4. Kill Matrix Assertions
    t0 = time.monotonic()
    try:
        km_file = repo_root / "runs" / "kill_matrix.json"
        if not km_file.exists():
            results.append(CheckResult("4. Kill Matrix Assertions", False, False, "runs/kill_matrix.json missing", time.monotonic() - t0))
        else:
            km_data = json.loads(km_file.read_text(encoding="utf-8"))
            rows = km_data.get("rows", [])
            ref_clean = False
            mutants_killed = 0
            for r in rows:
                if r.get("id") == "ref":
                    ref_clean = (r.get("killed") is False and len(r.get("rules_hit", [])) == 0)
                elif r.get("source") in ("mutant", "extra-mutant"):
                    expected_rule = r.get("expected_rule")
                    # Check if killed with expected rule
                    if r.get("killed") is True and expected_rule in r.get("rules_hit", []):
                        mutants_killed += 1

            all_ok = ref_clean and (mutants_killed == 13)
            msg = f"Ref clean: {ref_clean}, Mutants killed: {mutants_killed}/13"
            results.append(CheckResult("4. Kill Matrix Assertions", all_ok, False, msg, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("4. Kill Matrix Assertions", False, False, str(exc), time.monotonic() - t0))

    # 5. Counterexample Shrinking (m1, m2)
    t0 = time.monotonic()
    try:
        from runner.streams import generate_stream
        from shrink.predicate import make_predicate

        # Test m1_no_dedupe on seed 0
        raw_stream_m1 = generate_stream(seed=0)
        pred_m1 = make_predicate(repo_root / "mutants" / "m1_no_dedupe.py", "normal", "I2_idempotency", "R3")
        shrunk_m1, min_m1 = ddmin(raw_stream_m1, pred_m1, max_runs=50, max_seconds=10.0)

        # Test m2_nonatomic on seed 0
        raw_stream_m2 = generate_stream(seed=0)
        pred_m2 = make_predicate(repo_root / "mutants" / "m2_nonatomic.py", "normal", "I3_conservation", "R7")
        shrunk_m2, min_m2 = ddmin(raw_stream_m2, pred_m2, max_runs=50, max_seconds=10.0)

        passed = (len(shrunk_m1) <= 4 and min_m1 and len(shrunk_m2) <= 4 and min_m2)
        msg = f"m1: {len(shrunk_m1)} ev (1-min: {min_m1}), m2: {len(shrunk_m2)} ev (1-min: {min_m2})"
        results.append(CheckResult("5. Shrinking Minimization (m1 & m2)", passed, False, msg, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("5. Shrinking Minimization (m1 & m2)", False, False, str(exc), time.monotonic() - t0))

    # 6. Fixed Break-it Scenarios
    t0 = time.monotonic()
    try:
        verdicts_file = repo_root / "runs" / "scenario_verdicts.json"
        if not verdicts_file.exists():
            results.append(CheckResult("6. Scenario Verdicts (6 Scenarios)", False, False, "runs/scenario_verdicts.json missing", time.monotonic() - t0))
        else:
            v_data = json.loads(verdicts_file.read_text(encoding="utf-8"))
            ref_verdicts = v_data.get("by_candidate", {}).get("reference", {})
            ref_all_pass = (len(ref_verdicts) == 6 and all(v.get("verdict") == "pass" for v in ref_verdicts.values()))
            m1_dup_fail = v_data.get("by_candidate", {}).get("m1_no_dedupe", {}).get("duplicate_capture", {}).get("verdict") == "fail"
            passed = ref_all_pass and m1_dup_fail
            msg = f"Reference: {len(ref_verdicts)}/6 pass, m1 caught: {m1_dup_fail}"
            results.append(CheckResult("6. Scenario Verdicts (6 Scenarios)", passed, False, msg, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("6. Scenario Verdicts (6 Scenarios)", False, False, str(exc), time.monotonic() - t0))

    # 7. Static HTML Reports
    t0 = time.monotonic()
    try:
        reports = build_reports(repo_root / "runs", repo_root / "report" / "out")
        idx_p = repo_root / "report" / "out" / "index.html"
        km_p = repo_root / "report" / "out" / "kill_matrix.html"
        sc_p = repo_root / "report" / "out" / "scenarios.html"
        all_exist = idx_p.exists() and km_p.exists() and sc_p.exists() and len(reports) >= 4
        msg = f"{len(reports)} HTML reports generated in report/out/"
        results.append(CheckResult("7. Static HTML Reports Generation", all_exist, False, msg, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("7. Static HTML Reports Generation", False, False, str(exc), time.monotonic() - t0))

    # 8. Core Unit Test Suite (pytest)
    t0 = time.monotonic()
    try:
        test_files = [
            "tests/test_contract.py",
            "tests/test_oracle.py",
            "tests/test_ref.py",
            "tests/test_ast_gate.py",
            "tests/test_streams.py",
            "tests/test_shrink.py",
            "tests/test_generate.py",
            "tests/test_pilot.py",
            "tests/test_repair.py",
            "tests/test_scenarios.py",
            "tests/test_report.py",
            "tests/test_api.py",
            "tests/test_cli.py",
        ]
        cmd = [sys.executable, "-m", "pytest", "-q"] + test_files
        res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)
        passed = (res.returncode == 0)
        summary_line = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else res.stderr.strip()
        results.append(CheckResult("8. Core Unit Test Suite (pytest)", passed, False, summary_line, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("8. Core Unit Test Suite (pytest)", False, False, str(exc), time.monotonic() - t0))

    # 9. Docker Sandbox Gate (Gate 4)
    t0 = time.monotonic()
    docker_ready = is_docker_available() and is_docker_image_available("paysift-sandbox:1")
    if not docker_ready:
        results.append(CheckResult("9. Docker Sandbox Isolation (Gate 4)", True, True, "SKIP (Docker unavailable on host, logged as BH-001)", time.monotonic() - t0))
    else:
        try:
            # Run hostile tests if full and docker ready
            hostile_test = repo_root / "tests" / "test_sandbox_hostile.py"
            res = subprocess.run([sys.executable, "-m", "pytest", str(hostile_test)], cwd=str(repo_root), capture_output=True, text=True)
            results.append(CheckResult("9. Docker Sandbox Isolation (Gate 4)", res.returncode == 0, False, "Hostile containment verified", time.monotonic() - t0))
        except Exception as exc:
            results.append(CheckResult("9. Docker Sandbox Isolation (Gate 4)", False, False, str(exc), time.monotonic() - t0))

    # 10. Git Baseline Integrity (check-git)
    t0 = time.monotonic()
    try:
        res = subprocess.run([sys.executable, str(repo_root / "cli.py"), "check-git"], capture_output=True, text=True)
        results.append(CheckResult("10. Git Baseline Integrity (check-git)", res.returncode == 0, False, "HEAD matches baseline, 0 staged", time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("10. Git Baseline Integrity (check-git)", False, False, str(exc), time.monotonic() - t0))

    # 11. You.com Grounding Artifact (runs/grounding.json)
    t0 = time.monotonic()
    try:
        grounding_path = repo_root / "runs" / "grounding.json"
        if not grounding_path.is_file():
            results.append(CheckResult("11. You.com Grounding Schema", True, True, "SKIP (runs/grounding.json absent)", time.monotonic() - t0))
        else:
            from grounding.validator import validate_grounding
            g_data = json.loads(grounding_path.read_text(encoding="utf-8"))
            g_errs = validate_grounding(g_data)
            passed = len(g_errs) == 0
            msg = f"Validated {len(g_data.get('rules', {}))} rules with 0 errors" if passed else f"Validation errors: {g_errs[:2]}"
            results.append(CheckResult("11. You.com Grounding Schema", passed, False, msg, time.monotonic() - t0))
    except Exception as exc:
        results.append(CheckResult("11. You.com Grounding Schema", False, False, str(exc), time.monotonic() - t0))

    # Print summary table
    print("-----------------------------------------------------------------")
    print(f" {'Check':<42} | {'Result':<6} | {'Time':<6} | Details")
    print("-----------------------------------------------------------------")
    all_passed = True
    for r in results:
        status_str = "SKIP" if r.skipped else ("PASS" if r.passed else "FAIL")
        if not r.skipped and not r.passed:
            all_passed = False
        print(f" {r.name:<42} | {status_str:<6} | {r.duration:5.2f}s | {r.message}")
    print("=================================================================")
    total_time = time.monotonic() - t_start

    skipped_checks = [r for r in results if r.skipped]
    failed_checks = [r for r in results if not r.passed and not r.skipped]

    if failed_checks:
        verdict_text = f"SELF-TEST FAILED ({len(failed_checks)} failed)"
    elif skipped_checks:
        skipped_details = "; ".join(f"{r.name}: {r.message}" for r in skipped_checks)
        verdict_text = f"PASS ({len(skipped_checks)} skipped - {skipped_details})"
    else:
        verdict_text = "ALL CHECKS PASSED (Gate 8 Verified)"

    print(f" Final Verdict: {verdict_text} (Total Time: {total_time:.2f}s)")
    print("=================================================================")

    return 0 if all_passed else 1
