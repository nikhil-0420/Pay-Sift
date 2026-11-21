# PaySift Kill Matrix Report

- **Spec SHA:** `289fa48f542ffcf36eb6f27ba4fd513c97312f8c987396b8a2e98e1cdaea230a`
- **Oracle SHA:** `3c9fcb4d50d389846eacc942b2ae78dc823a795584ef0af002d1ba01a3675e16`
- **Generated At:** `2026-11-20T22:16:31.131849+00:00`
- **Seeds Range:** `0..99`

| ID | Label | Source | Expected Rule | Expected Invariant | Status | Rules Hit | Notes |
|---|---|---|---|---|---|---|---|
| `ref` | handler_ref.py | reference | `none` | `none` | **PASS (Clean)** | `-` | Reference implementation clean across all invariants and concurrency trials |
| `m1` | no dedupe | mutant | `R3` | `I2_idempotency` | **KILLED** | `R3, R4` | self-attested by the agent; omits deduplication check and applies duplicate captures |
| `m2` | ledger written, payments not updated | mutant | `R7` | `I3_conservation` | **KILLED** | `R7` | self-attested by the agent; writes ledger entries but leaves payments balance out of sync |
| `m3` | no refund bound | mutant | `R6` | `I4_bounds` | **KILLED** | `R6` | self-attested by the agent; omits refunded + amount <= captured check, permitting over-refunds |
| `m4` | accepts negative amount | mutant | `R2` | `I4_bounds` | **KILLED** | `R2` | self-attested by the agent; relaxes lower bound check on amount_paise |
| `m5` | rejected events consume event_id | mutant | `R8` | `I2_idempotency` | **KILLED** | `R8` | self-attested by the agent; records rejected event_id into dedupe table so redelivery is marked duplicate |
| `m6` | verifies signature over json.dumps(parsed) | mutant | `R1` | `I1_signature` | **KILLED** | `R1` | self-attested by the agent; checks HMAC against default-spaced serialized JSON rather than raw bytes |
| `m7` | state stored in memory, lost on restart | mutant | `R9` | `I2_idempotency` | **KILLED** | `R0, R9` | self-attested by the agent; module-level set() dedupe lost across fresh processes |
| `m8` | check-then-insert without transaction | mutant | `R10` | `I2_idempotency` | **KILLED** | `R10` | self-attested by the agent; autocommit statements allow duplicate capture race (window widened) |
| `m9` | refund bound checked in separate statement | mutant | `R10` | `I4_bounds` | **KILLED** | `R10` | self-attested by the agent; autocommit statements allow over-refund race (window widened) |
| `x1` | accepts bool as amount | extra-mutant | `R2` | `I4_bounds` | **KILLED** | `R2` | self-attested by the agent; accepts boolean true as integer 1 |
| `x2` | accepts float amount | extra-mutant | `R2` | `I4_bounds` | **KILLED** | `R2` | self-attested by the agent; accepts float values like 5.0 |
| `x3` | crashes on non-ASCII signature | extra-mutant | `R0` | `I5_interface` | **KILLED** | `R0` | self-attested by the agent; unhandled UnicodeEncodeError on non-ASCII signature |
| `x4` | verifies signature over canonical serialized JSON | extra-mutant | `R1` | `I1_signature` | **KILLED** | `R1` | self-attested by the agent; re-serializes payload canonically; caught only by non-canonical bodies |

## Invariant Sensitivity Verification

- **Reference Fully Green:** `PASS`
- **x4 Caught on Family 8 Seeds:** `PASS`
- **x4 Clean on Non-Family 8 Seeds:** `PASS`
