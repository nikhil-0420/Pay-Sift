# PaySift Canonical Naming Reference

This document defines the canonical taxonomy of identifiers, keys, modes, and rule IDs across PaySift as codified in `oracle/checks.py`, `contract/run_schema.json`, and the test runner.

---

## 1. Invariant Keys

The test harness evaluates 5 core financial invariants. Invariant keys must always match the keys emitted by `oracle/checks.py` and required by `contract/run_schema.json`:

| Canonical Key | Name | Primary Rules Tested | Description |
|---|---|---|---|
| `I1_signature` | Signature Verification | R1 | HMAC-SHA256 signature verification over exact raw bytes using secret key. |
| `I2_idempotency` | Event Idempotency | R3, R8, R9, R10 | Events apply at most once; deduplication survives restarts; rejections are non-consuming. |
| `I3_conservation` | Balance Conservation | R7 | Ledger entries and payment summary balances are updated atomically in the same database transaction. |
| `I4_bounds` | Bounds & Amount Validation | R2, R4, R5, R6, R10 | Amount positivity, integer paise types, capture uniqueness, and refund $\le$ captured bounds. |
| `I5_interface` | Totality & Response Shape | R0 | Handler never raises uncaught exceptions and always returns a structured status response. |

*Note: Historical documentation references to `I1_integrity` or `I5_totality` are deprecated in favor of `I1_signature` and `I5_interface` respectively.*

---

## 2. Execution Modes

The execution mode passed to `runner/run_candidate.py`, the CLI, and recorded in run artifacts:

| Mode | Description |
|---|---|
| `normal` | Sequential execution of event streams against a long-lived handler process. |
| `restart` | Process-isolated execution where a fresh child process is spawned before every event delivery to verify SQLite persistence (Rule R9). |

---

## 3. Candidate Source Values

Allowed values for `candidate.source` (as specified in `contract/run_schema.json`):

| Source Value | Meaning |
|---|---|
| `live` | Live LLM-generated code evaluated inside the container sandbox. |
| `pre-run` | Pre-computed model candidate output from pilot runs. |
| `reference` | The correct reference implementation (`ref/handler_ref.py`). |
| `mutant` | Core hand-written defect handler (`mutants/m1` through `m9`). |
| `extra-mutant` | Auxiliary hand-written defect handler (`mutants/x1` through `x4`). |
| `stub` | Reference handler used as offline test stand-in for pipeline testing. |

---

## 4. Candidate Condition Values

Allowed values for `candidate.condition` (prompting treatment):

| Condition | Description |
|---|---|
| `A` | Formal specification prompt containing complete rules R1–R10. |
| `B` | Casual specification prompt containing conversational payment webhook requirements. |
| `-` | Not applicable (used for reference handlers, mutants, and stubs). |

---

## 5. Specification Rule IDs

The 11 formal rules defined in `contract/SPEC.md` and enforced by `oracle/checks.py`:

| Rule ID | Name | Summary |
|---|---|---|
| `R0` | Interface Totality | Handler must return `{"status": ...}` and never crash or raise unhandled exceptions. |
| `R1` | Signature Verification | HMAC-SHA256 computed over unparsed raw request bytes; valid signatures never rejected. |
| `R2` | Payload Validation | Request body must be valid UTF-8 JSON object; `amount_paise` must be integer $\ge 1$. |
| `R3` | Event Idempotency | An `event_id` takes effect at most once. Duplicate events return duplicate status without re-application. |
| `R4` | Payment Capture Creation | First capture event creates the payment record with `captured_paise = amount_paise`. |
| `R5` | Payment Capture Uniqueness | A `payment_id` can be captured at most once; secondary captures for an existing payment are rejected. |
| `R6` | Refund Balance Bound | Total refunds for a payment cannot exceed total captured amount. Excess refunds are rejected. |
| `R7` | Atomic Conservation | Ledger entry insertion and payment record updates must occur within a single atomic database transaction. |
| `R8` | Rejection Non-Consumption | A rejected event does not register an idempotency record; subsequent valid deliveries with the same ID must succeed. |
| `R9` | Restart Durability | Idempotency and deduplication state must be persisted to the database and survive process restarts. |
| `R10` | Concurrency Safety | Handlers must be race-free under concurrent delivery of duplicate captures or competing refunds. |
