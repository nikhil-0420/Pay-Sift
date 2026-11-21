"""Tests for cli.py commands (check-env and check-git)."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

import cli


def test_check_env_execution_and_shape(tmp_path: Path):
    """Test that check-env runs, returns 0, and produces valid JSON report."""
    ret = cli.main(["check-env"])
    assert ret == 0

    json_path = Path("E:/PaySift/.agent/check_env.json")
    assert json_path.is_file()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert "python" in data
    assert "version" in data["python"]
    assert "docker" in data
    assert "cli_present" in data["docker"]
    assert "git" in data
    assert "head" in data["git"]
    assert "api_keys" in data
    assert "models_config" in data
    assert "filled" in data["models_config"]


def test_demo_command_no_serve():
    """Test that demo CLI command runs offline reports and returns 0 without launching webserver."""
    ret = cli.main(["demo", "--no-serve"])
    assert ret == 0


def test_selftest_command_help():
    """Test that selftest CLI command parses arguments and displays help."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["selftest", "--help"])
    assert exc.value.code == 0


def test_report_command_execution():
    """Test that report CLI command runs and generates static HTML files."""
    ret = cli.main(["report"])
    assert ret == 0


def test_repair_command_help():
    """Test that repair CLI command parses arguments and displays help."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["repair", "--help"])
    assert exc.value.code == 0


def test_serve_command_help():
    """Test that serve CLI command parses arguments and displays help."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["serve", "--help"])
    assert exc.value.code == 0


def test_generate_command_dry_run():
    """Test that generate CLI command executes dry-run plan cleanly."""
    ret = cli.main(["generate", "--dry-run"])
    assert ret == 0


def test_shrink_command_help():
    """Test that shrink CLI command parses arguments and displays help."""
    with pytest.raises(SystemExit) as exc:
        cli.main(["shrink", "--help"])
    assert exc.value.code == 0


def test_run_command_execution():
    """Test that cli run command executes successfully on ref/handler_ref.py."""
    ret = cli.main(["run", "--file", "ref/handler_ref.py", "--seeds", "0-1"])
    assert ret == 0


def test_check_git_passes_on_uncommitted_working_tree():
    """Test that check-git passes on the current project repository."""
    ret = cli.main(["check-git"])
    assert ret == 0


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Create an isolated temporary git repository for testing check-git logic."""
    repo = tmp_path / "temp_repo"
    repo.mkdir()

    # Configure user in temp repo so git commands work cleanly
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "TestUser"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)

    agent_dir = repo / ".agent"
    agent_dir.mkdir()

    # Baseline with NO_COMMITS
    baseline_content = """=== TIMESTAMP ===
2026-11-21T00:00:00+00:00
=== HEAD ===
NO_COMMITS
=== STATUS_PORCELAIN ===
=== DIFF_CACHED ===
=== STASH_LIST ===
=== BRANCH_LIST ===
=== TAG_LIST ===
"""
    (agent_dir / "git_baseline.txt").write_text(baseline_content, encoding="utf-8")
    return repo


def test_check_git_logic_fails_when_staged_changes_exist(temp_git_repo: Path, monkeypatch):
    """Test that check-git fails (exit 1) if anything is staged in the repo."""
    test_file = temp_git_repo / "staged_file.txt"
    test_file.write_text("hello", encoding="utf-8")

    subprocess.run(["git", "add", "staged_file.txt"], cwd=temp_git_repo, check=True, capture_output=True)

    # Monkeypatch cli.py to run inside temp_git_repo
    monkeypatch.setattr(cli, "__file__", str(temp_git_repo / "cli.py"))

    ret = cli.cmd_check_git(cli.argparse.Namespace())
    assert ret == 1


def test_check_git_logic_fails_when_head_changed(temp_git_repo: Path, monkeypatch):
    """Test that check-git fails (exit 1) if HEAD changes from NO_COMMITS to a commit hash."""
    test_file = temp_git_repo / "file.txt"
    test_file.write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=temp_git_repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "first commit"], cwd=temp_git_repo, check=True, capture_output=True)

    monkeypatch.setattr(cli, "__file__", str(temp_git_repo / "cli.py"))

    ret = cli.cmd_check_git(cli.argparse.Namespace())
    assert ret == 1
