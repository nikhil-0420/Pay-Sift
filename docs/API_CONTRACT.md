# PaySift REST API Contract & Specification

This document defines the formal REST API contract between the PaySift Python backend (`api/main.py`) and the frontend dashboard.

## Base Configuration & CORS
- **Default Port:** `8000` (e.g., `http://localhost:8000`)
- **Allowed Frontend Origins:**
  - `http://localhost:5173` (Vite dev server)
  - `http://127.0.0.1:5173`
  - `http://localhost:3000`
  - `http://127.0.0.1:3000`
- **Supported Methods:** `GET`, `POST`, `OPTIONS`
- **Preflight Support:** HTTP `OPTIONS` preflight returns `200 OK` with `Access-Control-Allow-Origin`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`.

---

## Standard Error Response Shape
All error responses from FastAPI conform to the standard error structure:
```json
{
  "detail": "Descriptive error message"
}
```
Validation errors (HTTP 422) return structured detail list:
```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## Endpoints

### 1. Health & Integrity Check
- **Path:** `GET /health`
- **Description:** Verifies service health, SQLite database accessibility, and returns authoritative cryptographic hashes.
- **Request Body:** None
- **Response (HTTP 200):**
```json
{
  "status": "ok",
  "spec_sha": "289fa48f542ffcf36eb6f27ba4fd513c97312f8c987396b8a2e98e1cdaea230a",
  "oracle_sha": "3c9fcb4d50d38984a9235d2182065842886f4553cb77a166164d142512f71887"
}
```

---

### 2. List Runs
- **Path:** `GET /runs`
- **Description:** Returns a summarized list of all evaluation runs located in `runs/*.json`.
- **Request Body:** None
- **Response (HTTP 200):**
```json
[
  {
    "id": "run_handler_ref_1795254205",
    "run_id": "run_handler_ref_1795254205",
    "created_at": "2026-11-21T09:43:33.708892+00:00",
    "candidate": {
      "id": "handler_ref",
      "source": "reference",
      "model": "reference",
      "condition": "-",
      "label": "reference implementation"
    },
    "candidate_id": "handler_ref",
    "candidate_source": "reference",
    "candidate_model": "reference",
    "candidate_condition": "-",
    "failure_count": 0,
    "failures_count": 0,
    "financial_failure_count": 0,
    "financial_failures_count": 0,
    "interface_failure_count": 0,
    "interface_failures_count": 0,
    "repair_of": null,
    "spec_sha": "289fa48f542ffcf3...",
    "oracle_sha": "3c9fcb4d50d38984...",
    "path": "runs/run_handler_ref_1795254205.json"
  }
]
```

---

### 3. Retrieve Full Run Details
- **Path:** `GET /runs/{run_id}`
- **Description:** Fetches complete Run JSON document including per-invariant statistics and detailed failure traces.
- **Path Parameters:**
  - `run_id` (string, regex `^[a-zA-Z0-9_\-]+$`): Identifier of the run.
- **Errors:**
  - `400 Bad Request`: Invalid `run_id` format (path traversal attempt).
  - `404 Not Found`: No run artifact matches `runs/{run_id}.json`.
- **Response (HTTP 200):**
```json
{
  "run_id": "run_m1_no_dedupe_1795254220",
  "candidate": {
    "id": "m1_no_dedupe",
    "source": "mutant",
    "model": "handwritten",
    "condition": "-",
    "label": "hand-written mutant"
  },
  "spec_sha": "289fa48f542ffcf3...",
  "oracle_sha": "3c9fcb4d50d38984...",
  "created_at": "2026-11-21T09:43:47.387119+00:00",
  "results": {
    "I1_signature": {"normal": {"passed": 18, "failed": 2}},
    "I2_idempotency": {"normal": {"passed": 14, "failed": 6}},
    "I3_conservation": {"normal": {"passed": 14, "failed": 6}},
    "I4_bounds": {"normal": {"passed": 16, "failed": 4}},
    "I5_interface": {"normal": {"passed": 20, "failed": 0}}
  },
  "failures": [
    {
      "seed": 0,
      "step_index": 4,
      "invariant": "I2_idempotency",
      "violated_rule": "Rule R3: Capture Idempotency",
      "explanation": "Event capture-001 accepted twice...",
      "shrunk_trace": [ ... ]
    }
  ]
}
```

---

### 4. Kill Matrix
- **Path:** `GET /kill-matrix`
- **Description:** Retrieves the comprehensive mutant kill matrix evaluating reference and mutants m1–m9, x1–x4 across all rules R0–R10.
- **Request Body:** None
- **Response (HTTP 200):** Returns contents of `runs/kill_matrix.json`.

---

### 5. Break-It Scenario Evaluation
- **Path:** `POST /break`
- **Description:** Evaluates a candidate against one of the 6 canonical scenarios (`duplicate_capture`, `forged_signature`, `over_refund`, `bool_amount`, `restart_between_calls`, `rejected_redelivery`).
- **Security Check:** Untrusted model-generated candidates are strictly rejected (`403 Forbidden`) unless `runs/GATE4_PASSED` exists.
- **Request Body:**
```json
{
  "candidate_id": "m1_no_dedupe",
  "scenario": "duplicate_capture"
}
```
- **Response (HTTP 200 - Violation Found):**
```json
{
  "candidate_id": "m1_no_dedupe",
  "scenario": "duplicate_capture",
  "verdict": "fail",
  "oracle_check": {
    "has_financial_violation": true,
    "violation_invariant": "I2_idempotency"
  },
  "ledger_diff": {
    "balance_diff_paise": 50000,
    "diff_summary": "Balance diff: Rs 500.00 created from nothing",
    "actual": { "captured_paise": 100000, "refunded_paise": 0 },
    "expected": { "captured_paise": 50000, "refunded_paise": 0 }
  }
}
```
- **Response (HTTP 200 - Pass):**
```json
{
  "candidate_id": "reference",
  "scenario": "duplicate_capture",
  "verdict": "pass",
  "oracle_check": {
    "has_financial_violation": false,
    "violation_invariant": null
  },
  "ledger_diff": {
    "balance_diff_paise": 0,
    "diff_summary": "Balances match expected oracle state",
    "actual": { "captured_paise": 50000, "refunded_paise": 0 },
    "expected": { "captured_paise": 50000, "refunded_paise": 0 }
  }
}
```

---

### 6. Interactive Repair Loop
- **Path:** `POST /repair`
- **Description:** Initiates or retrieves pre-computed repair result for a failed candidate.
- **Request Body:**
```json
{
  "candidate_id": "m1_no_dedupe",
  "failure_id": 0
}
```
- **Responses:**
  - `200 OK`: Returns repair diff, before/after invariant pass rates, and repaired candidate code.
  - `403 Forbidden`: Candidate execution blocked when Gate 4 sandbox verification is absent.
  - `503 Service Unavailable`: Live model repair generation blocked due to missing API keys / provider configuration.

---

### 7. Grounding & Evidence Endpoints
- **Path:** `GET /evidence/rules`
- **Description:** Returns grounding sources, queries, and You.com citations for all contract rules.
- **Path:** `GET /evidence/rules/{rule_id}`
- **Description:** Returns grounding cache and citations for specific rule (e.g. `R1`).
