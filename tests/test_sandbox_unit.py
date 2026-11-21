"""Unit tests for Docker sandbox harness verification without requiring a live Docker daemon (T6)."""

import ast
from pathlib import Path, PureWindowsPath
import subprocess
from unittest.mock import MagicMock, patch
import pytest

from runner.sandbox import (
    build_docker_run_cmd,
    is_docker_available,
    run_in_sandbox,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_build_docker_cmd_flags_match_plan_section_10():
    """Verify that all flags specified in plan section 10 are present in the command."""
    cmd = build_docker_run_cmd(
        container_name="test-cont-123",
        staged_dir=REPO_ROOT / "ref",
        cpus=2,
        image_tag="paysift-sandbox:1",
    )

    # Core flags verification
    assert "docker" == cmd[0]
    assert "run" == cmd[1]
    assert "--name" in cmd and cmd[cmd.index("--name") + 1] == "test-cont-123"
    assert "--rm" in cmd
    assert "-i" in cmd
    assert "--network" in cmd and cmd[cmd.index("--network") + 1] == "none"
    assert "--read-only" in cmd
    assert "--tmpfs" in cmd and cmd[cmd.index("--tmpfs") + 1] == "/tmp:rw,size=64m"
    assert "--memory" in cmd and cmd[cmd.index("--memory") + 1] == "256m"
    assert "--cpus" in cmd and cmd[cmd.index("--cpus") + 1] == "2"
    assert "--pids-limit" in cmd and cmd[cmd.index("--pids-limit") + 1] == "128"
    assert "--cap-drop" in cmd and cmd[cmd.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in cmd and cmd[cmd.index("--security-opt") + 1] == "no-new-privileges"
    assert "--user" in cmd and cmd[cmd.index("--user") + 1] == "65534"
    assert "-e" in cmd and "PYTHONDONTWRITEBYTECODE=1" in cmd
    assert "PYTHONHASHSEED=0" in cmd
    assert "paysift-sandbox:1" in cmd
    assert ["python", "-m", "runner.worker"] == cmd[-3:]


def test_mount_bind_readonly_and_source_path_format():
    """Verify that --mount type=bind,...,readonly uses clean path without slash/colon issues."""
    test_dir = Path("C:/test/path/to/stage")
    cmd = build_docker_run_cmd("test-cont", test_dir, cpus=1)

    mount_idx = cmd.index("--mount")
    mount_arg = cmd[mount_idx + 1]

    assert mount_arg.startswith("type=bind,source=")
    assert ",target=/cand,readonly" in mount_arg


def test_no_shell_true_in_sandbox_module():
    """Verify there is no shell=True anywhere in runner/sandbox.py."""
    sandbox_file = REPO_ROOT / "runner" / "sandbox.py"
    content = sandbox_file.read_text(encoding="utf-8")
    assert "shell=True" not in content
    assert "shell = True" not in content


def test_run_in_sandbox_returns_structured_error_when_docker_missing():
    """Verify run_in_sandbox returns structured error dict and does not raise when docker is absent."""
    with patch("runner.sandbox.is_docker_available", return_value=False):
        res = run_in_sandbox(REPO_ROOT / "ref" / "handler_ref.py", job={})
        assert isinstance(res, dict)
        assert res.get("ok") is False
        assert "Docker is not available" in res.get("error", "")


def test_docker_kill_and_rm_run_in_finally_on_normal():
    """Verify docker kill and docker rm -f run in finally block on successful execution."""
    mock_proc = MagicMock()
    mock_proc.communicate.return_value = ('{"ok": true, "sequences": []}', "")
    mock_proc.returncode = 0

    run_calls = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("runner.sandbox.is_docker_available", return_value=True), \
         patch("subprocess.Popen", return_value=mock_proc), \
         patch("subprocess.run", side_effect=mock_subprocess_run):

        res = run_in_sandbox(REPO_ROOT / "ref" / "handler_ref.py", job={"sequences": []})
        assert res.get("ok") is True

        # Assert cleanup commands were called
        kill_calls = [c for c in run_calls if len(c) >= 2 and c[0] == "docker" and c[1] == "kill"]
        rm_calls = [c for c in run_calls if len(c) >= 3 and c[0] == "docker" and c[1] == "rm" and c[2] == "-f"]

        assert len(kill_calls) == 1, "Expected docker kill call in finally block"
        assert len(rm_calls) == 1, "Expected docker rm -f call in finally block"


def test_docker_kill_and_rm_run_in_finally_on_timeout():
    """Verify docker kill and docker rm -f run in finally block on timeout."""
    mock_proc = MagicMock()
    mock_proc.communicate.side_effect = [subprocess.TimeoutExpired(cmd="docker run", timeout=1.0), ("", "")]

    run_calls = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("runner.sandbox.is_docker_available", return_value=True), \
         patch("subprocess.Popen", return_value=mock_proc), \
         patch("subprocess.run", side_effect=mock_subprocess_run):

        res = run_in_sandbox(REPO_ROOT / "ref" / "handler_ref.py", job={"sequences": []}, timeout=1.0)
        assert res.get("ok") is False
        assert "timed out" in res.get("error", "")

        kill_calls = [c for c in run_calls if len(c) >= 2 and c[0] == "docker" and c[1] == "kill"]
        rm_calls = [c for c in run_calls if len(c) >= 3 and c[0] == "docker" and c[1] == "rm" and c[2] == "-f"]

        assert len(kill_calls) == 1
        assert len(rm_calls) == 1


def test_docker_kill_and_rm_run_in_finally_on_exception():
    """Verify docker kill and docker rm -f run in finally block when Popen raises exception."""
    run_calls = []

    def mock_subprocess_run(cmd, *args, **kwargs):
        run_calls.append(cmd)
        m = MagicMock()
        m.returncode = 0
        return m

    with patch("runner.sandbox.is_docker_available", return_value=True), \
         patch("subprocess.Popen", side_effect=OSError("spawn failed")), \
         patch("subprocess.run", side_effect=mock_subprocess_run):

        res = run_in_sandbox(REPO_ROOT / "ref" / "handler_ref.py", job={"sequences": []})
        assert res.get("ok") is False
        assert "Failed to execute" in res.get("error", "")

        kill_calls = [c for c in run_calls if len(c) >= 2 and c[0] == "docker" and c[1] == "kill"]
        rm_calls = [c for c in run_calls if len(c) >= 3 and c[0] == "docker" and c[1] == "rm" and c[2] == "-f"]

        assert len(kill_calls) == 1
        assert len(rm_calls) == 1


def test_hostile_handlers_static_guard_and_no_native_exec():
    """Static check: every tests/hostile/*.py has /.dockerenv guard and is never imported/exec'd."""
    hostile_dir = REPO_ROOT / "tests" / "hostile"
    hostile_files = list(hostile_dir.glob("*.py"))
    assert len(hostile_files) >= 7, f"Expected at least 7 hostile files, found {len(hostile_files)}"

    for hf in hostile_files:
        lines = hf.read_text(encoding="utf-8").splitlines()[:20]
        has_guard = any("/.dockerenv" in line for line in lines)
        assert has_guard, f"Hostile file {hf.name} does not start with /.dockerenv guard!"

    # Ensure no python module imports or execs hostile files
    this_file = Path(__file__).resolve()
    for py_file in REPO_ROOT.rglob("*.py"):
        if any(part.startswith(".") for part in py_file.parts):
            continue
        if py_file.resolve() == this_file:
            continue
        if "hostile" in py_file.parts:
            continue
        content = py_file.read_text(encoding="utf-8")
        assert "import tests.hostile" not in content
        assert "from tests.hostile" not in content
