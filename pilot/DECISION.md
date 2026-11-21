# PaySift Pilot Decision & Demo Candidate Selection

- **Timestamp:** `2026-11-21T11:40:00Z`
- **Reviewers:** Nikhil & Nehaa
- **Decision:** `FINDING`
- **Demo Candidate:** `strong_a/A/3`
- **Failing Rule:** `Rule R8: Rejection Non-Consumption`
- **Violated Invariant:** `I2_idempotency`
- **Classification:** `(a)` - Rule violated as written
- **Illustrative Only:** `false` (Occurred under Condition A with full formal specification contract prompt)
- **Honest Label for Pitch:** `"real model finding"`

---

## 1. Context & Scope
- **Total Evaluated Candidates:** 15 candidates across 2 usable models:
  - Gemini 3.5 Flash Lite (`strong_a`): 10 candidates (5 Condition A, 5 Condition B)
  - Qwen 2.5 27B on Groq (`strong_b`): 5 candidates (3 Condition A, 2 Condition B)
  - OpenRouter Ling 3.2 Flash (`strong_c`): 0 candidates (free tier upstream rate-limited)
- **Discovery:** A genuine financial/idempotency bug was discovered in model-generated code adhering to the full contract (`strong_a/A/3`).

---

## 2. Selected Demo Candidate Details
- **Candidate:** `strong_a/A/3` (`candidates/strong_a/A/3.py`)
- **Model:** `gemini-3.5-flash-lite`
- **Condition:** `A` (Full specification prompt, rules R0–R10 printed verbatim)
- **Rule Violated:** `Rule R8: Rejection Non-Consumption`
  > "A 'rejected' event produces no state change and does NOT consume its event_id. If the same event_id is redelivered later with valid parameters or prerequisites satisfied, it must be processed and applied normally."
- **Failure Mechanism:** The candidate recorded all incoming event IDs in an auxiliary table `processed_events` even when rejected. When the prerequisite capture event arrived later and the refund event was redelivered, the candidate treated the redelivered refund as a duplicate instead of processing it.
- **Trace Length:** 4 events (1-minimal, 10/10 reproducible across runs)
- **Artifacts:**
  - Run Output: [`runs/run_3_1795260584.json`](file:///runs/run_3_1795260584.json)
  - Diagnostic Packet: [`pilot/packets/3__0.md`](file:///pilot/packets/3__0.md)

---

## 3. Human Classifications Table

| Candidate | Condition | Failing Rule | Invariant | Class | Notes |
|---|---|---|---|---|---|
| `strong_a/A/3` | `A` | `Rule R8` | `I2_idempotency` | `(a)` | R8 rejected events consumed; confirmed by Nikhil and Nehaa in packet review |

---

## 4. Pitch Positioning & Next Steps
- **Hero Presentation:** Feature `strong_a/A/3` as the central demo counterexample.
- **Pitch Label:** **"Real model finding"** discovered by PaySift's invariant harness on Gemini 3.5 Flash Lite under strict contract testing.
- **Next Steps:**
  1. Nikhil executes **Stage K7** (Sync UI data and ensure demo hero reflects `strong_a/A/3`).
  2. Nikhil executes **Stage K8** (Retrieve evidence citations for Rule R8).
  3. Nehaa executes **Stage N8** (Repair loop on `strong_a/A/3`).
