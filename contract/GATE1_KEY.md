# Gate 1 Master Answer Key

> [!CAUTION]
> Predictors must not read this until they have written their answers independently on the Gate 1 Answer Sheet.

---

## Authoritative Oracle Verdicts for Gate 1 Cases

| # | Case ID | Step 1 | Step 2 | Step 3 | Final Payments State | Final Ledger State | Primary Rule Justification |
|---|---|---|---|---|---|---|---|
| **1** | case_002 | `applied` (R4) | `duplicate` (R3) | N/A | `pay_1`: captured=50000, refunded=0 | 1 capture entry (50000) | R3: Duplicate event takes effect at most once; returns duplicate without mutating DB. |
| **2** | case_004 | `applied` (R4) | `rejected` (R4) | N/A | `pay_1`: captured=50000, refunded=0 | 1 capture entry (50000) | R4: A payment ID cannot be captured a second time. |
| **3** | case_007 | `applied` (R4) | `applied` (R6) | `applied` (R6) | `pay_1`: captured=50000, refunded=50000 | 1 capture (50000), 2 refunds (20000, 30000) | R6: Exact boundary refund allowed (20000 + 30000 == 50000). |
| **4** | case_009 | `applied` (R4) | `applied` (R6) | `rejected` (R6) | `pay_1`: captured=50000, refunded=20000 | 1 capture (50000), 1 refund (20000) | R6: Second refund rejected because 20000 + 35000 > 50000. |
| **5** | case_010 | `rejected` (R5) | N/A | N/A | (empty) | (empty) | R5: Refund requires existing captured payment. |
| **6** | case_016 | `rejected` (R2) | N/A | N/A | (empty) | (empty) | R2: Boolean literal `true` is not an integer paise amount. |
| **7** | case_039 | `rejected` (R1) | N/A | N/A | (empty) | (empty) | R1: Signature must equal lowercase hex HMAC. Uppercase is rejected. |
| **8** | case_041 | `rejected` (R1) | N/A | N/A | (empty) | (empty) | R1: HMAC must be computed over raw body bytes, not re-serialized JSON. |
| **9** | case_047 | `rejected` (R5) | `applied` (R4) | `applied` (R8) | `pay_1`: captured=50000, refunded=20000 | 1 capture (50000), 1 refund (20000) | R8: Rejected events do not consume event_id; redelivery succeeds once valid. |
| **10** | case_049 | `applied` (R4) | `rejected` (R1) | N/A | `pay_1`: captured=50000, refunded=0 | 1 capture (50000) | C3, R1: Signature check precedes duplicate check. Bad signature on applied ID returns rejected. |
