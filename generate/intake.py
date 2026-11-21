"""Intake and code extraction module for model-generated candidates.

This module NEVER executes candidates. It only parses code using ast.parse via runner/ast_gate.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from runner.ast_gate import check_ast


def extract_code(raw_text: str) -> str:
    """Extract Python code from markdown fences if present, else return raw text.

    Extraction logic:
    1. Scans for the first occurrence of a markdown code block starting with ```python or ```
       and ending with ```.
    2. If found, extracts the inner content between the fences, stripping surrounding whitespace
       while ensuring a trailing newline.
    3. If no code fence is detected, uses the raw text directly.
    4. Never modifies code logic, syntax, imports, or statements.
    """
    pattern = r"```(?:python|py)?\s*\n(.*?)```"
    match = re.search(pattern, raw_text, re.DOTALL | re.IGNORECASE)
    if match:
        code = match.group(1).strip()
    else:
        # Fallback to raw text without markdown fences
        code = raw_text.strip()

    if code and not code.endswith("\n"):
        code += "\n"
    return code


def intake_candidate(raw_text: str) -> Dict[str, Any]:
    """Process raw model response text: extract code and run AST security gate.

    Returns a dictionary containing:
      - 'code': extracted Python code string
      - 'compliant': bool (True if AST gate passes with no disallowed imports/calls)
      - 'violations': list of violation dicts from AST gate
      - 'allowed_future': list of allowed __future__ imports
    """
    code = extract_code(raw_text)
    ast_res = check_ast(code)

    return {
        "code": code,
        "compliant": ast_res["ok"],
        "violations": ast_res.get("violations", []),
        "allowed_future": ast_res.get("allowed_future", []),
    }
