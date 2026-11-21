"""PaySift Command Line Interface.

Provides developer and agent commands for environment verification,
git state verification, test harness execution, and pipeline orchestration.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None


def load_env_file(env_path: Path) -> None:
    """Load key-value pairs from .env into os.environ if not already present."""
    if not env_path.is_file():
        return
    try:
        content = env_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception as exc:
        print(f"Warning: failed to read .env: {exc}", file=sys.stderr)


def run_cmd(args: List[str], timeout: float = 10.0, cwd: Optional[Path] = None) -> Tuple[int, str, str]:
    """Run a subprocess command safely with argument list and timeout."""
    try:
        res = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(cwd) if cwd else None,
            encoding="utf-8",
            errors="replace",
        )
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return -2, "", "Executable not found"
    except Exception as exc:
        return -3, "", str(exc)


def get_git_state(repo_dir: Path) -> Dict[str, Any]:
    """Collect read-only git state."""
    code, out, _ = run_cmd(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    head = out if code == 0 else "NO_COMMITS"

    code, out, _ = run_cmd(["git", "status", "--porcelain"], cwd=repo_dir)
    status_porcelain = out.splitlines() if code == 0 and out else []

    code, out, _ = run_cmd(["git", "diff", "--cached", "--name-only"], cwd=repo_dir)
    staged = [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []

    code, out, _ = run_cmd(["git", "stash", "list"], cwd=repo_dir)
    stashes = [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []

    code, out, _ = run_cmd(["git", "branch", "--list"], cwd=repo_dir)
    branches = [line.strip().lstrip("* ").strip() for line in out.splitlines() if line.strip()] if code == 0 else []

    code, out, _ = run_cmd(["git", "tag", "--list"], cwd=repo_dir)
    tags = [line.strip() for line in out.splitlines() if line.strip()] if code == 0 else []

    return {
        "head": head,
        "status_porcelain": status_porcelain,
        "staged": staged,
        "stashes": stashes,
        "branches": branches,
        "tags": tags,
    }


def parse_git_baseline(baseline_file: Path) -> Dict[str, Any]:
    """Parse .agent/git_baseline.txt into sections."""
    if not baseline_file.is_file():
        raise FileNotFoundError(f"Git baseline file not found: {baseline_file}")

    content = baseline_file.read_text(encoding="utf-8")
    lines = content.splitlines()

    sections: Dict[str, List[str]] = {}
    current_section: Optional[str] = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("=== ") and stripped.endswith(" ==="):
            current_section = stripped[4:-4].strip()
            sections[current_section] = []
        elif current_section is not None:
            sections[current_section].append(line)

    head = "NO_COMMITS"
    if "HEAD" in sections and sections["HEAD"]:
        head = sections["HEAD"][0].strip()

    staged = [line.strip() for line in sections.get("DIFF_CACHED", []) if line.strip()]
    stashes = [line.strip() for line in sections.get("STASH_LIST", []) if line.strip()]
    branches = [line.strip().lstrip("* ").strip() for line in sections.get("BRANCH_LIST", []) if line.strip()]
    tags = [line.strip() for line in sections.get("TAG_LIST", []) if line.strip()]

    return {
        "head": head,
        "staged": staged,
        "stashes": stashes,
        "branches": branches,
        "tags": tags,
    }


def cmd_check_env(args: argparse.Namespace) -> int:
    """Execute check-env command."""
    root = Path(__file__).resolve().parent
    agent_dir = root / ".agent"
    agent_dir.mkdir(parents=True, exist_ok=True)
    load_env_file(root / ".env")

    # Python version
    py_version = platform.python_version()
    is_3_12 = (sys.version_info.major == 3 and sys.version_info.minor == 12)

    # Docker checks
    docker_bin = shutil.which("docker")
    docker_cli_present = docker_bin is not None
    docker_daemon_reachable = False
    image_present = False
    docker_run_result = "skipped (docker cli not found)"

    if docker_cli_present:
        code, out, _ = run_cmd(["docker", "info"], timeout=5.0)
        docker_daemon_reachable = (code == 0)

        if docker_daemon_reachable:
            code, out, _ = run_cmd(["docker", "image", "inspect", "python:3.12-slim"], timeout=5.0)
            image_present = (code == 0)

            if image_present:
                code, out, err = run_cmd(
                    ["docker", "run", "--rm", "--network", "none", "python:3.12-slim", "python", "-c", "print(1)"],
                    timeout=10.0,
                )
                if code == 0 and out.strip() == "1":
                    docker_run_result = "passed (output: 1)"
                else:
                    docker_run_result = f"failed (code {code}: {out} {err})"
            else:
                docker_run_result = "skipped (image python:3.12-slim missing)"
        else:
            docker_run_result = "skipped (docker daemon unreachable)"

    # Git state
    git_state = get_git_state(root)

    # API keys and models config
    models_file = root / "config" / "models.yaml"
    models_present = models_file.is_file()
    models_filled = False
    configured_keys: List[str] = []
    set_keys: List[str] = []

    if models_present and yaml is not None:
        try:
            with open(models_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            models_list = data.get("models", [])
            has_fill_me = False
            for m in models_list:
                key_env = m.get("api_key_env")
                if key_env and key_env not in configured_keys:
                    configured_keys.append(key_env)
                    if os.environ.get(key_env):
                        set_keys.append(key_env)
                model_id = str(m.get("model_id", "")).strip()
                if not model_id or model_id == "FILL_ME":
                    has_fill_me = True
            models_filled = (len(models_list) > 0 and not has_fill_me)
        except Exception as exc:
            print(f"Warning: could not parse models.yaml: {exc}", file=sys.stderr)

    report_data = {
        "timestamp": platform.node(),
        "python": {
            "version": py_version,
            "is_3_12": is_3_12,
            "executable": sys.executable,
        },
        "docker": {
            "cli_present": docker_cli_present,
            "daemon_reachable": docker_daemon_reachable,
            "image_present": image_present,
            "test_run": docker_run_result,
        },
        "git": {
            "head": git_state["head"],
            "staged_count": len(git_state["staged"]),
            "branch_count": len(git_state["branches"]),
            "tag_count": len(git_state["tags"]),
            "stash_count": len(git_state["stashes"]),
        },
        "api_keys": {
            "configured_names": configured_keys,
            "set_names": set_keys,
        },
        "models_config": {
            "present": models_present,
            "filled": models_filled,
        },
    }

    out_file = agent_dir / "check_env.json"
    out_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")

    # Print summary table
    print("=" * 60)
    print(" PaySift Environment Check (check-env)")
    print("=" * 60)
    print(f" Python Version        : {py_version} (3.12 target: {'YES' if is_3_12 else 'NO - runtime notice'})")
    print(f" Docker CLI            : {'PRESENT' if docker_cli_present else 'NOT FOUND'}")
    print(f" Docker Daemon         : {'REACHABLE' if docker_daemon_reachable else 'UNREACHABLE'}")
    print(f" python:3.12-slim      : {'PRESENT' if image_present else 'MISSING'}")
    print(f" Docker Sandbox Test   : {docker_run_result}")
    print(f" Git HEAD              : {git_state['head']}")
    print(f" Git Staged Files      : {len(git_state['staged'])}")
    print(f" Configured API Keys   : {', '.join(configured_keys) if configured_keys else 'None'}")
    print(f" Active API Keys (env) : {', '.join(set_keys) if set_keys else 'None'}")
    print(f" models.yaml Filled    : {'YES' if models_filled else 'NO (FILL_ME present or unconfigured)'}")
    print("-" * 60)
    print(f" Wrote report to: {out_file}")
    print("=" * 60)
    return 0


def cmd_check_git(args: argparse.Namespace) -> int:
    """Execute check-git command."""
    root = Path(__file__).resolve().parent
    baseline_file = root / ".agent" / "git_baseline.txt"

    try:
        baseline = parse_git_baseline(baseline_file)
    except Exception as exc:
        print(f"GIT CHECK FAILED: {exc}", file=sys.stderr)
        return 1

    current = get_git_state(root)
    violations: List[str] = []

    # 1. HEAD check
    if current["head"] != baseline["head"]:
        violations.append(f"HEAD changed: baseline '{baseline['head']}', current '{current['head']}'")

    # 2. Staged changes check
    if current["staged"]:
        violations.append(f"Working tree has staged files: {', '.join(current['staged'])}")

    # 3. New branch check
    new_branches = set(current["branches"]) - set(baseline["branches"])
    if new_branches:
        violations.append(f"New branch created: {', '.join(sorted(new_branches))}")

    # 4. New tag check
    new_tags = set(current["tags"]) - set(baseline["tags"])
    if new_tags:
        violations.append(f"New tag created: {', '.join(sorted(new_tags))}")

    # 5. New stash check
    new_stashes = set(current["stashes"]) - set(baseline["stashes"])
    if new_stashes:
        violations.append(f"New stash created: {', '.join(sorted(new_stashes))}")

    if violations:
        print("GIT CHECK FAILED: Git state violates agent rules:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("Git check passed: uncommitted working tree preserved, HEAD matches baseline.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Execute test run on a candidate handler."""
    from runner.run_candidate import run_candidate

    cand_path = Path(args.file)
    if not cand_path.is_file():
        print(f"Error: candidate file not found: {cand_path}", file=sys.stderr)
        return 1

    seed_range = (0, 99)
    if args.seeds:
        try:
            parts = args.seeds.split("-")
            seed_range = (int(parts[0]), int(parts[1]))
        except Exception:
            print(f"Error: invalid seed range '{args.seeds}', expected format 'start-end' (e.g. 0-99)", file=sys.stderr)
            return 1

    try:
        run_candidate(
            candidate_path=cand_path,
            mode=args.mode,
            seed_range=seed_range,
            sandbox=args.sandbox,
            amount_pass_enabled=getattr(args, "amount_pass", False),
        )
        return 0
    except Exception as exc:
        print(f"Error running candidate: {exc}", file=sys.stderr)
        return 1


