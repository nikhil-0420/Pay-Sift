# PaySift: Demonstration & Self-Test Guide

This guide explains how to run the one-command demonstration and the automated self-test suite (Gate G8).

---

## 1. Quick Start

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
- **Status:** PASSED (Docker checks skipped due to BH-001).
- **Coverage:** Environment checks, spec SHA consistency, schema validation across all 170+ run JSONs, kill matrix sensitivity assertions (13/13 hand-written mutants killed, reference clean), counterexample delta debugging & shrinking (max 3 events for m7, $\le 4$ overall), break-it scenario verdicts, static HTML reports generation, core unit tests, and git baseline preservation. Hostile Docker sandbox checks are safely skipped when Docker is absent.

### Full Self-Test (Full Parity & Gates)
```bash
python cli.py selftest --full
```
- Includes all hostile sandbox containment tests and concurrency stress tests (when Docker is running).

---

## 2. Requirements & Environment
- **Python:** 3.12+ (standard library + pinned requirements in `.venv`).
- **Docker:** Required for live candidate execution and hostile sandbox verification (`paysift-sandbox:1`).
- **API Keys:** Optional for offline demo; required for live model candidate generation and live repairs (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc. in `.env`).

---

## 3. Data & Artifact Taxonomy: What is Cached vs Live

PaySift maintains strict labeling across all outputs:

| Label / Source | Meaning | Where Used |
|---|---|---|
| `[LIVE GENERATION]` | Generated in real-time by an LLM and evaluated inside the Docker sandbox. | Active pilot runs |
| `[PRE-RUN CACHED]` | Pre-computed model output generated and verified beforehand. | Saved candidate runs |
| `[HAND-WRITTEN MUTANT]` | Hand-crafted intentional bug. **Not model output.** | `m1`–`m9`, `x1`–`x4`, `runs/real_example.json` |
| `[REFERENCE HANDLER]` | Formally correct reference implementation (`ref/handler_ref.py`). | Baseline, passes 100/100 invariants |
| `[STUB (STAND-IN)]` | Reference handler used as pipeline test stand-in. **Never used for demo claim.** | Offline repair pipeline tests |

### The Opening Demo Finding (Screen 1):
- **File:** [`runs/real_example.json`](file:///runs/real_example.json)
- **Status:** Hand-written mutant fallback (`m1_no_dedupe`)
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
