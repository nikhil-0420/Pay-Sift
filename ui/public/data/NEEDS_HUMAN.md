# NEEDS_HUMAN.md

Items requiring human attention, configuration, or decision. Format:
ID | Phase | Severity (BLOCKER | IMPORTANT | FYI) | What is needed | What was done meanwhile | Resolution

---

### NH-001: Model IDs and API Keys not configured in config/models.yaml
- **Phase:** P0
- **Severity:** IMPORTANT
- **What is needed:** `config/models.yaml` contains placeholder `FILL_ME` strings and no API keys are configured in `.env`. Real model candidates cannot be generated via live provider APIs without keys and valid model names.
- **What was done meanwhile:** Left `config/models.yaml` untouched per instructions. Marked generation steps to use stubs / pre-runs until configured.
- **How human resolves:** In the morning (or when ready), add real model IDs to `config/models.yaml` and export corresponding keys in `.env`.

### NH-002: Host Python version is 3.14.5 instead of 3.12
- **Phase:** P0
- **Severity:** FYI
- **What is needed:** The plan specifies Python 3.12. Host currently has Python 3.14.5 and Python 3.11.9 installed, but not 3.12.
- **What was done meanwhile:** Created `.venv` using the available host Python. All written code is restricted to standard Python 3.12 features and constructs.
- **How human resolves:** If strict 3.12 execution is required on the host, install Python 3.12 and recreate `.venv`. Note that Docker sandbox in P4 will use `python:3.12-slim`.

### NH-003: Docker CLI and daemon not detected
- **Phase:** P0
- **Severity:** IMPORTANT
- **What is needed:** Docker Desktop needs to be running and accessible via CLI in PATH to build `paysift-sandbox:1` and run Gate 4 hostile tests and candidate sandbox.
- **What was done meanwhile:** `check-env` reported Docker CLI missing. Trusted tests (reference, mutants, CLI tests) run natively. No untrusted model code will be executed natively.
- **How human resolves:** Start Docker Desktop, add docker to PATH if needed, and pull `python:3.12-slim`.

---

## Spec questions for Gate 1

### SQ-001: Attribution of R10 Concurrency Scenarios
- **Question:** Plan section 7 lists rule R10 under `I4_bounds`, but Scenario A tests concurrent delivery of the identical capture event (an idempotency/R3 property), while Scenario B tests concurrent refund events competing against a balance (a bounds/R6 property).
- **Adopted Resolution:** In `SPEC.md` and the oracle, Scenario A failures cite R10 under `I2_idempotency`, and Scenario B failures cite R10 under `I4_bounds`. Both count toward the financial headline.
- **Action for Gate 1 Reviewers:** Confirm during Gate 1 review whether this attribution aligns with team expectations.
- **Gate 1 Resolution:** CONFIRMED by Koushik and Rithvik on 2026-11-21. Scenario A attribute under I2_idempotency and Scenario B under I4_bounds adopted as final.

### BH-001: Docker Unavailable on Host (Gate 4 Hard Blocker)
- **Logged:** 2026-11-20T21:52:33.947575+00:00
- **Status:** RESOLVED (2026-11-21)
- **Resolution:** Docker sandbox `paysift-sandbox:1` built and verified. Gate 4 PASSED (`runs/GATE4_PASSED` generated). All 7 hostile handlers contained, native vs sandbox parity confirmed across seeds 0-19 for all 11 mutants and seeds 0-99 for reference handler.
- **Action:** None. Gate 4 is unblocked.

### BH-002: No Usable Model Config (P7 Blocker)
- **Logged:** 2026-11-20T23:20:00+00:00
- **Status:** BLOCKER
- **Impact:** Real candidate generation cannot call provider APIs. All model IDs in `config/models.yaml` are `FILL_ME` and environment variables `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, and `SMALL_MODEL_API_KEY` are unset.
- **What was done meanwhile:** Built full generation pipeline, intake code extraction, AST gate integration, key scrubbing, exponential backoff retries, and spec_sha binding; tested end-to-end with fake provider adapters; wrote `candidates/GENERATION_SUMMARY.md`.
- **Action:** Add real model IDs in `config/models.yaml` and export API keys in `.env`, then run `python cli.py generate`.

### BH-003: Pilot Blocked (Sandbox Gate Not Passed)
- **Logged:** 2026-11-20T23:35:00+00:00
- **Status:** BLOCKER
- **Impact:** Phase P8 pilot runner halts execution. Precondition check failed because `runs/GATE4_PASSED` does not exist (Docker unavailable on host, BH-001). In accordance with Agent Rule 3, no untrusted candidate can be executed.
- **What was done meanwhile:** Built pilot runner engine (`pilot/runner.py`), failure packet generator (`pilot/packets.py`), wired `cli.py pilot`, wrote `runs/real_example.json` (mutant fallback) for UI development, wrote `pilot/packets/m1_no_dedupe__0.md`, and generated `pilot/PILOT_REPORT.md` stating "PILOT BLOCKED: sandbox gate not passed".
- **Action:** Install Docker, build `paysift-sandbox:1`, run `python cli.py sandbox-test` to pass Gate 4, then run `python cli.py pilot`.

### BH-004: Real Repair Pre-generation Blocked (Stub Stand-in Used)
- **Logged:** 2026-11-21T00:05:00+00:00
- **Status:** BLOCKER
- **Impact:** Phase P9 repair loop cannot execute live model calls because Docker sandbox is not verified (Gate 4 blocked, BH-001) and model API keys are unconfigured (BH-002).
- **What was done meanwhile:** Built full repair loop pipeline (`repair/repair.py`), prompt builder (`repair/prompt.py`), fixed break-it scenarios (`scenarios/scenarios.py`, `runs/scenario_verdicts.json`), REST API (`api/main.py`), and static HTML reports (`report/generate.py`). Verified repair pipeline using a trusted mutant (`m1_no_dedupe`) and reference handler as stand-in, labeled "stub" everywhere. Stubs were strictly excluded from `repair/cache/`.
- **Action:** In the morning, after Gate 4 passes and model API keys are exported, run `python cli.py repair --candidate <real_candidate_id>` to pre-generate and cache a real model repair for the demo.

### Model Configuration Notice (P7)
- [NH-CFG-STRONG_A] Model 'strong_a': model_id is FILL_ME or empty. Please set environment variable `ANTHROPIC_API_KEY` or configure a valid model_id in config/models.yaml.
- [NH-CFG-STRONG_B] Model 'strong_b': model_id is FILL_ME or empty. Please set environment variable `OPENAI_API_KEY` or configure a valid model_id in config/models.yaml.
- [NH-CFG-STRONG_C] Model 'strong_c': model_id is FILL_ME or empty. Please set environment variable `GEMINI_API_KEY` or configure a valid model_id in config/models.yaml.
- [NH-CFG-SMALL_A] Model 'small_a': model_id is FILL_ME or empty. Please set environment variable `SMALL_MODEL_API_KEY` or configure a valid model_id in config/models.yaml.

### NH-SEC-001: Secret scan hit in MORNING_HANDOFF.md
- **Status:** EXCLUDED FROM COMMITS
- **File and Lines:** `MORNING_HANDOFF.md` lines 65, 66, 67
- **Reason:** Matches pattern assignment `*_API_KEY=<non-empty value>`
- **Resolution:** Review file and remove key assignments before publishing this file.
