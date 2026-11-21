STATUS: DRAFT-FROZEN (Gate 1 pending)

# PaySift Contract Specification (v1.0)

This document defines the strict specification for webhook handlers tested by the PaySift harness.
A judge reading only this specification must be able to independently predict the oracle's verdict
on any sequence of events.

---

## 1. Handler Interface

The candidate handler must expose a top-level callable:

```python
def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> dict:
    """Processes a webhook event against SQLite database at db_path.

    Returns:
        {"status": "applied" | "duplicate" | "rejected", "reason": str}
    """
```

- `db_path`: Absolute path to a SQLite database initialized with the harness schema.
- `raw_body`: Raw bytes received over HTTP/transport before any JSON parsing.
- `signature`: Hex HMAC string received in webhook headers.
- `secret`: Webhook signing secret string (UTF-8).
- Return value: Dictionary with `status` (exact literal string) and `reason` (free-text string).

Financial truth is read directly from the SQLite database tables (`payments` and `ledger`),
never from the return value. The return value is evaluated exclusively by Invariant I5 (Interface).

---

## 2. Event Format

Events represent a simplified generic payment gateway webhook protocol.
All monetary amounts are non-negative integer paise (1 INR = 100 paise). Floating-point amounts are forbidden.

### Capture Event
```json
{
  "event_id": "evt_001",
  "type": "payment.captured",
  "payment_id": "pay_1",
  "amount_paise": 50000
}
```

### Refund Event
```json
{
  "event_id": "evt_002",
  "type": "refund.processed",
  "payment_id": "pay_1",
  "refund_id": "rfd_1",
  "amount_paise": 20000
}
```

---

## 3. Harness Database Schema

The harness initializes the database before any test stream begins:

```sql
CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY,
  captured_paise INTEGER NOT NULL,
  refunded_paise INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE ledger (
  entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('capture','refund')),
  amount_paise INTEGER NOT NULL,
  event_id TEXT
);
```

- Handlers may create auxiliary tables and indexes for deduplication or locking.
- Handlers must never alter, drop, or rename `payments` or `ledger`.
- The harness schema intentionally omits UNIQUE constraints on ledger `event_id` so that faulty handlers that fail to deduplicate are exposed.
- The oracle verifies balances across `payments` and rows in `ledger`. The oracle does not depend on the ledger `event_id` column value.

---

## 4. Numbered Rules

Every failure reported by the oracle cites exactly one rule:

| ID | Rule | Description |
|---|---|---|
| **R0** | **Totality & Interface** | For every input the handler returns a dict containing `"status"` in `{"applied", "duplicate", "rejected"}` and a string `"reason"`. It never raises an uncaught exception and never hangs (timeout 5.0 s per call). |
| **R1** | **Signature Verification** | The signature must equal the lowercase hex HMAC-SHA256 of the exact `raw_body` bytes, keyed with the UTF-8 `secret`. Any discrepancy (missing, empty, incorrect secret, corrupted/flipped byte, uppercase hex, non-ASCII characters, or signature computed over re-serialized JSON): return status `"rejected"`, commit no database state change, and raise no exception. |
| **R2** | **Payload Validation** | The `raw_body` must be valid UTF-8 JSON encoding a JSON object containing: `event_id` (non-empty string, length <= 64), `type` (`"payment.captured"` or `"refund.processed"`), `payment_id` (non-empty string, length <= 64), `amount_paise` (strict JSON integer from 1 to 10^12 inclusive; not boolean, not float even if 5.0, not string, not null, not <= 0), and for `"refund.processed"` additionally `refund_id` (non-empty string). Extra unrecognized JSON fields are permitted and ignored. Any violation of these requirements: return status `"rejected"` and commit no database state change. |
| **R3** | **Event Idempotency** | An `event_id` takes effect at most once. Redelivery of an already-applied event (with valid signature and payload): return status `"duplicate"` and commit no database state change. |
| **R4** | **Payment Capture** | For `payment.captured`: if no capture exists for `payment_id`, insert into `payments` (`captured_paise = amount`, `refunded_paise = 0`) and insert exactly one `'capture'` ledger entry (`amount_paise = amount`). If the payment already has a capture: return status `"rejected"` and commit no state change. |
| **R5** | **Refund Target Existence** | For `refund.processed`: requires an existing captured payment in `payments`. If `payment_id` does not exist: return status `"rejected"` and commit no state change. |
| **R6** | **Refund Balance Bound** | For `refund.processed`: total refunds cannot exceed capture amount (`refunded_paise + amount_paise <= captured_paise`). If amount exceeds remaining balance: return status `"rejected"` and commit no state change. If valid: update `payments` (`refunded_paise += amount_paise`) and insert exactly one `'refund'` ledger entry. |
| **R7** | **Financial Atomicity** | `payments` and `ledger` must always agree: `captured_paise` equals the sum of capture entries in `ledger`; `refunded_paise` equals the sum of refund entries in `ledger`. An event applies in full or not at all. |
| **R8** | **Rejection Non-Consumption** | A `"rejected"` event produces no state change and does NOT consume its `event_id`. If the same `event_id` is redelivered later with valid parameters or prerequisites satisfied, it must be processed and applied normally. |
| **R9** | **Durability Across Restarts** | All state lives in the SQLite database. The handler process may be terminated and restarted between any two calls without losing idempotency or accounting integrity. |
| **R10** | **Concurrency Safety** | Calls may run concurrently in separate processes against the same database file. Rules R3 (idempotency) and R6 (refund bounds) must strictly hold under concurrent execution. |

