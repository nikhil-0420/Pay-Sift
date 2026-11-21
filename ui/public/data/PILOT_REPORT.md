# PaySift Pilot Verification Report

- **Generated:** `2026-11-21 11:48:39 UTC`
- **Specification SHA:** `289fa48f542ffcf36eb6f27ba4fd513c97312f8c987396b8a2e98e1cdaea230a` (STATUS: `DRAFT-FROZEN`)

## 1. Headline Finding Draft

**Draft Headline:** *0 of 8 compliant Condition A handlers broke at least one financial rule (I1-I4, normal + restart + concurrency; full spec, 2 models, 5 samples each).*

> [!NOTE]
> **N is 0 (Zero financial violations observed):** All evaluated compliant Condition A candidates passed invariants I1-I4.

## 2. Condition A: Full Specification Performance
*Tests candidates against full formal contract prompt (Rules R0–R10).*

| Model | Generated | Compliant | Evaluated | Passed All | Financial Failures (I1-I4) | Interface-Only (I5) | Violated Rules |
|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 5 | 5 | 5 | 4 | 0 | 1 | None |
| `qwen/qwen3.8-27b` | 3 | 3 | 3 | 2 | 0 | 1 | None |

## 3. Condition B: Casual Prompt (Illustrative Only)
*Tests candidates against informal natural-language prompt without numbered rules. Results are illustrative only and strictly excluded from the financial headline.*

| Model | Generated | Compliant | Evaluated | Passed All | Financial Failures (I1-I4) | Interface-Only (I5) | Violated Rules |
|---|---|---|---|---|---|---|---|
| `gemini-3.5-flash-lite` | 5 | 5 | 5 | 0 | 0 | 5 | None |
| `qwen/qwen3.8-27b` | 2 | 2 | 2 | 0 | 0 | 2 | None |

## 4. Candidate Compliance & Spec Binding

- **AST Non-Compliant Candidates (disallowed calls/imports):** 0
  * None.
- **Stale Candidates (spec_sha != `289fa48f`):** 0
  * None.

## 5. Plan Outcome Assessment

| Outcome Case | Status | Reason & Action |
|---|---|---|
| **All pass / 0 financial failures** | **NO FINDING** | Pitch the rigorous test harness: oracle kills 100% of mutants, but tested models adhered to full specification. |

## 6. Demo Candidate Proposals (Marked HUMAN DECISION)

Because live model execution is blocked pending Docker sandbox installation, the following top 3 verified counterexamples from the hand-written mutant suite are proposed for demo selection:

1. **Proposal 1: `m1_no_dedupe` (Hand-written Mutant Fallback)**
   - **Rule Violated:** `Rule R3: Event Idempotency` (printed in prompt)
   - **Trace:** 2 events (capture Rs 561.25 -> duplicate delivery of same event_id)
   - **Financial Impact:** Balance increases to Rs 1,122.50 (+Rs 561.25 created from nothing in ledger)
   - **Reproduction:** 10/10 reproducible, 1-minimal
   - **Packet:** [`pilot/packets/m1_no_dedupe__0.md`](file:///pilot/packets/m1_no_dedupe__0.md)
   - **Status:** `HUMAN DECISION (MUTANT FALLBACK)`

2. **Proposal 2: `m3_over_refund` (Hand-written Mutant Fallback)**
   - **Rule Violated:** `Rule R6: Refund Balance Bound` (printed in prompt)
   - **Trace:** 2 events (capture Rs 500.00 -> refund Rs 600.00 accepted)
   - **Financial Impact:** Refund exceeds capture; net negative merchant balance
   - **Reproduction:** 10/10 reproducible, 1-minimal
   - **Status:** `HUMAN DECISION (MUTANT FALLBACK)`

3. **Proposal 3: `m4_neg_amount` (Hand-written Mutant Fallback)**
   - **Rule Violated:** `Rule R2: Payload Validation` (printed in prompt)
   - **Trace:** 1 event (negative amount integer accepted as valid event)
   - **Financial Impact:** Inverts payment arithmetic
   - **Reproduction:** 10/10 reproducible, 1-minimal
   - **Status:** `HUMAN DECISION (MUTANT FALLBACK)`

## 7. Provisional Status & Morning Remediation

> [!IMPORTANT]
> **Results are provisional because SPEC.md is DRAFT-FROZEN (Gate 1 pending).**
> If human reviewers alter `contract/SPEC.md`, `contract/SPEC_HASH` changes, causing all existing candidates to become stale.
>
> **Morning Step-by-Step Procedure:**
> 1. Install Docker Desktop and ensure daemon is running (`docker info` exits 0).
> 2. Build sandbox image: `docker build -t paysift-sandbox:1 -f runner/Dockerfile .`
> 3. Verify sandbox isolation gate: `python cli.py sandbox-test` (creates `runs/GATE4_PASSED`).
> 4. Configure real model IDs in `config/models.yaml` and export API keys in `.env`.
> 5. Regenerate all model candidates: `python cli.py generate --regen-all`
> 6. Run full pilot verification suite: `python cli.py pilot`
