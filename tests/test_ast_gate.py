"""Unit tests for AST Allowlist Gate (runner/ast_gate.py)."""

from __future__ import annotations

import pytest
from runner.ast_gate import check_ast


def test_valid_code_passes():
    code = """
from __future__ import annotations
import sqlite3
import hmac
import hashlib
import json
import time
from typing import Dict, Any, Optional
import contextlib

def handle_event(db_path, raw_body, signature, secret):
    return {"status": "applied"}
"""
    res = check_ast(code)
    assert res["ok"] is True
    assert len(res["violations"]) == 0
    assert "annotations" in res["allowed_future"]


def test_disallowed_top_level_import():
    code = "import os\nimport sys"
    res = check_ast(code)
    assert res["ok"] is False
    assert len(res["violations"]) == 2
    names = [v["name"] for v in res["violations"]]
    assert "os" in names
    assert "sys" in names


def test_from_import_disallowed():
    code = "from subprocess import Popen, PIPE"
    res = check_ast(code)
    assert res["ok"] is False
    assert any(v["name"] == "subprocess" for v in res["violations"])


def test_import_aliasing():
    code = "import socket as sock\nfrom requests import get as fetch"
    res = check_ast(code)
    assert res["ok"] is False
    names = [v["name"] for v in res["violations"]]
    assert "socket" in names
    assert "requests" in names


def test_forbidden_calls_direct():
    forbidden = ["eval('1+1')", "exec('pass')", "open('/tmp/test', 'w')", "__import__('os')", "compile('x=1', '', 'exec')", "breakpoint()", "input('prompt')"]
    for call_stmt in forbidden:
        code = f"def foo():\n    {call_stmt}\n"
        res = check_ast(code)
        assert res["ok"] is False, f"Expected {call_stmt} to be flagged"
        assert res["violations"][0]["kind"] == "forbidden_call"


def test_nested_functions_and_classes():
    code = """
class Worker:
    def execute(self):
        def helper():
            return open("file.txt")
        return helper()
"""
    res = check_ast(code)
    assert res["ok"] is False
    assert res["violations"][0]["kind"] == "forbidden_call"
    assert res["violations"][0]["name"] == "open"


def test_attribute_calls():
    code = """
import builtins
def foo():
    return builtins.eval("2+2")
"""
    res = check_ast(code)
    assert res["ok"] is False
    assert any(v["name"] == "eval" for v in res["violations"])


def test_syntax_error_reported():
    code = "def invalid_syntax(:"
    res = check_ast(code)
    assert res["ok"] is False
    assert res["violations"][0]["kind"] == "syntax_error"
