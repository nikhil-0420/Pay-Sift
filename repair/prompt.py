"""Repair prompt generator for PaySift candidate handlers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_repair_prompt(
    failing_code: str,
    minimal_trace: List[Dict[str, Any]],
    rule_id: str,
    rule_text: str,
    invariant: str,
    explanation: str,
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

    return f"""You are fixing a Python payment webhook handler for PaySift.
The handler currently contains a bug that violates the financial contract.

======================================================================
VIOLATED RULE: Rule {rule_id}
{rule_text}
======================================================================
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
