# PaySift Pilot Review Sheet

## 1. Candidate Population Note
A total of 15 candidates were evaluated. Only 2 models produced usable candidates due to upstream rate limits:
- `gemini-3.5-flash-lite` (`strong_a`): 10 candidates generated (5 Condition A, 5 Condition B)
- `qwen/qwen3.8-27b` (`strong_b`): 5 candidates generated (3 Condition A, 2 Condition B)
- `inclusionai/ling-3.2-flash:free` (`strong_c`): 0 candidates generated (all calls rate-limited upstream on OpenRouter)

## 2. Failing Candidates (Condition A - Full Specification)

| Candidate ID | Model | Condition | Violated Rule | Invariant | Minimal Trace Length | Diagnostic Packet |
|---|---|---|---|---|---|---|
| `strong_a/A/3` | `gemini-3.5-flash-lite` | `A` | **Rule R8: Rejection Non-Consumption** | `I2_idempotency` | 4 events | [`pilot/packets/3__0.md`](file:///pilot/packets/3__0.md) |

### Failure Summary: `strong_a/A/3`
- **Candidate ID:** `strong_a/A/3`
- **Model:** `gemini-3.5-flash-lite`
- **Condition:** `A` (Full Specification Contract)
- **Violated Rule:** `Rule R8: Rejection Non-Consumption`
- **Violated Invariant:** `I2_idempotency`
- **Minimal Counterexample Trace (4 steps):**
  1. `refund.processed s6_rfd_r8 (Rs 250)` [tag: premature_refund_r5]
  2. `payment.captured s6_cap_r8 (Rs 600)` [tag: capture_applied_r4]
  3. `refund.processed s6_rfd_r8 (Rs 250)` [tag: redelivered_refund_applied_r8]
  4. `payment.captured s6_badsig_then_good (Rs 400)` [tag: bad_signature_r1]
- **Diagnostic Packets:** [`pilot/packets/3__0.md`](file:///pilot/packets/3__0.md) through [`pilot/packets/3__9.md`](file:///pilot/packets/3__9.md)
- **Run JSON:** [`runs/run_3_1795260584.json`](file:///runs/run_3_1795260584.json)
