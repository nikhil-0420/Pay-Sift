"""Worker process executing candidate sequences and capturing independent DB snapshots.

Enforces:
- native_allowed(candidate_path): trusted paths only natively (ref/ or mutants/)
- fresh DB per sequence
- independent snapshot query by worker (never trusting candidate)
- 5s per-call timeout and 30s per-sequence timeout
"""

from __future__ import annotations

import json
from pathlib import Path
import queue
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Tuple


def native_allowed(candidate_path: Path, is_sandbox: bool = False) -> bool:
    """Verify whether candidate file is allowed to execute natively on host."""
    if is_sandbox:
        return True

    repo_root = Path(__file__).resolve().parent.parent
    ref_dir = (repo_root / "ref").resolve()
    mutants_dir = (repo_root / "mutants").resolve()

    resolved = candidate_path.resolve()
    try:
        resolved.relative_to(ref_dir)
        return True
    except ValueError:
        pass

    try:
        resolved.relative_to(mutants_dir)
        return True
    except ValueError:
        pass

    return False


def init_db(db_path: Path, schema_path: Path) -> None:
    """Initialize SQLite database with harness schema."""
    schema_sql = schema_path.read_text(encoding="utf-8")
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def query_snapshot(db_path: Path) -> Dict[str, Any]:
    """Capture independent DB snapshot of payments and ledger tables."""
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    try:
        cur = conn.cursor()
        cur.execute("SELECT payment_id, captured_paise, refunded_paise FROM payments ORDER BY payment_id")
        payments = [
            {"payment_id": row[0], "captured_paise": row[1], "refunded_paise": row[2]}
            for row in cur.fetchall()
        ]

        cur.execute("SELECT entry_id, payment_id, kind, amount_paise, event_id FROM ledger ORDER BY entry_id")
        ledger = [
            {"entry_id": row[0], "payment_id": row[1], "kind": row[2], "amount_paise": row[3], "event_id": row[4]}
            for row in cur.fetchall()
        ]

        summary: Dict[str, Dict[str, int]] = {}
        for entry in ledger:
            pid = entry["payment_id"]
            if pid not in summary:
                summary[pid] = {
                    "captures_count": 0,
                    "captures_sum": 0,
                    "refunds_count": 0,
                    "refunds_sum": 0,
                }
            if entry["kind"] == "capture":
                summary[pid]["captures_count"] += 1
                summary[pid]["captures_sum"] += entry["amount_paise"]
            elif entry["kind"] == "refund":
                summary[pid]["refunds_count"] += 1
                summary[pid]["refunds_sum"] += entry["amount_paise"]

        return {
            "payments": payments,
            "ledger": ledger,
            "summary": summary,
        }
    finally:
        conn.close()


