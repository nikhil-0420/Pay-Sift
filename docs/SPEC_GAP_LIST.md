# Specification Gap List (Stage K4)

- **Generated:** 2026-11-21
- **Status:** Human Review Overrides Applied
- **Specification SHA:** `289fa48f542ffcf36eb6f27ba4fd513c97312f8c987396b8a2e98e1cdaea230a`

This document lists rules where public provider documentation is silent, partial, or where PaySift internal conventions govern behavior. These questions serve as an optional second pass for specification review and do not block Gate 1 or candidate generation.

---

## Gap Rules & Questions for Review

| Rule | Title | Post-Review Label | Type / Classification | Question for Review |
|---|---|---|---|---|
| **R0** | Totality & Interface | `NOT_FOUND` | PaySift convention | Is the exact return dictionary structure (`{"status": ..., "reason": ...}`) and 5.0 s execution timeout a PaySift convention that should be standardized, or can standard webhook response conventions be adopted? |
| **R2** | Payload Validation | `NOT_FOUND` | PaySift convention | Are the strict integer amount bounds (1 to 10^12 paise, i.e. up to Rs 10,000,000,000 inclusive) and field presence constraints PaySift conventions, or should gateway-specific schema validation limits be documented? |
| **R3** | Event Idempotency | `PARTIAL` | Empirical / Partial | While duplicate event delivery is widely recognized across payment gateways, should the spec clarify whether duplicate events must return status `"duplicate"` or HTTP 200 without re-processing? |
| **R4** | Payment Capture | `NOT_FOUND` | PaySift convention | Is the single-capture restriction per `payment_id` with rejection of subsequent captures a PaySift convention, or does it vary by gateway multi-capture policies? |
| **R5** | Refund Target Existence | `NOT_FOUND` | PaySift convention | Is rejecting refunds when the original payment capture is absent a PaySift convention, or should out-of-order event delivery be buffered rather than rejected? |
| **R6** | Refund Balance Bound | `PARTIAL` | Empirical / Partial | Partial and multiple refunds are supported across gateways, but should the spec clarify how the running refund balance bound is enforced under gateway fee reversals? |
| **R7** | Financial Atomicity | `NOT_FOUND` | PaySift convention | Is the dual-ledger accounting reconciliation requirement a PaySift internal invariant convention, or can single-table transactional consistency suffice? |
| **R8** | Rejection Non-Consumption | `PARTIAL` | Human Override | Gateway documentation primarily covers API idempotency key non-consumption on rejection; should the spec confirm whether webhook `event_id` non-consumption follows the same idempotency semantics? |
| **R9** | Durability Across Restarts | `PARTIAL` | Human Override | While SQLite durability across restarts is well-documented, should the spec explicitly define expected crash-recovery state transitions for in-flight uncommitted webhook transactions? |
| **R10** | Concurrency Safety | `PARTIAL` | Human Override | Given that concurrent webhook delivery protection is detailed in engineering literature rather than official gateway docs, should the concurrency safety requirements cite recommended locking architectures (e.g. SQLite `BEGIN IMMEDIATE`)? |

---

## Summary of Human Overrides

- **R8:** Overridden from `SUPPORTED` to `PARTIAL` — *Quote is about API idempotency keys, not webhook event ids; supports the concept only.*
- **R9:** Overridden from `SUPPORTED` to `PARTIAL` — *Source only says SQLite survives crashes; it does not cover idempotency across restarts.*
- **R10:** Overridden from `SUPPORTED` to `PARTIAL` — *Only source is a blog post, not official provider docs.*
