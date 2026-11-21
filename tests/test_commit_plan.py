"""Test that every path referenced in scripts/commit_plan.md exists."""

from pathlib import Path
import re
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_every_path_in_commit_plan_exists():
    """Verify that all files/directories listed in git add commands exist on disk."""
    plan_file = REPO_ROOT / "scripts" / "commit_plan.md"
    assert plan_file.is_file(), "scripts/commit_plan.md must exist"

    content = plan_file.read_text(encoding="utf-8")
    add_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith("git add ") and not line.strip().endswith("-A")
    ]

    assert len(add_lines) > 0, "Expected git add commands in commit_plan.md"

    checked_paths = 0
    for line in add_lines:
        tokens = line[len("git add "):].strip().split()
        for token in tokens:
            token = token.strip()
            if not token or token.startswith("-"):
                continue
            path = REPO_ROOT / token
            assert path.exists(), f"Path '{token}' listed in scripts/commit_plan.md does not exist!"
            checked_paths += 1

    assert checked_paths >= 20, f"Expected at least 20 paths checked, got {checked_paths}"
