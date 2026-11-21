"""Docker Sandbox Execution Harness for PaySift Candidate Verification.

Runs untrusted model-generated candidate handlers inside an isolated Docker container
with strict security limits (--network none, --read-only, --tmpfs /tmp, non-root user 65534).
"""

from __future__ import annotations

import json
from pathlib import Path, PureWindowsPath
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid


_docker_available_cache: Optional[bool] = None
_docker_image_cache: Dict[str, bool] = {}


def is_docker_available(force_refresh: bool = False) -> bool:
    """Return True if docker executable is in PATH and daemon is reachable."""
    global _docker_available_cache
    if _docker_available_cache is not None and not force_refresh:
        return _docker_available_cache

    docker_bin = shutil.which("docker")
    if not docker_bin:
        _docker_available_cache = False
        return False
    try:
        res = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15.0,
            check=False,
        )
        _docker_available_cache = (res.returncode == 0)
        return _docker_available_cache
    except Exception:
        _docker_available_cache = False
        return False


def is_docker_image_available(image_name: str = "paysift-sandbox:1", force_refresh: bool = False) -> bool:
    """Return True if target docker image is available locally."""
    if not is_docker_available():
        return False
    if image_name in _docker_image_cache and not force_refresh:
        return _docker_image_cache[image_name]
    try:
        res = subprocess.run(
            ["docker", "image", "inspect", image_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15.0,
            check=False,
        )
        _docker_image_cache[image_name] = (res.returncode == 0)
        return _docker_image_cache[image_name]
    except Exception:
        _docker_image_cache[image_name] = False
        return False


def build_sandbox_image(image_tag: str = "paysift-sandbox:1") -> Tuple[bool, str]:
    """Build the sandbox image from runner/Dockerfile."""
    if not is_docker_available():
        return False, "Docker is not available"

    root = Path(__file__).resolve().parent.parent
    dockerfile = root / "runner" / "Dockerfile"
    if not dockerfile.is_file():
        return False, f"Dockerfile not found at {dockerfile}"

    cmd = [
        "docker",
        "build",
        "-t",
        image_tag,
        "-f",
        str(dockerfile),
        str(root),
    ]

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120.0,
            check=False,
        )
        if proc.returncode == 0:
            return True, "Build successful"
        return False, proc.stderr[:1000]
    except Exception as exc:
        return False, str(exc)


def build_docker_run_cmd(
    container_name: str,
    staged_dir: Union[str, Path],
    cpus: int = 1,
    image_tag: str = "paysift-sandbox:1",
) -> List[str]:
    """Construct docker run argument list according to plan section 10."""
    staged_path = Path(staged_dir).resolve()
    # Format Windows path cleanly using forward slashes
    mount_source = staged_path.as_posix()
    mount_arg = f"type=bind,source={mount_source},target=/cand,readonly"

    return [
        "docker",
        "run",
        "--name",
        container_name,
        "--rm",
        "-i",
        "--network",
        "none",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,size=64m",
        "--memory",
        "256m",
        "--cpus",
        str(cpus),
        "--pids-limit",
        "128",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--user",
        "65534",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
        "-e",
        "PYTHONHASHSEED=0",
        "--mount",
        mount_arg,
        image_tag,
        "python",
        "-m",
        "runner.worker",
    ]


class SandboxResultPayload(dict):
    """Result dictionary supporting both dict ['sequences'] and list [i] access."""

    def __getitem__(self, key: Any) -> Any:
        if isinstance(key, int):
            return self.get("sequences", [])[key]
        return super().__getitem__(key)

    def __iter__(self):
        if "sequences" in self:
            return iter(self["sequences"])
        return super().__iter__()

    def __len__(self) -> int:
        if "sequences" in self:
            return len(self["sequences"])
        return super().__len__()