---

## 5. Order of Checks

Handlers must evaluate events in this deterministic order:

```
1. Signature check (R1)
      ↓ passes
2. Payload validation (R2)
      ↓ passes
3. Idempotency / Duplicate check (R3)
      ↓ new event_id
4. Business logic execution (R4 / R5 / R6)
```

- A bad signature on an already-applied `event_id` must return `"rejected"` (R1), not `"duplicate"`.
- A malformed payload on an already-applied `event_id` must return `"rejected"` (R2), not `"duplicate"`.

---

## 6. Clarifications (Closed Ambiguities)

- **C1. Idempotency Key:** The deduplication key is `event_id` only. `refund_id` is informational. Two distinct events carrying the same `refund_id` are two separate refunds, each subject to R6.
- **C2. Duplicates Apply Only to Applied Events:** The `"duplicate"` status is reserved exclusively for events that previously transitioned to `"applied"` (R3, R8). Events previously rejected must not return `"duplicate"`.
- **C3. Strict Check Precedence:** R1 (signature) precedes R2 (payload syntax) precedes R3 (idempotency) precedes business rules.
- **C4. Return Status Taxonomy:** Handlers must return strictly `"applied"`, `"duplicate"`, or `"rejected"`. Any other string violates R0. The `"reason"` field is informative diagnostic text and is not asserted by financial invariants.
- **C5. Payload Alteration on Duplicate ID:** If an event arrives with an `event_id` that was already applied, but with different payload fields: return status `"duplicate"` (by C1 and R3) without modifying database state.
- **C6. Schema Invariance:** Handlers may create auxiliary tables and indexes; existing harness definitions for `payments` and `ledger` must remain unchanged.
- **C7. Connection Lifecycle:** The handler must open and close its own connection per call to `db_path`, or manage connection transactions properly.
- **C8. Clock Independence:** Decisions must never depend on system wall-clock time.
- **C9. Unique Keys in JSON:** Harness event streams will never produce duplicate object keys within a single JSON payload.

---

## 7. Invariants and Headline Accounting

The test harness evaluates 5 invariants after each step:

| Invariant | Monitored Rules | Severity | Counts Toward Headline |
|---|---|---|---|
| **I1_signature** | R1 | financial | **Yes** |
| **I2_idempotency** | R3, R8, R9, R10 (Scenario A) | financial | **Yes** |
| **I3_conservation** | R4, R7 | financial | **Yes** |
| **I4_bounds** | R2, R5, R6, R10 (Scenario B) | financial | **Yes** |
| **I5_interface** | R0, status mismatch (C3, C4) | interface | **No** (reported separately) |

*Attribution Note:* Concurrency failures cite rule R10. Scenario A (duplicate capture race) attributes to `I2_idempotency`. Scenario B (concurrent refunds exceeding balance) attributes to `I4_bounds`.

