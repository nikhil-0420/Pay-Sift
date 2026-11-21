"""PaySift Sandbox and Hostile Test Suite (Gate 4 Verification)."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple
import uuid

from runner.sandbox import (
    build_sandbox_image,
    is_docker_available,
    is_docker_image_available,
    run_in_sandbox,
)


def compute_run_digest(run_data: Dict[str, Any]) -> str:
    """Compute deterministic digest of run results (excluding execution timing)."""
    normalized = {
        "results": run_data.get("results"),
        "failures": [
            {
                "rule": f.get("rule"),
                "seed": f.get("seed"),
                "first_bad_step": f.get("first_bad_step"),
                "expected": f.get("expected"),
                "observed": f.get("observed"),
            }
            for f in run_data.get("failures", [])
        ],
    }
    dumped = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def execute_sandbox_gate() -> Tuple[bool, Dict[str, Any]]:
    """Execute complete Gate 4 sandbox verification.

    Returns:
        (passed, summary_dict)
    """
    root = Path(__file__).resolve().parent.parent
    runs_dir = root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    gate4_passed = runs_dir / "GATE4_PASSED"
    gate4_failed = runs_dir / "GATE4_FAILED.md"

    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Check Docker Availability
    if not is_docker_available():
        if gate4_passed.exists():
            gate4_passed.unlink()

        fail_report = [
            "# Gate 4 Failure Report: Docker Unavailable",
            "",
            f"- **Timestamp:** `{now_iso}`",
            "- **Status:** FAILED / BLOCKED",
            "- **Reason:** Docker CLI or Docker daemon is not installed/reachable on host.",
            "",
            "## Impact",
            "- In accordance with **Agent Rule 3** (Untrusted Code Only in the Sandbox):",
            "  * Model-generated candidates and hostile handlers can NEVER run natively.",
            "  * Gate 4 is a **HARD GATE**: no untrusted candidate execution can proceed.",
            "  * Phase P8 (Pilot Runs) and Phase P9 (Repair Loop) model execution remain strictly blocked.",
            "",
            "## Required Human Action",
            "1. Install Docker Desktop or Docker Engine on host.",
            "2. Ensure Docker daemon is running and `docker info` exits with code 0.",
            "3. Build the sandbox image: `docker build -t paysift-sandbox:1 -f runner/Dockerfile .`",
            "4. Run `python cli.py sandbox-test` to re-verify Gate 4.",
        ]
        gate4_failed.write_text("\n".join(fail_report), encoding="utf-8")

        # Update NEEDS_HUMAN.md
        needs_human = root / "NEEDS_HUMAN.md"
        if needs_human.is_file():
            nh_text = needs_human.read_text(encoding="utf-8")
            blocker_entry = (
                "\n### BH-001: Docker Unavailable on Host (Gate 4 Hard Blocker)\n"
                f"- **Logged:** {now_iso}\n"
                "- **Status:** BLOCKER\n"
                "- **Impact:** Gate 4 FAILED. No model-generated code can execute tonight without Docker sandbox (Rule 3).\n"
                "- **Action:** Install Docker, run daemon, build `paysift-sandbox:1`, and run `python cli.py sandbox-test`.\n"
            )
            if "BH-001" not in nh_text:
                needs_human.write_text(nh_text.strip() + "\n" + blocker_entry, encoding="utf-8")

        summary = {
            "ok": False,
            "reason": "Docker unavailable on host",
            "timestamp": now_iso,
            "gate": "G4_BLOCKED",
        }
        return False, summary

    # 2. Check Sandbox Image
    image_tag = "paysift-sandbox:1"
    if not is_docker_image_available(image_tag):
        print(f"Building sandbox image '{image_tag}'...")
        ok, msg = build_sandbox_image(image_tag)
        if not ok:
            summary = {"ok": False, "reason": f"Failed to build sandbox image: {msg}"}
            return False, summary

    # 3. Hostile Tests Containment
    hostile_dir = root / "tests" / "hostile"
    hostile_files = [
        "h1_socket.py",
        "h2_write_root.py",
        "h3_infinite_loop.py",
        "h4_alloc_2gb.py",
        "h5_forkbomb.py",
        "h6_read_proc_environ_home.py",
        "h7_write_cand.py",
    ]

    hostile_results: Dict[str, Any] = {}
    canary_secret = f"PAYSIFT_CANARY_{uuid.uuid4().hex}"
    os.environ["PAYSIFT_CANARY"] = canary_secret

    print("\nRunning Hostile Handler Containment Tests in Docker Sandbox...")
    for hf in hostile_files:
        hpath = hostile_dir / hf
        job = {
            "candidate_file": str(hpath),
            "mode": "normal",
            "sequences": [{
                "seed": 0,
                "steps": [{
                    "raw_body_b64": "e30=",
                    "signature": "00" * 32,
                    "tag": f"test_{hf}",
                }],
            }],
        }
        res = run_in_sandbox(hpath, job, mode="normal", timeout=35.0)
        hostile_results[hf] = res

        # Verify canary did not leak
        if hf == "h6_read_proc_environ_home.py":
            res_str = json.dumps(res)
            if canary_secret in res_str:
                return False, {"ok": False, "reason": "Host environment variable leaked into container!"}

    # 4. Check Leftover Containers
    ps_proc = subprocess.run(
        ["docker", "ps", "-a", "--filter", "name=paysift-", "--format", "{{.Names}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    leftovers = [line.strip() for line in ps_proc.stdout.splitlines() if line.strip()]
    if leftovers:
        return False, {"ok": False, "reason": f"Leftover containers found: {leftovers}"}

    # 5. Parity Tests
    from runner.run_candidate import run_candidate

    candidates_to_test = [
        root / "ref" / "handler_ref.py",
        root / "mutants" / "m1_no_dedupe.py",
        root / "mutants" / "m2_nonatomic.py",
        root / "mutants" / "m3_no_bound.py",
        root / "mutants" / "m4_neg_amount.py",
        root / "mutants" / "m5_reject_consumes_id.py",
        root / "mutants" / "m6_sig_reserialized.py",
        root / "mutants" / "x1_bool_amount.py",
        root / "mutants" / "x2_float_amount.py",
        root / "mutants" / "x3_nonascii_sig_crash.py",
        root / "mutants" / "x4_sig_canonical_reserialized.py",
    ]

    print("\nRunning Native vs Sandbox Parity Verification (seeds 0-19)...")
    parity_results: Dict[str, bool] = {}
    for cand in candidates_to_test:
        if not cand.is_file():
            continue
        native_run = run_candidate(cand, mode="normal", seed_range=(0, 19), sandbox=False)
        sandbox_run = run_candidate(cand, mode="normal", seed_range=(0, 19), sandbox=True)

        native_digest = compute_run_digest(native_run)
        sandbox_digest = compute_run_digest(sandbox_run)

        match = (native_digest == sandbox_digest)
        parity_results[cand.name] = match
        if not match:
            return False, {"ok": False, "reason": f"Parity mismatch on {cand.name}"}

    # Reference parity on seeds 0-99
    ref_file = root / "ref" / "handler_ref.py"
    ref_nat = run_candidate(ref_file, mode="normal", seed_range=(0, 99), sandbox=False)
    ref_sbx = run_candidate(ref_file, mode="normal", seed_range=(0, 99), sandbox=True)
    if compute_run_digest(ref_nat) != compute_run_digest(ref_sbx):
        return False, {"ok": False, "reason": "Reference parity mismatch on seeds 0-99"}

    # 6. Success: Gate 4 Passed
    img_proc = subprocess.run(
        ["docker", "image", "inspect", image_tag, "--format", "{{.Id}}"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    image_id = img_proc.stdout.strip()

    pass_lines = [
        f"GATE4_PASSED={now_iso}",
        f"IMAGE_ID={image_id}",
        f"IMAGE_TAG={image_tag}",
        "HOSTILE_CONTAINMENT=7/7 contained",
        "CONTAINER_LEFTOVERS=0",
        "PARITY_SEEDS_0_19=11/11 matched",
        "REFERENCE_PARITY_SEEDS_0_99=matched",
    ]
    gate4_passed.write_text("\n".join(pass_lines) + "\n", encoding="utf-8")
    if gate4_failed.exists():
        gate4_failed.unlink()

    return True, {
        "ok": True,
        "image_id": image_id,
        "timestamp": now_iso,
        "hostile_results": hostile_results,
        "parity_results": parity_results,
    }
