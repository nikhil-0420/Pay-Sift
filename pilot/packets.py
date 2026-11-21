"""Failure Packet Generator for PaySift Pilot Runs.

Generates markdown packets under pilot/packets/<candidate_id>__<failure_index>.md
containing complete diagnostic context for human classification.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


RULE_TEXTS = {
    "R0": (
        "Totality & Interface: For every input the handler returns a dict containing 'status' in "
        "{'applied', 'duplicate', 'rejected'} and a string 'reason'. It never raises an uncaught exception "
        "and never hangs (timeout 5.0 s per call)."
    ),
    "R1": (
        "Signature Verification: The signature must equal the lowercase hex HMAC-SHA256 of the exact raw_body "
        "bytes, keyed with the UTF-8 secret. Any discrepancy (missing, empty, incorrect secret, corrupted/flipped byte, "
        "uppercase hex, non-ASCII characters, or signature computed over re-serialized JSON): return status 'rejected', "
        "commit no database state change, and raise no exception."
    ),
    "R2": (
        "Payload Validation: The raw_body must be valid UTF-8 JSON encoding a JSON object containing: "
        "event_id (non-empty string <= 64 chars), type ('payment.captured' or 'refund.processed'), "
        "payment_id (non-empty string <= 64 chars), amount_paise (strict JSON integer from 1 to 10^12 inclusive; "
        "not boolean, not float even if 5.0, not string, not null, not <= 0), and for 'refund.processed' "
        "additionally refund_id (non-empty string). Extra unrecognized JSON fields are permitted and ignored. "
        "Any violation: return status 'rejected' and commit no database state change."
    ),
    "R3": (
        "Event Idempotency: An event_id takes effect at most once. Redelivery of an already-applied event "
        "(with valid signature and payload): return status 'duplicate' and commit no database state change."
    ),
    "R4": (
        "Payment Capture: For payment.captured: if no capture exists for payment_id, insert into payments "
        "(captured_paise = amount, refunded_paise = 0) and insert exactly one 'capture' ledger entry "
        "(amount_paise = amount). If the payment already has a capture: return status 'rejected' and commit no state change."
    ),
    "R5": (
        "Refund Target Existence: For refund.processed: requires an existing captured payment in payments. "
        "If payment_id does not exist: return status 'rejected' and commit no state change."
    ),
    "R6": (
        "Refund Balance Bound: For refund.processed: total refunds cannot exceed capture amount "
        "(refunded_paise + amount_paise <= captured_paise). If amount exceeds remaining balance: "
        "return status 'rejected' and commit no state change. If valid: update payments "
        "(refunded_paise += amount_paise) and insert exactly one 'refund' ledger entry."
    ),
    "R7": (
        "Financial Atomicity: payments and ledger must always agree: captured_paise equals the sum of capture "
        "entries in ledger; refunded_paise equals the sum of refund entries in ledger. An event applies in full or not at all."
    ),
    "R8": (
        "Rejection Non-Consumption: A 'rejected' event produces no state change and does NOT consume its event_id. "
        "If the same event_id is redelivered later with valid parameters or prerequisites satisfied, it must be "
        "processed and applied normally."
    ),
    "R9": (
        "Durability Across Restarts: All state lives in the SQLite database. The handler process may be terminated "
        "and restarted between any two calls without losing idempotency or accounting integrity."
    ),
    "R10": (
        "Concurrency Safety: Calls may run concurrently in separate processes against the same database file. "
        "Rules R3 (idempotency) and R6 (refund bounds) must strictly hold under concurrent execution."
    ),
}


def classify_failure(candidate: Dict[str, Any], failure: Dict[str, Any]) -> Dict[str, str]:
    """Propose an agent classification (a)-(d) for a failure per plan section 11."""
    cond = candidate.get("condition", "-")
    rule = failure.get("rule", "Unknown")
    inv = failure.get("invariant", "Unknown")

    if cond == "B":
        return {
            "label": "d",
            "by": "agent-proposed",
            "note": f"Condition B failure against rule {rule}: prompt used casual style without explicit rules; illustrative only.",
        }

    # For Condition A or mutants/references
    return {
        "label": "a",
        "by": "agent-proposed",
        "note": f"Violates numbered rule {rule} as written under invariant {inv}.",
    }


def format_failure_packet(
    run_dict: Dict[str, Any],
    failure_index: int,
    candidate_code: str,
    candidate_path_str: str,
    run_path_str: str,
) -> str:
    """Format a failure packet in markdown per section 11 specifications."""
    cand = run_dict.get("candidate", {})
    failures = run_dict.get("failures", [])
    if failure_index >= len(failures):
        raise IndexError(f"Failure index {failure_index} out of range ({len(failures)} failures)")

    fail = failures[failure_index]
    cand_id = cand.get("id", "unknown")
    model_id = cand.get("model", "unknown")
    condition = cand.get("condition", "-")
    sample = cand.get("sample")
    sha256 = cand.get("sha256", "unknown")
    spec_sha = run_dict.get("spec_sha", "unknown")
    source_label = cand.get("label", cand.get("source", "unknown"))

    rule_id = fail.get("rule", "R0")
    rule_desc = RULE_TEXTS.get(rule_id, "Rule description not found.")
    invariant = fail.get("invariant", "unknown")
    mode = fail.get("mode", "normal")
    seed = fail.get("seed", 0)

    # Classification
    classification = fail.get("classification")
    if not classification or classification.get("label") == "unreviewed":
        classification = classify_failure(cand, fail)

    # Format trace
    trace_events = fail.get("minimal_stream") or fail.get("stream") or []
    trace_lines = []
    for idx, ev in enumerate(trace_events):
        summary = ev.get("summary")
        if not summary:
            t = ev.get("type", "event")
            eid = ev.get("event_id", "eid")
            amt = ev.get("amount_paise")
            amt_str = f"Rs {amt/100:.2f}" if isinstance(amt, int) else str(amt)
            summary = f"{t} {eid} ({amt_str})"
        trace_lines.append(f"{idx + 1}. `{summary}` [tag: {ev.get('tag', '-')}]")

    trace_block = "\n".join(trace_lines) if trace_lines else "No trace events recorded."

    # Format code snippet (<= 150 lines or first 150 lines + note)
    code_lines = candidate_code.splitlines()
    if len(code_lines) <= 150:
        code_block = candidate_code
        code_note = f"Full file ({len(code_lines)} lines)"
    else:
        code_block = "\n".join(code_lines[:150])
        code_note = f"First 150 lines of {len(code_lines)} total lines (path: `{candidate_path_str}`)"

    observed = fail.get("observed_state")
    expected = fail.get("expected_state")
    explanation = fail.get("explanation", "No explanation text available.")

    repro = fail.get("repro", {})
    repro_text = f"{repro.get('reproduced', 0)} of {repro.get('runs', 0)} runs" if repro else "Not tested"
    one_min = fail.get("one_minimal", False)

    return f"""# Failure Packet: `{cand_id}` (Failure #{failure_index})

