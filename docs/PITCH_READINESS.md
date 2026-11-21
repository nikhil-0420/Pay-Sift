# PaySift Readiness & Reviewer Audit (Phase C5)

- **Date:** 2026-11-22
- **Audience:** Portfolio Reviewers & Technical Auditors
- **Owner:** Nikhil (Reviewer & Frontend Agent)
- **Target Deployments:**
  - Production Frontend: [https://pay-sift.vercel.app](https://pay-sift.vercel.app)
  - Production Read-Only Backend: [https://paysift-api.onrender.com](https://paysift-api.onrender.com)
- **Status:** READY FOR REVIEW

---

## 1. Executive Claim Audit Matrix

Every claim on the live site is derived strictly from recorded data files and handoff markers. No counts or statuses are hardcoded.

| # | Site Area | Exact Claim / Presentation | Backing Source File | Reviewer / Honesty Status |
|---|---|---|---|---|
| 1 | **Hero Finding** | "Real model finding": Gemini 3.5 Flash Lite (`strong_a/A/3`), Rule R8 violation, minimal trace length of 4 events. | `pilot/DECISION.md`, `runs/run_3_1795260584.json`, `handoff/N7_PILOT_DONE` | **VERIFIED.** Real failure under Condition A with full contract prompt. Not an illustrative condition B bug or mutant. |
| 2 | **Mutants Killed** | "13/13 mutants killed" with distinct badge "HAND-WRITTEN MUTANTS, not model output". | `runs/kill_matrix.json`, `mutants/` | **VERIFIED.** Hand-written bugs are explicitly distinguished from model output. |
| 3 | **Evidence Coverage** | "1 supported, 5 partial, 5 not found" empirical documentation grounding. | `runs/grounding.json`, `contract/grounding_schema.json` | **VERIFIED.** Computed dynamically; R8–R10 marked PARTIAL by human override; definition of PARTIAL explicitly explained. |
| 4 | **Spec Status & G1** | "Gate 1 passed, spec unchanged, reviewed by two independent predictors: Koushik and Rithvik". Persistent `DRAFT-FROZEN` banner. | `contract/SPEC.md`, `contract/SPEC_HASH`, `handoff/G1_RESULT` | **VERIFIED.** Displays G1 outcome and preserves draft status warning. |
| 5 | **Spec Run Counts** | "Violated in N runs" computed per distinct candidate run. | `runs/index.json` (excluding stubs) | **VERIFIED.** Dynamic distinct run count (`runs.filter(r => r.failures.some(f => f.rule === rule.id)).length`). |
| 6 | **Pilot Scope** | Exactly 8 Condition A candidates evaluated across 2 usable models (Gemini 3.5 Flash Lite, Qwen 2.5 27B). OpenRouter Ling rate-limited. | `pilot/DECISION.md`, `pilot/PILOT_REPORT.md` | **VERIFIED.** Candidate cards deduplicated by `${model}/${condition}/${candId}`; no model ranking is presented. |
| 7 | **Repair Outcome** | Rule R8 fixed on `strong_a/A/3` with 0 invariant regressions; grounded with 9 empirical sources. | `repair/cache/3__0.json`, `handoff/N8_REPAIR_DONE` | **VERIFIED.** Labeled `"CACHED REPAIR RESULT (run on operator machine)"`; before/after test suite numbers displayed directly. |
| 8 | **Execution Safety** | Hosted instance runs in read-only mode (`HOSTED_MODE=1`); mutation endpoints return HTTP 403. | `api/main.py`, `render.yaml` | **VERIFIED.** Hosted backend never runs arbitrary code or calls LLMs without Docker/local isolation. |
| 9 | **Concurrency Checks** | Concurrency trials for M8 and M9 show recorded trial failures with full tooltips. | `runs/kill_matrix.json` (`concurrency.scenario_A` / `scenario_B`) | **VERIFIED.** Heatmap cells reflect concurrency trial failures rather than false sequential passes. |

---

## 2. Reviewer Understanding Guide: Claims, Limits & Evidence

Can an independent reviewer understand the claim, limits, and evidence from the live site alone?

### A. The Core Claim
PaySift proves that **prompting LLMs with informal specifications or natural language is insufficient for financial correctness**.
When evaluated against formal executable payment invariants, modern LLMs produce subtle state-machine and idempotency flaws (e.g. `strong_a/A/3` consuming `event_id` on rejected events).

### B. The Method & Proof
1. **Formal Specification:** Contract Rules R0–R10 define strict state-machine transitions and financial invariants (signature integrity, deduplication idempotency, balance conservation, refund bounds, and complete interface totality).
2. **Oracle Gate (G2):** The reference implementation passes 100/100 trials, proving that the invariants are mathematically satisfiable and consistent.
3. **Adversarial Shrinking:** When a violation occurs, PaySift minimizes the event stream to the shortest reproducible failing sequence (4 events for R8).
4. **Grounded Repair:** Grounding the repair prompt with empirical documentation citations (via You.com API) guides the model to fix Rule R8 while preserving all other invariants.

### C. The Honest Limits
1. **Mutants are Hand-Written:** The 13 kill-matrix mutants are developer-crafted synthetic defects used to validate the invariant test suite.
2. **No Model Leaderboards:** PaySift does not rank models; sample sizes in pilot evaluations are diagnostic, not statistical benchmarks.
3. **Spec Status:** The contract remains `DRAFT-FROZEN` pending production ratification.
4. **LLM Evidence Judgments:** Documentation citations are retrieved and judged by LLMs, flagged as unreviewed unless manually verified by human review.
5. **Hosted Read-Only Isolation:** Live Docker container execution and model generation require a local environment with private API keys; the hosted site is an immutable forensic record.

---

## 3. Fallback & Resilience Checklist

| Verification Item | Hosted State | Cold / Offline Fallback |
|---|---|---|
| **Render Web Service** | Responds `200 OK` on `/health` (warm). | Returns static snapshot with top banner `"Backend waking or unavailable, showing static snapshot"` within 6s. |
| **Evidence Retrieval** | Queries live search proxy if configured. | Falls back to cached empirical citations from `runs/grounding.json`. |
| **Repair Replay** | Serves cached `3__0.json` artifact. | Renders pre-computed diff, before/after invariant table, and grounding sources. |
| **Local Backend Connect** | Allows developer to connect `http://localhost:8000`. | Validates via `LocalConnectControl` with 4s timeout and CORS guidance. |
