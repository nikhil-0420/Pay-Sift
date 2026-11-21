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

### 7. Grounding & Evidence Endpoints (You.com Layer)

PaySift includes a live documentation grounding layer (`api/evidence.py`) that queries You.com for web documentation and official API references supporting or challenging contract rules.

#### 7.1 Complete Grounding Artifact
- **Path:** `GET /evidence`
- **Description:** Returns the complete grounding artifact (`runs/grounding.json`), including rule text, citations, search queries, and LLM judge verdicts for all rules (R0 through R10).
- **Request Body:** None
- **Response (HTTP 200):**
```json
{
  "generated_at": "2026-11-21T08:40:21.423168+00:00",
  "spec_sha": "289fa48f542ffcf36eb6f27ba4fd513c97312f8c987396b8a2e98e1cdaea230a",
  "provider": "you.com",
  "rules": {
    "R1": {
      "title": "Signature Verification",
      "label": "SUPPORTED",
      "convention": false,
      "human_reviewed": false,
      "sources": [
        {
          "id": "R1_s1",
          "url": "https://docs.stripe.com/webhooks/signature",
          "title": "Stripe Webhook Signatures",
          "snippet": "Always verify HMAC-SHA256 signatures over the exact raw body payload bytes.",
          "rank": 1,
          "query": "site:docs.stripe.com/webhooks verify signature raw request body hmac sha256",
          "retrieved_at": "2026-11-21T07:38:51.048378+00:00",
          "provider": "you.com"
        }
      ],
      "sources_used": ["R1_s1"],
      "quote": "Always verify HMAC-SHA256 signatures over the exact raw body payload bytes. Do not verify signature over re-serialized JSON.",
      "reason": "The retrieved documentation explicitly supports the requirement to compute the HMAC-SHA256 signature using the exact raw body bytes.",
      "judge": {
        "model": "gemini-3.5-flash-lite",
        "temperature": 0.0,
        "token_usage": {
          "prompt_tokens": 393,
          "completion_tokens": 109,
          "total_tokens": 502
        },
        "timestamp": "2026-11-21T08:40:21.423168+00:00"
      }
    }
  }
}
```
- **Errors:**
  - `404 Not Found`: `runs/grounding.json` missing (run `python cli.py ground --fetch`).
  - `500 Internal Server Error`: Disk read / JSON deserialization error.

#### 7.2 Single Rule Evidence
- **Path:** `GET /evidence/{rule_id}`
- **Description:** Returns evidence citations, quotes, judge verdict, and review status for a single rule.
- **Path Parameters:**
  - `rule_id` (string, required): Specification rule ID matching regex `^R(10|[0-9])$`.
- **Request Body:** None
- **Response (HTTP 200):**
```json
{
  "title": "Signature Verification",
  "label": "SUPPORTED",
  "convention": false,
  "human_reviewed": false,
  "sources": [
    {
      "id": "R1_s1",
      "url": "https://docs.stripe.com/webhooks/signature",
      "title": "Stripe Webhook Signatures",
      "snippet": "Always verify HMAC-SHA256 signatures over the exact raw body payload bytes.",
      "rank": 1,
      "query": "site:docs.stripe.com/webhooks verify signature raw request body hmac sha256",
      "retrieved_at": "2026-11-21T07:38:51.048378+00:00",
      "provider": "you.com"
    }
  ],
  "sources_used": ["R1_s1"],
  "quote": "Always verify HMAC-SHA256 signatures over the exact raw body payload bytes. Do not verify signature over re-serialized JSON.",
  "reason": "The retrieved documentation explicitly supports the requirement to compute the HMAC-SHA256 signature using the exact raw body bytes.",
  "judge": {
    "model": "gemini-3.5-flash-lite",
    "temperature": 0.0,
    "token_usage": {
      "prompt_tokens": 393,
      "completion_tokens": 109,
      "total_tokens": 502
    },
    "timestamp": "2026-11-21T08:40:21.423168+00:00"
  }
}
```
- **Errors:**
  - `400 Bad Request`: `rule_id` does not match regex `^R(10|[0-9])$`.
  - `404 Not Found`: Rule ID not found in `runs/grounding.json` or cache.
  - `500 Internal Server Error`: Disk read error.

#### 7.3 Live Search & Re-Grounding
- **Path:** `POST /evidence/search`
- **Description:** Triggers an on-demand You.com search for a rule with optional extra search terms, updates `grounding/cache/{rule_id}.json`, and rebuilds `runs/grounding.json`.
- **Rate Limit:** Per-process sliding window limit of 10 calls per 60 seconds (`429 Too Many Requests`).
- **Request Body:**
```json
{
  "rule_id": "R1",
  "extra_terms": "stripe test"
}
```
- **Fields:**
  - `rule_id` (string, required): Specification rule ID matching regex `^R(10|[0-9])$`.
  - `extra_terms` (string, optional): Extra terms to augment queries (max 80 chars, sanitized).
- **Response (HTTP 200):**
```json
{
  "status": "ok",
  "rule_id": "R1",
  "sources_retrieved": 2,
  "data": {
    "rule_id": "R1",
    "rule_text": "Webhook endpoint MUST verify signature...",
    "rule_text_sha": "d3b07384d113edec49eaa6238ad5ff00",
    "queries": ["site:docs.stripe.com/webhooks verify signature raw request body hmac sha256 stripe test"],
    "sources": [
      {
        "id": "R1_s1",
        "url": "https://docs.stripe.com/webhooks/signature",
        "title": "Stripe Webhook Signatures",
        "snippet": "Always verify HMAC-SHA256 signatures over the exact raw body payload bytes.",
        "rank": 1,
        "query": "site:docs.stripe.com/webhooks verify signature raw request body hmac sha256 stripe test",
        "retrieved_at": "2026-11-21T07:38:51.048378+00:00",
        "provider": "you.com"
      }
    ]
  }
}
```
- **Errors:**
  - `400 Bad Request`: Malformed `rule_id` or `extra_terms` exceeds 80 characters.
  - `404 Not Found`: Rule ID not defined in `grounding/queries.yaml`.
  - `429 Too Many Requests`: Sliding-window rate limit (10 calls/min) or upstream You.com call cap exceeded.
  - `502 Bad Gateway`: Upstream search request failed.
  - `503 Service Unavailable`: `YDC_API_KEY` is missing / not configured on the server.
