# PaySift: Demonstration & Self-Test Guide

This guide explains how to view the hosted deployment, run the one-command demonstration, and execute the automated self-test suite (Gate G8).

---

## 1. Live Hosted Links

- **Interactive Frontend (Vercel):** [https://pay-sift.vercel.app](https://pay-sift.vercel.app)
- **Hosted Backend API (Render):** [https://paysift-api.onrender.com](https://paysift-api.onrender.com)
  - API Interactive Swagger UI: [https://paysift-api.onrender.com/docs](https://paysift-api.onrender.com/docs)
  - Health Endpoint: [https://paysift-api.onrender.com/health](https://paysift-api.onrender.com/health)

> [!NOTE]
> The hosted backend runs on Render's free tier and spins down when idle. Cold starts take approximately 50 seconds. If the hosted backend is sleeping or unreachable, the frontend automatically falls back to an embedded pre-computed snapshot so all demo views, kill matrices, shrunk traces, and repair outcomes remain 100% interactive.
>
> Render's container environment does not provide Docker, so the hosted backend runs in **Read-Only Mode** (`HOSTED_MODE=1`). Read operations (`/runs`, `/runs/{id}`, `/kill-matrix`, `/evidence`, static `/break` replays, cached `/repair`) are active. Live LLM execution, dynamic Docker sandbox evaluation, and live repair run exclusively locally with your own Docker daemon and API keys.

---

## 2. Quick Start: Local Offline Demo & Self-Test

### One-Command Offline Demo
```bash
python cli.py demo
```
- **What it does:**
  1. Regenerates all static HTML reports in `report/out/` (100% self-contained, 0 external CDN assets).
  2. Displays all demonstration artifacts and hero findings.
  3. Launches the PaySift REST API on `http://127.0.0.1:8000` (interactive documentation at `http://127.0.0.1:8000/docs`).
- **Flags:**
  - `--no-serve`: Prepares reports and prints URLs without starting the long-running server.
  - `--port <PORT>`: Custom API port (default: 8000).

### Fast End-to-End Self-Test (Gate G8)
```bash
python cli.py selftest
```
- **Target runtime:** < 2 minutes (typically ~40 seconds).
- **Status:** PASSED (Hostile Docker sandbox checks safely skipped when Docker is absent).
- **Coverage:** Environment checks, spec SHA consistency (`contract/SPEC_HASH`), schema validation across all run JSONs, kill matrix sensitivity assertions (13 of 13 hand-written mutants killed, reference clean 100/100), counterexample delta debugging & shrinking (max 3 events for m7, $\le 4$ overall), break-it scenario verdicts, static HTML reports generation, core unit tests, and git baseline preservation.

### Full Self-Test (Full Parity & Gates)
```bash
python cli.py selftest --full
```
- Includes all hostile sandbox containment tests and concurrency stress tests (when Docker is running).

---

## 3. Data & Artifact Taxonomy: What is Cached vs Live

PaySift maintains strict labeling across all outputs:

| Label / Source | Meaning | Where Used |
|---|---|---|
| `[LIVE GENERATION]` | Generated in real-time by an LLM and evaluated inside the Docker sandbox. | Active local pilot runs |
| `[PRE-RUN CACHED]` | Pre-computed model output generated and verified beforehand. | Saved candidate runs (`runs/`) |
| `[HAND-WRITTEN MUTANT]` | Hand-crafted intentional bug. **Not model output.** | `m1`–`m9`, `x1`–`x4`, `runs/real_example.json` |
| `[REFERENCE HANDLER]` | Formally correct reference implementation (`ref/handler_ref.py`). | Baseline, passes 100/100 invariants |
| `[STUB (STAND-IN)]` | Reference handler used as pipeline test stand-in. **Never used for demo claim.** | Offline repair pipeline tests |

### The Opening Demo Finding (Screen 1):
- **Real Model Finding:**
  - **Candidate:** `strong_a/A/3` (Gemini 3.5 Flash Lite, Condition A)
  - **Run JSON:** [`runs/run_3_1795260584.json`](file:///runs/run_3_1795260584.json)
  - **Classification:** `(a)` - Rule violated as written (confirmed by Nikhil and Nehaa)
  - **Vulnerability:** Rule R8 (Rejection Non-Consumption). Handler recorded all events in `processed_events` even on rejection, blocking redelivery when prerequisites were satisfied.
  - **Minimal Counterexample:** Shrunk via delta debugging to **4 events** (1-minimal, 10/10 reproducible across runs).
  - **Repair Artifact:** [`repair/cache/3__0.json`](file:///repair/cache/3__0.json) (Rule R8 fixed with 0 regressions, grounded with 9 You.com citations).
- **Mutant Demonstration Fallback (Offline):**
  - **File:** [`runs/real_example.json`](file:///runs/real_example.json)
  - **Status:** Hand-written mutant fallback (`m1_no_dedupe`, **not model output**)
  - **Vulnerability:** Rule R3 (Event Idempotency). Duplicate webhook delivery records duplicate ledger entries.
  - **Impact:** ₹561.25 captured twice resulting in **₹561.25 created from nothing** in the ledger.
  - **Minimal Counterexample:** Shrunk via delta debugging to exactly **2 events** (1-minimal, 10/10 reproducible).

---

## 4. Key Demonstration URLs
When running `python cli.py demo` or `python cli.py serve`:
- **Dashboard Hub:** `report/out/index.html`
- **The Money Bug (Hero):** `report/out/real_example.html`
- **Mutant Kill Matrix:** `report/out/kill_matrix.html`
- **Break-it Scenarios Replay:** `report/out/scenarios.html`
- **Interactive REST API Docs:** `http://127.0.0.1:8000/docs`