## 1. Candidate Metadata
- **Candidate ID:** `{cand_id}`
- **Model:** `{model_id}`
- **Condition:** `{condition}`
- **Sample:** `{sample}`
- **SHA-256:** `{sha256}`
- **Spec SHA:** `{spec_sha}`
- **Source Label:** `{source_label}`
- **Run JSON:** [`{run_path_str}`](file:///{run_path_str.replace('\\', '/')})
- **Failing Seed:** `{seed}` (mode: `{mode}`)
- **Reproduction:** `{repro_text}` (1-minimal: `{one_min}`)

## 2. Violated Contract Rule
### **Rule {rule_id}** (Invariant `{invariant}`)
> {rule_desc}

## 3. Minimal Counterexample Trace
{trace_block}

## 4. Expected vs Observed State
- **Explanation:** {explanation}
- **Expected State:** `{expected if expected is not None else "N/A"}`
- **Observed State:** `{observed if observed is not None else "N/A"}`

## 5. Candidate Source Code
*{code_note}*
```python
{code_block}
```

## 6. Classification
- **Proposed Class:** `({classification.get('label')})`
- **Classified By:** `{classification.get('by')}`
- **Justification / Note:** {classification.get('note')}
- **Human Decision:** `PENDING HUMAN REVIEW`
"""


def write_failure_packet(
    run_dict: Dict[str, Any],
    failure_index: int,
    candidate_file: Path,
    output_dir: Path = Path("pilot/packets"),
    run_path: Optional[Path] = None,
) -> Path:
    """Generate and write a failure packet markdown file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cand = run_dict.get("candidate", {})
    cand_id = cand.get("id", "unknown")
    packet_path = output_dir / f"{cand_id}__{failure_index}.md"

    code_str = ""
    if candidate_file.exists():
        code_str = candidate_file.read_text(encoding="utf-8")
    else:
        code_str = f"# Candidate source file not found at {candidate_file}"

    run_path_str = str(run_path or f"runs/{run_dict.get('run_id')}.json")
    content = format_failure_packet(
        run_dict=run_dict,
        failure_index=failure_index,
        candidate_code=code_str,
        candidate_path_str=str(candidate_file),
        run_path_str=run_path_str,
    )
    packet_path.write_text(content, encoding="utf-8")
    return packet_path