def run_in_sandbox(
    candidate_file: Union[str, Path],
    job: Dict[str, Any],
    mode: str = "normal",
    cpus: int = 1,
    timeout: Optional[float] = None,
    image_tag: str = "paysift-sandbox:1",
) -> Dict[str, Any]:
    """Execute candidate job inside Docker sandbox.

    Args:
        candidate_file: Path to candidate python file on host.
        job: Worker job specification dictionary.
        mode: Execution mode ('normal', 'restart', 'concurrency').
        cpus: Number of CPU cores allocated (1 for normal/restart, 2 for concurrency).
        timeout: Total execution timeout in seconds.
        image_tag: Tag of the sandbox docker image.

    Returns:
        {"ok": bool, "results": list[dict]} on success, or {"ok": False, "error": str}.
    """
    if timeout is None or timeout == 60.0:
        num_seq = len(job.get("sequences", []))
        if num_seq > 20:
            timeout = max(timeout or 60.0, num_seq * 3.0 + 30.0)
        elif timeout is None:
            timeout = 60.0
    if not is_docker_available():
        return {
            "ok": False,
            "error": "Docker is not available on this host: Gate 4 BLOCKED.",
        }

    cand_path = Path(candidate_file).resolve()
    if not cand_path.is_file():
        return {"ok": False, "error": f"Candidate file not found: {cand_path}"}

    container_id = f"paysift-{uuid.uuid4().hex[:12]}"

    # Stage candidate in a temporary directory containing handler.py
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str).resolve()
        staged_file = tmp_dir / "handler.py"
        shutil.copyfile(cand_path, staged_file)

        # Build job JSON for container worker
        container_job = dict(job)
        container_job["candidate_file"] = "/cand/handler.py"
        container_job["mode"] = mode
        container_job["is_sandbox"] = True
        job_json = json.dumps(container_job)

        cmd = build_docker_run_cmd(
            container_name=container_id,
            staged_dir=tmp_dir,
            cpus=cpus,
            image_tag=image_tag,
        )

        proc: Optional[subprocess.Popen] = None
        stdout_data = ""
        stderr_data = ""
        timed_out = False

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )

            try:
                stdout_data, stderr_data = proc.communicate(input=job_json, timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                proc.kill()
                stdout_data, stderr_data = proc.communicate()

        except Exception as exc:
            return {"ok": False, "error": f"Failed to execute container process: {exc}"}
        finally:
            # Ensure container is killed and removed by name
            for cleanup_subcmd in [["docker", "kill", container_id], ["docker", "rm", "-f", container_id]]:
                try:
                    subprocess.run(
                        cleanup_subcmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=5.0,
                        check=False,
                    )
                except Exception:
                    pass

        if timed_out:
            return {
                "ok": False,
                "error": f"Container execution timed out after {timeout}s",
                "stderr": stderr_data[:2000],
            }

        if proc is not None and proc.returncode != 0:
            return {
                "ok": False,
                "error": f"Container exited with code {proc.returncode}",
                "stderr": stderr_data[:2000],
            }

        try:
            raw_parsed = json.loads(stdout_data.strip())
            if isinstance(raw_parsed, dict):
                seqs = raw_parsed.get("sequences", [])
                for seq in seqs:
                    if "results" in seq and "steps" not in seq:
                        seq["steps"] = seq["results"]
                    elif "steps" in seq and "results" not in seq:
                        seq["results"] = seq["steps"]
                results = SandboxResultPayload(raw_parsed)
            elif isinstance(raw_parsed, list):
                for seq in raw_parsed:
                    if "results" in seq and "steps" not in seq:
                        seq["steps"] = seq["results"]
                    elif "steps" in seq and "results" not in seq:
                        seq["results"] = seq["steps"]
                results = SandboxResultPayload({"sequences": raw_parsed})
            else:
                results = raw_parsed
            return {"ok": True, "results": results}
        except json.JSONDecodeError as exc:
            return {
                "ok": False,
                "error": f"Invalid JSON returned from container worker: {exc}",
                "raw_stdout": stdout_data[:2000],
                "stderr": stderr_data[:2000],
            }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Execute candidate inside PaySift Docker sandbox.")
    parser.add_argument("--file", required=True, help="Path to candidate python file")
    parser.add_argument("--mode", default="normal", choices=["normal", "restart", "concurrency"], help="Execution mode")
    parser.add_argument("--cpus", type=int, default=1, help="CPUs allocation")
    parser.add_argument("--timeout", type=float, default=60.0, help="Sandbox timeout")
    parser.add_argument("--print-cmd", action="store_true", help="Print docker run argument list and exit without executing")
    args = parser.parse_args()

    if args.print_cmd:
        cand_p = Path(args.file).resolve()
        staged_dir = cand_p.parent
        cmd = build_docker_run_cmd("paysift-preview", staged_dir, cpus=args.cpus)
        print(cmd)
        sys.exit(0)

    dummy_job = {"candidate_file": args.file, "mode": args.mode, "sequences": []}
    res = run_in_sandbox(args.file, dummy_job, mode=args.mode, cpus=args.cpus, timeout=args.timeout)
    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("ok") else 1)