---

## 8. Worked Examples

The following canonical examples define expected behavior across representative event streams:

| # | Stream Sequence | Expected Outcome & Final Database State | Rule Cited |
|---|---|---|---|
| 1 | capture evt_1 ₹500 | `pay_1`: captured 500, refunded 0; 1 capture entry | R4 |
| 2 | capture evt_1 ₹500, capture evt_1 ₹500 | Second event returns `duplicate`; state identical to #1 | R3 |
| 3 | capture evt_1 ₹500, capture evt_2 ₹500 (same payment) | Second capture returns `rejected`; state identical to #1 | R4 |
| 4 | capture ₹500, refund ₹300, refund ₹300 (distinct event IDs) | Second refund `rejected`; `pay_1`: captured 500, refunded 300; 1 capture, 1 refund | R6 |
| 5 | capture ₹500, refund ₹300, refund ₹200 | Both refunds applied; `pay_1`: captured 500, refunded 500; 1 capture, 2 refunds | R6 |
| 6 | refund ₹100 on unknown payment | Event `rejected`; database remains empty | R5 |
| 7 | capture with bad signature | Event `rejected`; database remains empty | R1 |
| 8 | capture with uppercase hex signature | Event `rejected`; database remains empty | R1 |
| 9 | capture signed over re-serialized JSON (body has whitespace) | Event `rejected`; signature was not computed over raw bytes | R1 |
| 10 | capture with bad amounts (`-500`, `0`, `5.0`, `"500"`, `true`, `null`, `10**13`) | Each event returns `rejected`; database remains empty | R2 |
| 11 | refund missing `refund_id` field | Event `rejected`; database remains empty | R2 |
| 12 | refund before capture (`rejected`), capture applied, same refund redelivered | Refund is `applied` upon redelivery; final refunded 300 | R8 |
| 13 | bad-signature event evt_1 (`rejected`), then valid evt_1 | Second event is `applied`; initial bad signature consumed nothing | R1, R8 |
| 14 | capture evt_1 applied, then redelivered evt_1 with bad signature | Event returns `rejected` (signature check precedes duplicate check) | C3, R1 |
| 15 | two refund events with identical `refund_id`, both fit | Both refunds applied; `refund_id` is not idempotency key | C1, R6 |

---

## 9. Required Fixture Classes

Test suites (`contract/cases.jsonl`) must include coverage for:
1. Exact duplicates on capture and refund events
2. Second capture attempts on same payment ID
3. Multiple distinct payments in single stream
4. Exact-bound refunds and over-bound refunds
5. Refund attempted before capture
6. Refund on nonexistent/unknown payment ID
7. Invalid amount representations: negative, zero, float (e.g. 5.0), string ("500"), boolean (`true`), `null`, huge integers (> 10^12)
8. Missing mandatory fields (`event_id`, `type`, `payment_id`, `amount_paise`, `refund_id`)
9. Extra unrecognized payload fields (valid and ignored)
10. Malformed payload bodies: non-object JSON (array, number, string), invalid UTF-8 bytes, invalid JSON syntax
11. Signature mutations: missing, empty, incorrect secret, single bit/byte flip, uppercase hex, non-ASCII characters, signed over re-serialized JSON
12. Non-canonical valid bodies: non-standard whitespace separators, inverted key order, Unicode escape sequences, trailing newlines, pretty-printed JSON
13. Rejection followed by valid redelivery (R8)
14. Applied event followed by corrupted redelivery (C3)
15. Identical `refund_id` on distinct `event_id`s (C1)
16. Identical `event_id` with modified payload parameters (C5)

---

## 10. Prompt Definitions

- **Condition A (`prompt_full.txt`):** The fair benchmark prompt. Contains full specification text, interface signature, SQLite schema, rules R0–R10, and explicit instructions: single file, no markdown explanation, allowed imports: `sqlite3, hmac, hashlib, json, time, typing, contextlib`.
- **Condition B (`prompt_casual.txt`):** Illustrative prompt representing typical developer instructions. Requests webhook handler function and signature verification, includes SQL schema and example event JSONs, but omits the explicit numbered rules. Results are classified as illustrative only.