def run_sequence_normal(
    candidate_path: Path,
    steps: List[Dict[str, str]],
    secret: str,
    schema_path: Path,
    child_script: Path,
    per_call_timeout: float = 5.0,
    seq_timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Execute a single stream sequence in normal mode (fresh process per sequence)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staged_candidate = tmp_dir / "handler.py"
        shutil.copyfile(candidate_path, staged_candidate)

        db_path = tmp_dir / "harness.db"
        init_db(db_path, schema_path)

        cmd = [
            sys.executable,
            str(child_script),
            "--candidate",
            str(staged_candidate),
            "--db",
            str(db_path),
            "--secret",
            secret,
        ]

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        out_queue: queue.Queue = queue.Queue()

        def reader_thread():
            try:
                for line in proc.stdout:
                    out_queue.put(line)
            except Exception:
                pass

        t = threading.Thread(target=reader_thread, daemon=True)
        t.start()

        results: List[Dict[str, Any]] = []
        seq_start = time.monotonic()
        timed_out = False

        for idx, step in enumerate(steps):
            if timed_out or (time.monotonic() - seq_start > seq_timeout):
                # Mark as sequence timeout
                results.append({
                    "step_index": idx,
                    "response": "timeout",
                    "snapshot": query_snapshot(db_path),
                })
                continue

            # Send step
            step_payload = json.dumps({
                "raw_body_b64": step["raw_body_b64"],
                "signature": step.get("signature", ""),
            }) + "\n"

            try:
                assert proc.stdin is not None
                proc.stdin.write(step_payload)
                proc.stdin.flush()
            except Exception as exc:
                results.append({
                    "step_index": idx,
                    "response": {"error": f"Child stdin error: {exc}"},
                    "snapshot": query_snapshot(db_path),
                })
                continue

            # Read response with 5s timeout
            try:
                line = out_queue.get(timeout=per_call_timeout)
                resp = json.loads(line.strip())
            except queue.Empty:
                # Per-call timeout
                timed_out = True
                try:
                    proc.kill()
                except Exception:
                    pass
                results.append({
                    "step_index": idx,
                    "response": "timeout",
                    "snapshot": query_snapshot(db_path),
                })
            except Exception as exc:
                results.append({
                    "step_index": idx,
                    "response": {"error": f"Invalid output from child: {exc}"},
                    "snapshot": query_snapshot(db_path),
                })
            else:
                results.append({
                    "step_index": idx,
                    "response": resp,
                    "snapshot": query_snapshot(db_path),
                })

        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except Exception:
            pass

        try:
            if proc.poll() is None:
                proc.kill()
            proc.wait(timeout=2.0)
        except Exception:
            pass

        try:
            if proc.stdout and not proc.stdout.closed:
                proc.stdout.close()
            if proc.stderr and not proc.stderr.closed:
                proc.stderr.close()
        except Exception:
            pass

        return results


def run_sequence_restart(
    candidate_path: Path,
    steps: List[Dict[str, str]],
    secret: str,
    schema_path: Path,
    child_script: Path,
    per_call_timeout: float = 5.0,
    seq_timeout: float = 30.0,
) -> List[Dict[str, Any]]:
    """Execute a single stream sequence in restart mode (fresh child process before EVERY call)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        staged_candidate = tmp_dir / "handler.py"
        shutil.copyfile(candidate_path, staged_candidate)

        db_path = tmp_dir / "harness.db"
        init_db(db_path, schema_path)

        results: List[Dict[str, Any]] = []
        seq_start = time.monotonic()
        timed_out = False

        for idx, step in enumerate(steps):
            if timed_out or (time.monotonic() - seq_start > seq_timeout):
                results.append({
                    "step_index": idx,
                    "response": "timeout",
                    "snapshot": query_snapshot(db_path),
                })
                continue

            cmd = [
                sys.executable,
                str(child_script),
                "--candidate",
                str(staged_candidate),
                "--db",
                str(db_path),
                "--secret",
                secret,
            ]

            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            line_to_send = json.dumps(step) + "\n"
            resp: Any = None
            try:
                stdout_data, stderr_data = proc.communicate(input=line_to_send, timeout=per_call_timeout)
                line = stdout_data.strip().splitlines()[0] if stdout_data.strip() else ""
                if not line:
                    resp = {"error": f"Child exited without output: {stderr_data[:500]}"}
                else:
                    resp = json.loads(line)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                resp = "timeout"
            except Exception as exc:
                resp = {"error": str(exc)}
            finally:
                try:
                    if proc.poll() is None:
                        proc.kill()
                    proc.wait(timeout=1.0)
                except Exception:
                    pass

            results.append({
                "step_index": idx,
                "response": resp,
                "snapshot": query_snapshot(db_path),
            })

        return results


def execute_job(job: Dict[str, Any], is_sandbox: bool = False) -> Dict[str, Any]:
    """Execute worker job dictionary and return structured sequence results."""
    candidate_file = Path(job["candidate_file"])
    if not native_allowed(candidate_file, is_sandbox=is_sandbox):
        raise PermissionError(
            f"Native execution forbidden for untrusted code: {candidate_file}. "
            "Must execute inside Docker sandbox (Rule 3)."
        )

    mode = job.get("mode", "normal")
    secret = job.get("secret", "paysift_secret_key_v1_offline_test")
    sequences = job.get("sequences", [])

    repo_root = Path(__file__).resolve().parent.parent
    schema_path = repo_root / "contract" / "schema.sql"
    child_script = repo_root / "runner" / "child.py"

    sequence_results = []
    for seq in sequences:
        seed = seq["seed"]
        steps = seq["steps"]
        if mode == "restart":
            res = run_sequence_restart(
                candidate_path=candidate_file,
                steps=steps,
                secret=secret,
                schema_path=schema_path,
                child_script=child_script,
            )
        else:
            res = run_sequence_normal(
                candidate_path=candidate_file,
                steps=steps,
                secret=secret,
                schema_path=schema_path,
                child_script=child_script,
            )
        sequence_results.append({
            "seed": seed,
            "results": res,
        })

    return {"sequences": sequence_results}


def main() -> int:
    """Worker CLI entry point: reads job JSON from stdin, writes results JSON to stdout."""
    try:
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            print(json.dumps({"error": "Empty job input"}), file=sys.stderr)
            return 1
        job = json.loads(raw_input)
        out = execute_job(job)
        print(json.dumps(out))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