def cmd_shrink(args: argparse.Namespace) -> int:
    """Execute shrink command on a run failure."""
    from runner.streams import generate_stream
    from shrink import shrink_failure

    run_path = Path(args.run)
    if not run_path.is_file():
        print(f"Error: run file not found: {run_path}", file=sys.stderr)
        return 1

    try:
        run_data = json.loads(run_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Error reading {run_path}: {exc}", file=sys.stderr)
        return 1

    failures = run_data.get("failures", [])
    if not failures:
        print(f"Run {run_path} has no failures to shrink.")
        return 0

    fail_idx = args.failure
    if fail_idx < 0 or fail_idx >= len(failures):
        print(f"Error: failure index {fail_idx} out of range (0..{len(failures)-1})", file=sys.stderr)
        return 1

    fail = failures[fail_idx]
    cand_id = run_data["candidate"]["id"]

    # Locate candidate file
    repo_root = Path(__file__).resolve().parent
    cand_path = None
    for search_dir in [repo_root / "ref", repo_root / "mutants"]:
        candidate_file = search_dir / f"{cand_id}.py"
        if candidate_file.is_file():
            cand_path = candidate_file
            break
        for f in search_dir.glob("*.py"):
            if f.stem == cand_id:
                cand_path = f
                break

    if cand_path is None:
        print(f"Error: could not locate candidate file for '{cand_id}'", file=sys.stderr)
        return 1

    seed = fail.get("seed", 0)
    raw_stream = generate_stream(seed)
    mode = fail.get("mode", "normal")
    sandbox = run_data.get("harness", {}).get("docker", False)

    print(f"Shrinking failure #{fail_idx} ({fail['invariant']}, {fail['rule']}) from seed {seed}...")
    print(f"Candidate: {cand_path} (mode={mode}, initial events={len(raw_stream)})")

    def print_progress(intermediate):
        print(f"  -> Reduced stream length to {len(intermediate)}")

    shrink_failure(
        candidate_path=cand_path,
        failure=fail,
        raw_stream=raw_stream,
        mode=mode,
        sandbox=sandbox,
        amount_pass_enabled=getattr(args, "amount_pass", False),
        on_step_callback=print_progress,
    )

    print("\n--- Shrink Result ---")
    print(f"Minimal stream length: {len(fail['minimal_stream'])}")
    print(f"1-minimal: {fail['one_minimal']}")
    print(f"Repro: {fail.get('repro', {})}")
    print(f"Explanation: {fail.get('explanation')}")

    # Write back updated run_data
    run_path.write_text(json.dumps(run_data, indent=2), encoding="utf-8")
    print(f"Updated {run_path}")
    return 0


def cmd_kill_matrix(args: argparse.Namespace) -> int:
    """Execute kill-matrix command."""
    from runner.kill_matrix import run_kill_matrix

    try:
        km = run_kill_matrix(seed_range=(0, 99), print_table=True)
        if "assertion_errors" in km and km["assertion_errors"]:
            for err in km["assertion_errors"]:
                print(f"Assertion error: {err}", file=sys.stderr)
            return 1
        return 0
    except Exception as exc:
        print(f"Error executing kill matrix: {exc}", file=sys.stderr)
        return 1


def cmd_sandbox_test(args: argparse.Namespace) -> int:
    """Execute sandbox-test command."""
    from runner.sandbox_test import execute_sandbox_gate

    passed, summary = execute_sandbox_gate()
    if not passed:
        print(f"Sandbox Gate 4 FAILED: {summary.get('reason')}", file=sys.stderr)
        return 1
    print("Sandbox Gate 4 PASSED: All hostile tests contained and parity holds.")
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Execute candidate generation pipeline."""
    from generate.generate import run_generation_pipeline

    filter_models = [m.strip() for m in args.models.split(",") if m.strip()] if getattr(args, "models", None) else None
    run_generation_pipeline(
        dry_run=getattr(args, "dry_run", False),
        limit=getattr(args, "limit", None),
        filter_models=filter_models,
        stale_only=getattr(args, "stale_only", False),
        regen_all=getattr(args, "regen_all", False),
    )
    return 0


def cmd_pilot(args: argparse.Namespace) -> int:
    """Execute pilot verification on model candidates."""
    from pilot.runner import run_pilot

    models = [m.strip() for m in args.models.split(",") if m.strip()] if getattr(args, "models", None) else None
    return run_pilot(
        force=getattr(args, "force", False),
        models=models,
        limit=getattr(args, "limit", None),
    )


def cmd_repair(args: argparse.Namespace) -> int:
    """Execute repair loop on a failing candidate run."""
    from repair.repair import run_repair

    target = getattr(args, "run", None) or getattr(args, "candidate", None) or "runs/real_example.json"
    failure_idx = getattr(args, "failure", 0)
    stub = getattr(args, "stub", False)
    res = run_repair(target_run_id_or_path=target, failure_index=failure_idx, stub=stub)
    print(f"[repair] Generated repair run: {res.get('run_id')} (label: {res.get('candidate', {}).get('label')})")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Generate static HTML reports under report/out/."""
    from report.generate import build_reports

    out_dir = Path(getattr(args, "out", "report/out"))
    files = build_reports(out_dir=out_dir)
    print(f"[report] Generated {len(files)} static HTML reports in {out_dir}/")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    """Start PaySift FastAPI backend server via uvicorn."""
    import uvicorn

    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    print(f"[serve] Starting PaySift API server on http://{host}:{port}")
    uvicorn.run("api.main:app", host=host, port=port, reload=False)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Run one-command offline demonstration."""
    from scripts.demo import run_demo

    no_serve = getattr(args, "no_serve", False)
    host = getattr(args, "host", "127.0.0.1")
    port = getattr(args, "port", 8000)
    return run_demo(serve=(not no_serve), host=host, port=port)


def cmd_selftest(args: argparse.Namespace) -> int:
    """Run end-to-end self-test pipeline (Gate G8)."""
    from scripts.selftest import run_selftest

    full = getattr(args, "full", False)
    return run_selftest(full=full)


def cmd_ground(args: argparse.Namespace) -> int:
    """Execute ground command for You.com evidence retrieval and validation."""
    from grounding.fetch import fetch_all_evidence
    from grounding.judge import rebuild_grounding_json
    from grounding.youcom import YouComClient

    target_rules = None
    if getattr(args, "rules", None):
        target_rules = [r.strip() for r in args.rules.split(",") if r.strip()]

    refresh = getattr(args, "refresh", False)
    call_cap = getattr(args, "call_cap", 60)
    allow_keyless = getattr(args, "allow_keyless", False)

    if getattr(args, "fetch", False):
        print(f"[ground] Fetching evidence from You.com (call cap={call_cap}, refresh={refresh})...")
        client = YouComClient(call_cap=call_cap, allow_keyless=allow_keyless)
        fetched = fetch_all_evidence(client=client, rules=target_rules, refresh=refresh)
        print(f"[ground] Fetched evidence for {len(fetched)} rules. Calls used: {client.calls_used}/{call_cap}")
        rebuild_grounding_json()
        print("[ground] Rebuilt runs/grounding.json successfully.")
        return 0

    if getattr(args, "judge", False):
        from grounding.judge import run_judge
        print("[ground] Running model judge evaluation...")
        res = run_judge(rules=target_rules)
        print(f"[ground] Evaluated {len(res['data']['rules'])} rules using model '{res['judge_model']}'.")
        print(f"[ground] Model calls used: {res['model_calls_used']}. Label counts: {res['label_counts']}")
        return 0

    rebuild_grounding_json()
    print("[ground] Rebuilt runs/grounding.json from cache.")
    return 0


def make_stub(command_name: str, phase_name: str):
    """Return a stub command handler."""
    def handler(args: argparse.Namespace) -> int:
        print(f"Command '{command_name}' is not implemented yet ({phase_name}).")
        return 0
    return handler


def build_parser() -> argparse.ArgumentParser:
    """Build CLI parser."""
    parser = argparse.ArgumentParser(
        prog="paysift",
        description="PaySift: Stress-test AI-written payment code.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="Available subcommands")

    # Real commands
    p_check_env = subparsers.add_parser("check-env", help="Verify environment, Python, Docker, git and models config")
    p_check_env.set_defaults(func=cmd_check_env)

    p_check_git = subparsers.add_parser("check-git", help="Verify working tree remains uncommitted and unstaged")
    p_check_git.set_defaults(func=cmd_check_git)

    p_run = subparsers.add_parser("run", help="Run test suite against candidate handler")
    p_run.add_argument("--file", required=True, help="Path to candidate python file")
    p_run.add_argument("--mode", default="normal", choices=["normal", "restart"], help="Execution mode")
    p_run.add_argument("--seeds", default="0-99", help="Seed range start-end (default: 0-99)")
    p_run.add_argument("--sandbox", action="store_true", help="Execute inside Docker sandbox")
    p_run.add_argument("--amount-pass", action="store_true", help="Enable optional amount-shrinking pass")
    p_run.set_defaults(func=cmd_run)

    p_shrink = subparsers.add_parser("shrink", help="Delta-debug a failing event stream down to minimal repro")
    p_shrink.add_argument("--run", required=True, help="Path to Run JSON file")
    p_shrink.add_argument("--failure", type=int, default=0, help="Index of failure to shrink (default: 0)")
    p_shrink.add_argument("--amount-pass", action="store_true", help="Enable optional amount-shrinking pass")
    p_shrink.set_defaults(func=cmd_shrink)

    p_km = subparsers.add_parser("kill-matrix", help="Run kill matrix across reference and all mutants")
    p_km.set_defaults(func=cmd_kill_matrix)

    p_sbx = subparsers.add_parser("sandbox-test", help="Verify sandbox isolation with hostile handlers and parity")
    p_sbx.set_defaults(func=cmd_sandbox_test)

    p_gen = subparsers.add_parser("generate", help="Generate candidate payment webhook handlers from models")
    p_gen.add_argument("--dry-run", action="store_true", help="Print plan without calling APIs")
    p_gen.add_argument("--limit", type=int, default=None, help="Limit number of candidates generated")
    p_gen.add_argument("--models", type=str, default=None, help="Comma-separated model names")
    p_gen.add_argument("--stale-only", action="store_true", help="Only generate candidates missing or with stale spec_sha")
    p_gen.add_argument("--regen-all", action="store_true", help="Move old candidates to _stale/ before generating")
    p_gen.set_defaults(func=cmd_generate)

    p_pilot = subparsers.add_parser("pilot", help="Run pilot verification on model candidates inside Docker sandbox")
    p_pilot.add_argument("--force", action="store_true", help="Force re-running existing candidates")
    p_pilot.add_argument("--models", type=str, default=None, help="Comma-separated model names to filter")
    p_pilot.add_argument("--limit", type=int, default=None, help="Limit number of candidates to run")
    p_pilot.set_defaults(func=cmd_pilot)

    p_rep = subparsers.add_parser("repair", help="Execute repair loop on a failing candidate run")
    p_rep.add_argument("--run", type=str, default=None, help="Run JSON path or ID to repair")
    p_rep.add_argument("--candidate", type=str, default=None, help="Alias for candidate/run target")
    p_rep.add_argument("--failure", type=int, default=0, help="Failure index to repair")
    p_rep.add_argument("--stub", action="store_true", help="Force stub repair using reference stand-in")
    p_rep.set_defaults(func=cmd_repair)

    p_rpt = subparsers.add_parser("report", help="Generate static HTML reports under report/out/")
    p_rpt.add_argument("--out", type=str, default="report/out", help="Output directory for reports")
    p_rpt.set_defaults(func=cmd_report)

    p_srv = subparsers.add_parser("serve", help="Start PaySift FastAPI backend server via uvicorn")
    p_srv.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    p_srv.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    p_srv.set_defaults(func=cmd_serve)

    p_demo = subparsers.add_parser("demo", help="Run one-command offline demonstration of PaySift")
    p_demo.add_argument("--no-serve", action="store_true", help="Prepare demo reports and print URLs without starting server")
    p_demo.add_argument("--host", type=str, default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    p_demo.add_argument("--port", type=int, default=8000, help="Port (default: 8000)")
    p_demo.set_defaults(func=cmd_demo)

    p_selftest = subparsers.add_parser("selftest", help="Run end-to-end self-test pipeline (Gate G8)")
    p_selftest.add_argument("--full", action="store_true", help="Run full suite including all hostile tests & parity")
    p_selftest.set_defaults(func=cmd_selftest)

    p_ground = subparsers.add_parser("ground", help="You.com evidence retrieval, caching, and model evaluation")
    p_ground.add_argument("--fetch", action="store_true", help="Fetch and cache evidence from You.com")
    p_ground.add_argument("--judge", action="store_true", help="Evaluate evidence with model judge")
    p_ground.add_argument("--rules", type=str, default=None, help="Comma-separated list of rule IDs (e.g. R1,R3)")
    p_ground.add_argument("--refresh", action="store_true", help="Refresh existing cached evidence")
    p_ground.add_argument("--rebuild", action="store_true", help="Rebuild runs/grounding.json from cache")
    p_ground.add_argument("--allow-keyless", action="store_true", help="Allow keyless fallback route if YDC_API_KEY unset")
    p_ground.add_argument("--call-cap", type=int, default=60, help="Maximum allowed You.com API calls (default: 60)")
    p_ground.set_defaults(func=cmd_ground)

    # All subcommands implemented - no stubs remain
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
