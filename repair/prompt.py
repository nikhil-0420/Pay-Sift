"""Repair prompt generator for PaySift candidate handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_grounding_for_rule(rule_id: str, grounding_file: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load sources from runs/grounding.json for a given rule_id if available."""
    gfile = grounding_file or Path("runs/grounding.json")
    if not gfile.is_file():
        return []
    try:
        data = json.loads(gfile.read_text(encoding="utf-8"))
        rules = data.get("rules", {})
        rule_info = rules.get(rule_id, {})
        return rule_info.get("sources", [])
    except Exception:
        return []


def build_repair_prompt(
    failing_code: str,
    minimal_trace: List[Dict[str, Any]],
    rule_id: str,
    rule_text: str,
    invariant: str,
    explanation: str,
    sources: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Construct the repair prompt sent to the LLM model to request corrected handler code."""
    trace_lines = []
    for idx, ev in enumerate(minimal_trace):
        summary = ev.get("summary")
        if not summary:
            t = ev.get("type", "event")
            eid = ev.get("event_id", "eid")
            amt = ev.get("amount_paise")
            amt_str = f"Rs {amt/100:.2f}" if isinstance(amt, int) else str(amt)
            summary = f"{t} {eid} ({amt_str})"
        trace_lines.append(f"{idx + 1}. {summary} [tag: {ev.get('tag', '-')}]")

    trace_str = "\n".join(trace_lines) if trace_lines else "Single-step or empty counterexample."

    if sources is None:
        sources = load_grounding_for_rule(rule_id)

    sources_section = ""
    if sources:
        lines = []
        for s in sources:
            sid = s.get("id", "")
            title = s.get("title", "")
            url = s.get("url", "")
            snippet = s.get("snippet", "")
            lines.append(f"- [{sid}] {title} ({url})\n  Snippet: {snippet}")
        sources_section = (
            "\n======================================================================\n"
            "OFFICIAL DOCUMENTATION & VERIFIED SOURCES (You.com Grounding):\n"
            + "\n".join(lines)
            + "\n======================================================================\n"
        )

    return f"""You are fixing a Python payment webhook handler for PaySift.
The handler currently contains a bug that violates the financial contract.

======================================================================
VIOLATED RULE: Rule {rule_id}
{rule_text}
======================================================================{sources_section}
INVARIANT: {invariant}

MINIMAL REPRODUCIBLE COUNTEREXAMPLE TRACE:
{trace_str}

FAILURE EXPLANATION:
{explanation}

CURRENT CODE:
```python
{failing_code}
```

REQUIREMENTS:
1. Return the complete corrected Python code in a single markdown ```python ... ``` fence.
2. The code must implement:
   def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> dict:
3. The returned dict must have "status" in {{"applied", "duplicate", "rejected"}} and a string "reason".
4. Use standard library modules only (sqlite3, json, hmac, hashlib, time, typing). No external imports.
5. Do not use open(), exec(), eval(), compile(), or __import__().
6. Fix the bug cleanly while preserving full compliance across all rules R0 through R10.
"""
