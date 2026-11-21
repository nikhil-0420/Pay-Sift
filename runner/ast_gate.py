"""AST Allowlist Gate for PaySift Candidate Verification.

Parses candidate code statically using ast.parse ONLY.
Never imports or executes candidate code.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union


ALLOWED_MODULES: Set[str] = {
    "sqlite3",
    "hmac",
    "hashlib",
    "json",
    "time",
    "typing",
    "contextlib",
}

FORBIDDEN_CALLS: Set[str] = {
    "exec",
    "eval",
    "open",
    "__import__",
    "compile",
    "breakpoint",
    "input",
}


class CandidateASTVisitor(ast.NodeVisitor):
    """Inspects AST nodes for disallowed imports and dangerous built-in calls."""

    def __init__(self) -> None:
        self.violations: List[Dict[str, Any]] = []
        self.allowed_future_imports: List[str] = []

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top_level = alias.name.split(".")[0]
            if top_level not in ALLOWED_MODULES:
                self.violations.append({
                    "kind": "disallowed_import",
                    "name": alias.name,
                    "line": getattr(node, "lineno", 0),
                })
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module == "__future__":
            for alias in node.names:
                self.allowed_future_imports.append(alias.name)
            self.generic_visit(node)
            return

        if not node.module:
            self.violations.append({
                "kind": "disallowed_import",
                "name": "relative_import",
                "line": getattr(node, "lineno", 0),
            })
            self.generic_visit(node)
            return

        top_level = node.module.split(".")[0]
        if top_level not in ALLOWED_MODULES:
            self.violations.append({
                "kind": "disallowed_import",
                "name": node.module,
                "line": getattr(node, "lineno", 0),
            })
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct call by name (e.g. open(...), eval(...))
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                self.violations.append({
                    "kind": "forbidden_call",
                    "name": node.func.id,
                    "line": getattr(node, "lineno", 0),
                })
        # Check call via attribute if attr matches (e.g. builtins.open(...))
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in FORBIDDEN_CALLS:
                self.violations.append({
                    "kind": "forbidden_call",
                    "name": node.func.attr,
                    "line": getattr(node, "lineno", 0),
                })
        self.generic_visit(node)


def check_ast(source_code: str) -> Dict[str, Any]:
    """Inspect source code string statically against allowlist rules.

    Returns:
        {
            "ok": bool,
            "violations": list[dict],
            "allowed_future": list[str],
        }
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError as exc:
        return {
            "ok": False,
            "violations": [{
                "kind": "syntax_error",
                "name": str(exc),
                "line": exc.lineno or 0,
            }],
            "allowed_future": [],
        }

    visitor = CandidateASTVisitor()
    visitor.visit(tree)

    return {
        "ok": len(visitor.violations) == 0,
        "violations": visitor.violations,
        "allowed_future": visitor.allowed_future_imports,
    }


def check_file(file_path: Union[str, Path]) -> Dict[str, Any]:
    """Inspect a python file statically against allowlist rules."""
    path = Path(file_path)
    if not path.is_file():
        return {
            "ok": False,
            "violations": [{
                "kind": "file_not_found",
                "name": str(path),
                "line": 0,
            }],
            "allowed_future": [],
        }

    try:
        content = path.read_text(encoding="utf-8")
    except Exception as exc:
        return {
            "ok": False,
            "violations": [{
                "kind": "read_error",
                "name": str(exc),
                "line": 0,
            }],
            "allowed_future": [],
        }

    return check_ast(content)
