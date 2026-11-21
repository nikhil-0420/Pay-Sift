# PaySift Runs Directory (`runs/`) — Frontend Developer Guide

This directory holds the artifacts, ground-truth runs, scenario verdicts, and counterexamples consumed by the PaySift web UI and static report pages.

---

## 1. Schema Location & Contract Version
- **JSON Schema:** [`contract/run_schema.json`](file:///contract/run_schema.json)
- **Validator Script:** [`contract/validate_run.py`](file:///contract/validate_run.py)
- **Contract Version:** `1.0` (Draft-Frozen pending Gate 1)

Every `<run_id>.json` file in this directory strictly validates against `contract/run_schema.json`.

---

## 2. Directory Contents & Artifact Taxonomy

### A. Synthetic / Mock Files (For UI Testing Before Pilot Finishes)
| File | Purpose | Notes |
|---|---|---|
| `runs/sample.json` | Synthetic run containing all failure shapes and modes | **FAKE / MOCK DATA**. Used to build and test UI widgets before real test runs exist. |
| `runs/kill_matrix.sample.json` | Synthetic kill matrix layout | **FAKE / MOCK DATA**. Illustrates matrix table layout. |

### B. Hero Demonstrations & Static Replay
| File | Purpose | Notes |
|---|---|---|
| `runs/real_example.json` | **The Primary Hero Finding**. Contains the cleanest minimal counterexample trace with Rs created from nothing. | Validated run file. If model execution was blocked, this is sourced from `m1_no_dedupe` with label `"hand-written mutant, not model output"`. |
| `runs/scenario_verdicts.json` | Pre-computed verdicts and ledger diffs for all 6 canonical break-it scenarios across all candidates. | Powers the interactive static scenario replay panel without requiring a live backend API server. |
| `runs/kill_matrix.json` | Real executed kill matrix across reference handler and all 13 mutants. | Verified pass/kill results across all 5 invariants. Reference is 100% clean. |

### C. Executed Candidate Runs (`runs/run_<target>_<timestamp>.json`)
Each JSON document records the full verification results of a specific handler under test:
- `candidate`: Metadata including `id`, `model`, `condition` (`A` = formal contract, `B` = casual prompt, `-` = mutant/reference), `sha256`, `source` (`live`, `pre-run`, `reference`, `mutant`, `stub`), and `label`.
- `results`: Counts of passed and failed seeds for each invariant (`I1_signature`, `I2_idempotency`, `I3_conservation`, `I4_bounds`, `I5_interface`) under normal and restart execution modes.
- `concurrency`: Concurrency scenario results (Scenario A and Scenario B trial counts, failures, warnings).
- `failures`: List of failure objects. Each contains:
  - `invariant`: Violated invariant name
  - `rule`: Violated rule ID (R0–R10)
  - `seed`: Failing seed integer
  - `first_bad_step`: Zero-based step index where divergence occurred
  - `minimal_stream`: Shrunk minimal event sequence (<= 4 events for sequential bugs)
  - `shrink_history`: Array of event lists documenting each minimization step
  - `one_minimal`: Boolean indicating whether 1-minimality was strictly verified
  - `repro`: Object with `runs` (10) and `reproduced` (10) proving counterexample stability
  - `explanation`: Deterministic template explanation describing the failure arithmetic
  - `classification`: Classification object (`label`, `by: "agent-proposed"`, `note`)

---

## 3. How to Read and Animate `shrink_history`

The `shrink_history` property enables step-by-step counterexample visualization (e.g. animating a 40-event stream shrinking down to 2 events):

```json
"shrink_history": [
  [ /* Step 0: full initial stream (e.g. 10-40 events) */ ],
  [ /* Step 1: partition complement subset (e.g. 5 events) */ ],
  [ /* Step 2: further reduced subset (e.g. 3 events) */ ],
  [ /* Step 3: final 1-minimal stream (e.g. 2 events) */ ]
]
```

### UI Animation Guidelines:
1. **Initial State:** Display `shrink_history[0]` as a timeline or list of webhook events.
2. **Animation Loop:** Step through each slice `shrink_history[i]`. Gray out or strike through eliminated events to show the delta debugging partition testing process.
3. **Hero Counter:** In `real_example.json`, observe the duplicate capture event firing twice. Display the ledger balance flipping from expected ₹500 to observed ₹1,000, and highlight the red counter: **`₹500 created from nothing`**.
4. **Minimality Callout:** When `one_minimal: true`, render the badge:
   `1-Minimal: removing any single remaining event removes the failure`.
