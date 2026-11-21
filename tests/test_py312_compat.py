"""Test Python 3.12 compatibility across all repository Python source files."""

import ast
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_all_python_files_compatible_with_py312():
    """Verify every .py file compiles with ast.parse feature_version=(3, 12)."""
    checked = 0
    failures = []

    for path in REPO_ROOT.rglob("*.py"):
        # Ignore virtual environments, git metadata, and build dirs
        if any(part.startswith(".") for part in path.parts):
            continue

        checked += 1
        source = path.read_text(encoding="utf-8")
        try:
            ast.parse(source, filename=str(path), feature_version=(3, 12))
        except SyntaxError as exc:
            failures.append((str(path.relative_to(REPO_ROOT)), str(exc)))

    assert checked >= 50, f"Expected at least 50 python files scanned, found {checked}"
    assert not failures, f"Python 3.12 incompatible files found: {failures}"
