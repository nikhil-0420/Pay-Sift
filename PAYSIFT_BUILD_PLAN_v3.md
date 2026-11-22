# PaySift: Build Plan (v3, final)

**Tagline:** Find the bugs before money moves.
**Subline:** Stress-test AI-written payment code. Get the smallest event sequence that breaks it.

**One-line pitch:** AI can write payment code that looks right. PaySift tests whether it keeps the money correct under duplicates, forged signatures, bad refunds, process restarts and concurrent delivery, and shows the smallest event sequence that breaks it.

**Event:** BEYOND 9TO5 Buildathon, 21 Nov 2026, 8 hours, offline, open theme.

**Build style:** depth-first. Finish one thin slice end to end, then deepen it. Never start a new layer while the previous one is unproven.

**This file is the source of truth.** `contract/SPEC.md` is generated from section 5. Every prompt in `docs/process/PAYSIFT_ANTIGRAVITY_PROMPTS.md` defers to this file.

---

## 0. What changed from v2 (all fixes folded in below)

| # | Problem found in v2 | Fix in v3 | Where |
|---|---|---|---|
| 1 | Hero demo bug (double credit) is unlikely to come from a real model; opening on a mutant while saying "your AI agent wrote this" would be false | The opening bug must come from a real pilot candidate, labeled with model, condition, sample, hash. Mutants are always labeled "hand-written mutant". Demo script is finalized only after the pilot | 16 |
| 2 | `worker.py` ran all sequences in one process, so a module-level `set()` dedupe would fail normal runs and Gate 5 would contradict itself | Normal mode = fresh process per sequence. Restart mode = fresh process per call | 6 |
| 3 | R1 untestable with canonical-only signed bodies | Valid-signed streams also use non-canonical bodies (whitespace, key order, `\u` escapes, trailing newline) | 8 |
| 4 | Oracle ignored `status`, yet spec clauses depend on it | New invariant I5 (interface): status and totality. Headline counts financial invariants I1-I4 only; I5 reported separately | 7, 11 |
| 5 | Spec gaps (huge ints, non-ASCII signature, hex case, missing fields, same event_id different payload, exceptions) would create (b) failures | R0 added; R1/R2 tightened; clarifications C1-C9; amount bound 1..10^12 | 5 |
| 6 | "Frozen before generation" contradicted the pilot loop | Honest wording; every candidate and run carries `spec_sha`; mixing spec versions is refused mechanically; post-pilot changes logged | 2, 11 |
| 7 | AST allowlist could silently inflate failures | Non-compliant candidates are regenerated (max 2 extra), excluded from the headline denominator and reported | 11 |
| 8 | Pilot ran too late and depended on Phase 6 | Generation starts right after SPEC freeze; sequential pilot runs as soon as Gate 4 passes | 19 |
| 9 | Nikhil still the bottleneck; nobody owned the one-command pipeline | Koushik owns the pipeline; Nehaa and Koushik do first-pass classification; Nikhil does final review only | 1 |
| 10 | Pre-flight said "do today" on event day | Pre-flight collapsed into hour 0, run in parallel | 3 |
| 11 | Kill matrix is circular (authors wrote oracle and mutants) | Stated openly; m4-m6 written blind to oracle code; extra "natural bug" mutants x1-x4 added | 9, 17 |
| 12 | ddmin had no budget; R7 only checked between calls | Budgeted ddmin with 1-minimal flag; R7 mid-call limit stated as a limitation | 13, 2 |
| 13 | Single-file bind mount and `C:\` colon parsing fragile on Docker Desktop | Runner baked into a local image; candidate mounted as a directory; docker invoked via argument list (no shell) | 10 |
| 14 | Scenario B underspecified | 4 processes deliver refund X, 4 deliver refund Y, one barrier | 12 |
| 15 | Demo step 5 depended on a stretch feature | Static scenario-replay fallback required | 16 |
| 16 | Backend is built by an autonomous overnight agent | Section 4: operating contract, human-only gates, no git writes | 4 |

---

## 1. Team and ownership

| Person | Role | Owns |
|---|---|---|
| **Nikhil** | Project lead, backend head | `contract/SPEC.md`, `oracle/`, `ref/handler_ref.py`, mutants m1-m3, run JSON schema, final classification review, pitch |
| **Nehaa** | Backend | `runner/` (sandbox, worker, concurrency), Docker, AST gate, hostile tests, restart and concurrency modes, mutants m7-m9, first-pass classification |
| **Koushik** | Backend | `runner/streams.py`, `shrink/`, `generate/`, pilot runs, repair loop, FastAPI, static HTML report, **one-command pipeline**, mutants m4-m6, first-pass classification |
| **Rithvik** | Frontend | The whole UI, built against `runs/sample.json` until real runs exist |

### Ownership rules

1. One owner for `SPEC.md` (Nikhil). Any spec change after freeze changes `spec_sha`, goes through him, and **triggers full regeneration** of candidates.
2. Nikhil is protected: handoffs of schema and fixtures happen first; classification is split (Nehaa + Koushik first pass, Nikhil final); the pipeline belongs to Koushik.
3. Rithvik builds only against `sample.json` until real runs exist. Nobody changes the run JSON schema after freeze without telling him.
4. Everyone reads the pilot traces. Classifying failures (a)/(b)/(c)/(d) is the most error-prone step.
5. One narrator and one demo driver.

### Integration checkpoints

End of hour 2, 4, 6. Each: everyone runs `python cli.py demo` or `python cli.py selftest` on one laptop and shows the state of their piece. No integration at the end.

---

## 2. What we claim and do not claim

**Claim (stage and Q&A):** on one fixed, published contract, these specific generated handlers violated these specific rules, reproducibly, with a minimal trace.

**Do not claim:**
- A ranking of models.
- That all AI-generated payment code is unsafe.
- That passing means correct. Passing means "no violation found in N seeded streams and M concurrent trials".
- That the combination is novel. Carbon Layer and payfuzz test webhook handlers for duplicates, ordering and signatures. Our difference: the target (generated code), the model-based oracle, restart and concurrency checks, the minimal counterexample, and the repair loop.
- That the oracle is proven correct. The kill matrix shows it catches the bugs we thought of (see 17).

**Known limitations (say them if asked):**
- R7 atomicity is checked between calls (and via x/m2-style inconsistency), not by killing a process mid-transaction.
- Concurrency passes are probabilistic; failures are real.
- The shrinker does not apply to race failures.

**Freeze wording (replaces v2):** "Spec, prompts and oracle were frozen before the final generation run. Every candidate and run records `spec_sha` and `oracle_sha`. Any change made after the pilot is logged in `DECISIONS.md` and forced a full regeneration."

**Condition rule:** results from the **casual prompt** (Condition B) are labeled *illustrative* everywhere. They never feed the headline, which comes only from the **full-spec prompt** (Condition A).

**Stage rule:** keep the hedging for Q&A. The first 30 seconds of the pitch are the bug, not the caveats.

---

## 3. Pre-flight (hour 0, in parallel; all of this finishes before agent output is trusted)

1. **Rules check.** Ask the organizers whether pre-event preparation (specs, prompts, pre-generated outputs, code) is allowed. If it is not, the overnight build must be rebuilt at the event: use the phase prompts as the rebuild order, and never present pre-built work as event work.
2. **Docker works offline** (Windows, Docker Desktop with WSL2). Pre-pull `python:3.12-slim`. Verify `docker run --rm --network none python:3.12-slim python -c "print(1)"`.
3. **Build the sandbox image and test the exact invocation** from PowerShell and from Python `subprocess` (argument list, no shell). No unsandboxed model code on any machine.
4. **API keys.** Two or three strong model families plus one small/cheap model. One real call each. Keys in env vars or `.env` (git-ignored). Fill `config/models.yaml` with the exact model id strings.
5. **Repo skeleton** exists (below). **Source of truth:** this file; `contract/SPEC.md` derives from section 5.
6. **Check name availability:** domain and GitHub org. Open with "PaySift tests the code, not the transactions".

### Repo skeleton

```
paysift/
  AGENT_RULES.md  PROGRESS.md  DECISIONS.md  NEEDS_HUMAN.md  MORNING_HANDOFF.md
  cli.py                     (check-env, run, kill-matrix, sandbox-test, pilot, shrink, repair, report, serve, demo, selftest)
  config/     models.yaml
  contract/   SPEC.md  schema.sql  events.py  build_prompts.py  prompt_full.txt  prompt_casual.txt
              cases.jsonl  run_schema.json  SPEC_HASH
  oracle/     validate.py  model.py  checks.py
  ref/        handler_ref.py
  mutants/    m1..m9, x1..x4, MANIFEST.json
  runner/     streams.py  child.py  worker.py  run_candidate.py  concurrency.py  sandbox.py  ast_gate.py  Dockerfile
  shrink/     ddmin.py  predicate.py  explain.py
  generate/   providers.py  generate.py  intake.py
  repair/     repair.py  cache/
  scenarios/  scenarios.py   (break-it streams)
  candidates/ <model>/<condition>/<sample>.py + .meta.json + .raw.txt
  runs/       sample.json  real_example.json  <run_id>.json  kill_matrix.json
  pilot/      packets/  PILOT_REPORT.md
  api/        main.py
  report/     generate.py  out/
  tests/      (pytest; tests/hostile/ for hostile handlers)
  ui/         (Rithvik)
  scripts/    sandbox.ps1  sandbox.sh
  .agent/     (agent logs and phase markers)
```

---

## 4. Execution modes and the overnight agent contract

**Overnight (Antigravity):** phases P0-P10 in `docs/process/PAYSIFT_ANTIGRAVITY_PROMPTS.md` build the whole backend with no human present.

Binding rules (full text in `AGENT_RULES.md`):
- **Never asks, never waits.** Blockers go to `NEEDS_HUMAN.md`; assumptions go to `DECISIONS.md`; the agent continues.
- **No git writes.** Everything stays uncommitted and unstaged. Humans commit and push in the morning. Read-only git commands only.
- **Untrusted code only in the sandbox.** Model-generated candidates and hostile test handlers run only inside Docker with `--network none`. No Docker, no such runs.
- **No faked results.** A gate that cannot pass is reported FAILED after at most 5 honest fix attempts.
- **Human-only gates:** Gate 1 (two people predict verdicts on fresh cases), classification of pilot failures, confirming the rules check, choosing the demo candidate.

**Morning handoff:** the agent ends with `MORNING_HANDOFF.md` (phase status, gate status, headline draft, NEEDS_HUMAN summary, suggested commit grouping with the git commands written out but not run).

---

## 5. Contract (SPEC v1.0)

A judge should be able to predict the oracle's verdict on any case from this section.

### Handler interface

```python
def handle_event(db_path: str, raw_body: bytes, signature: str, secret: str) -> dict:
    """Returns {"status": "applied" | "duplicate" | "rejected", "reason": str}."""
```

The return value is checked only by I5 (interface). **Financial truth is read from the database, never from the return value.** The harness initializes the schema before the first call.

### Event format (simplified generic gateway, not a real provider schema)

```json
{"event_id": "evt_001", "type": "payment.captured", "payment_id": "pay_1", "amount_paise": 50000}
{"event_id": "evt_002", "type": "refund.processed", "payment_id": "pay_1", "refund_id": "rfd_1", "amount_paise": 20000}
```

Money is integer paise everywhere.

### Harness-provided schema (no UNIQUE constraints on purpose, so duplicates are not masked)

```sql
CREATE TABLE payments (
  payment_id TEXT PRIMARY KEY,
  captured_paise INTEGER NOT NULL,
  refunded_paise INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE ledger (
  entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('capture','refund')),
  amount_paise INTEGER NOT NULL,
  event_id TEXT
);
```

Handlers may create extra tables and indexes of their own. They must not drop or alter `payments` or `ledger`. The oracle reads only `payments` and `ledger` and does not check the `event_id` column.

### Numbered rules (every failure cites one)

| ID | Rule |
|---|---|
| R0 | **Totality (interface).** For every input the handler returns a dict with `status` in {applied, duplicate, rejected} and a string `reason`. It never raises and never hangs (5 s per call). |
| R1 | The signature must equal the **lowercase hex** HMAC-SHA256 of the **raw body bytes**, keyed with the UTF-8 secret. Anything else (missing, empty, wrong, non-hex, uppercase, non-ASCII, signed over re-serialized JSON): `rejected`, no state change, no exception. |
| R2 | Body must be valid UTF-8 JSON and a JSON object with: `event_id` (non-empty string, at most 64 chars), `type` (`payment.captured` or `refund.processed`), `payment_id` (non-empty string, at most 64 chars), `amount_paise` (a JSON integer from 1 to 10^12 inclusive: not bool, not float even if `5.0`, not string, not null), and for `refund.processed` also `refund_id` (non-empty string). Extra fields are ignored. Any violation: `rejected`, no state change. |
| R3 | An `event_id` takes effect at most once. Redelivery of an applied event (valid signature, valid payload): `duplicate`, no state change. |
| R4 | `payment.captured`: if the payment has no capture, create it (`captured_paise` = amount, `refunded_paise` = 0) and write exactly one `capture` ledger entry. If it already has a capture: `rejected`, no state change. |
| R5 | `refund.processed` requires an existing captured payment. Otherwise `rejected`. |
| R6 | Refund bound: `refunded + amount <= captured`. Otherwise `rejected`, no state change. When applied: `refunded_paise += amount` and exactly one `refund` ledger entry. |
| R7 | Atomicity: `payments` and `ledger` always agree (`captured_paise` = sum of capture entries; `refunded_paise` = sum of refund entries). An event applies entirely or not at all. |
| R8 | A `rejected` event changes nothing and does **not** consume its `event_id`. It may be redelivered later and applied if it is then valid. |
| R9 | All state lives in the database. The process may be killed and restarted between any two calls. |
| R10 | Calls may run concurrently in separate processes on the same database file. R3 and R6 must still hold. |

### Clarifications (closed ambiguities)

- **C1. Idempotency key is `event_id` only.** `refund_id` is informational. Two distinct events carrying the same `refund_id` are two refunds, subject to R6.
- **C2.** A `duplicate` is decided only for events previously **applied** (R3, R8).
- **C3. Order of checks:** R1 signature, then R2 validation, then R3 duplicate, then R4/R5/R6. A bad signature on an already-applied `event_id` is `rejected`, not `duplicate`. A malformed body is `rejected` even if it would otherwise carry an applied id.
- **C4. Status mapping is exact:** `applied`, `duplicate`, `rejected`. `reason` is free text and never checked.
- **C5.** Same `event_id` with a different payload after the first was applied: `duplicate` (by C1/R3).
- **C6.** Extra tables and indexes allowed; `payments` and `ledger` definitions untouched.
- **C7.** The handler opens its own connection per call to `db_path`.
- **C8.** Decisions must not depend on wall-clock time.
- **C9.** The harness never sends duplicate JSON object keys; behavior on them is undefined and untested.

### Worked examples (in SPEC.md; they double as oracle unit tests)

| Stream | Expected final state |
|---|---|
| capture evt_1 ₹500 | pay_1: captured 500, refunded 0, 1 capture entry |
| capture evt_1 ₹500, capture evt_1 ₹500 | same as above (R3) |
| capture evt_1 ₹500, capture evt_2 ₹500 same payment | second `rejected` (R4) |
| capture ₹500, refund ₹300, refund ₹300 (distinct events) | second refund `rejected`, refunded 300 (R6) |
| capture ₹500, refund ₹300, refund ₹200 | both applied, refunded 500 (R6 boundary) |
| refund ₹100 on unknown payment | `rejected`, empty DB (R5) |
| capture with bad signature | `rejected`, empty DB (R1) |
| capture with uppercase hex signature | `rejected`, empty DB (R1) |
| capture signed over re-serialized JSON, body has spaces | `rejected` (R1) |
| capture with `amount_paise: -500`, `0`, `5.0`, `"500"`, `true`, `null`, `10**13` | each `rejected` (R2) |
| refund missing `refund_id` | `rejected` (R2) |
| refund before capture (rejected), capture applied, same refund event redelivered | refund `applied` (R8) |
| bad-signature event evt_1, then good-signature evt_1 | second `applied` (R1, R8) |
| capture evt_1 applied, then evt_1 with bad signature | `rejected` (C3) |
| two refund events with the same `refund_id`, both fit | both applied (C1) |

### Required fixture classes (`contract/cases.jsonl`, at least 40 cases)

Duplicates; second capture; multiple payments; exact-bound and over-bound refunds; refund before capture; unknown payment; each invalid amount type; missing and extra fields; non-object body; invalid UTF-8; invalid JSON; each signature variant (missing, empty, wrong secret, flipped byte, uppercase, non-ASCII, re-serialized); non-canonical valid bodies; rejected-then-redelivered; same refund_id twice; same event_id different payload.

**Gate 1 (human-only):** two people independently predict verdicts on 10 fresh cases from `cases.jsonl` (cases they did not write) and agree with the file. Any disagreement means the spec is ambiguous: fix the spec, not the test. Then **freeze SPEC.md, the schema, the handler signature and the run JSON schema**. Until then the agent marks the spec `DRAFT-FROZEN (Gate 1 pending)`.

### Prompts

**`prompt_full.txt` (Condition A, the fair test):** generated deterministically by `contract/build_prompts.py` from SPEC.md: the full spec text, interface, schema, and: "single file, no explanation, allowed imports: sqlite3, hmac, hashlib, json, time, typing, contextlib". Same prompt for every model.

**`prompt_casual.txt` (Condition B, illustrative):**

> Write a Python function `handle_event(db_path, raw_body, signature, secret)` for a payment gateway webhook. It receives `payment.captured` and `refund.processed` events as JSON, verifies the HMAC-SHA256 signature, and records them in the SQLite tables `payments` and `ledger` (schema and event examples below). Return `{"status": ..., "reason": ...}`. Single file, no explanation. Allowed imports: sqlite3, hmac, hashlib, json, time, typing, contextlib.

(Then the schema SQL and the two example events. No numbered rules.)

### Run JSON v1.1 (UI is just a viewer of this)

```json
{
  "run_id": "...", "contract_version": "1.0", "spec_sha": "...", "oracle_sha": "...", "created_at": "...",
  "candidate": {"id": "...", "model": "...", "condition": "A|B|-", "sample": 3, "sha256": "...",
                "source": "live|pre-run|reference|mutant|extra-mutant|stub", "label": "..."},
  "harness": {"mode_set": ["normal","restart","concurrency"], "docker": true, "cpus": 1},
  "seeds": [0, 99],
  "results": {
    "I1_signature":    {"normal": {"passed": 100, "failed": 0}, "restart": null},
    "I2_idempotency":  {"normal": {"passed": 97, "failed": 3}, "restart": {"passed": 20, "failed": 0}},
    "I3_conservation": {"normal": {"passed": 100, "failed": 0}, "restart": null},
    "I4_bounds":       {"normal": {"passed": 100, "failed": 0}, "restart": null},
    "I5_interface":    {"normal": {"passed": 100, "failed": 0}, "restart": null}
  },
  "concurrency": {"scenario_A": {"trials": 50, "failed": 0, "warnings": 0},
                  "scenario_B": {"trials": 50, "failed": 0, "warnings": 0}},
  "failures": [{
    "invariant": "I2_idempotency", "severity": "financial|interface", "rule": "R3", "mode": "normal",
    "seed": 17, "first_bad_step": 1,
    "stream": [], "minimal_stream": [], "one_minimal": true, "shrink_history": [],
    "expected": {}, "observed": {}, "explanation": "template text, no LLM",
    "classification": {"label": "a|b|c|d|unreviewed", "by": "agent-proposed|human", "note": ""}
  }],
  "noncompliant": null,
  "repair_of": null
}
```

`runs/sample.json` is a realistic fake (one failure, minimal trace, shrink history, kill matrix section) checked in first. It is never overwritten; real examples go to `runs/real_example.json`.

---

## 6. Execution architecture (fixes the process-model contradiction)

- **Host (trusted):** oracle, streams, orchestration, shrinker, reports.
- **Container (untrusted):** candidate handler only, driven by `runner/worker.py` and `runner/child.py`.
- **Normal mode:** one **fresh child process per sequence**. Module-level state may persist within a sequence (like a long-lived server) but never across sequences.
- **Restart mode:** one **fresh child process per call**. A module-level `set()` dedupe passes normal mode and fails here (R9).
- **Per step the child returns:** the handler's return value (or exception text or `timeout`), and a snapshot of `payments` and `ledger` read by the worker's own connection. The oracle on the host compares snapshots to the model. The candidate's return value is used only for I5.
- **Timeouts:** per call 5 s, per sequence 30 s. On timeout the child is killed and the step is recorded as R0 `timeout`.
- **Same code path natively and in Docker:** `child.py` and `worker.py` run identically; Docker only wraps them. Native execution is allowed **only** for trusted code (reference, mutants, extra mutants).

---

## 7. Oracle and invariants

`oracle/validate.py` is an independent validator written from SPEC.md only (it never imports reference code). `oracle/model.py` is a pure-Python model that returns `(status, rule)` for each event.

```python
class Model:
    def __init__(self): self.pay, self.applied, self.rejected_ids = {}, set(), set()
    def apply(self, ev, sig_ok, payload_ok):
        # returns (status, rule_responsible)
        if not sig_ok: return ("rejected", "R1")
        if not payload_ok: return ("rejected", "R2")
        eid = ev["event_id"]
        if eid in self.applied: return ("duplicate", "R3")
        p = self.pay.get(ev["payment_id"])
        if ev["type"] == "payment.captured":
            if p: return ("rejected", "R4")
            self.pay[ev["payment_id"]] = {"cap": ev["amount_paise"], "ref": 0, "n_cap": 1, "n_ref": 0}
            rule = "R8" if eid in self.rejected_ids else "R4"
        else:  # refund.processed
            if not p: self.rejected_ids.add(eid); return ("rejected", "R5")
            if p["ref"] + ev["amount_paise"] > p["cap"]: self.rejected_ids.add(eid); return ("rejected", "R6")
            p["ref"] += ev["amount_paise"]; p["n_ref"] += 1
            rule = "R8" if eid in self.rejected_ids else "R6"
        self.applied.add(eid); return ("applied", rule)
```

(Implementers: `rejected_ids` must also be updated for the R1, R2, R4 rejection branches. The snippet shows the idea; tests decide.)

After **every** step the oracle compares the DB snapshot to the model: `payments` rows, and per payment the ledger sum and entry count per kind. It also checks internal consistency (R7). The first diverging step is recorded and **attributed to the rule the model decided on** at that step (for example a double capture entry after a duplicate attributes to R3; a missing apply after a prior rejection attributes to R8; payments vs ledger disagreement attributes to R7).

| Invariant | Rules | Severity | Counts toward headline |
|---|---|---|---|
| I1 Signature | R1 | financial | yes |
| I2 Idempotency (incl. restart mode) | R3, R8, R9 | financial | yes |
| I3 Conservation | R4, R7 | financial | yes |
| I4 Refund bounds and validation | R2, R5, R6, R10 (concurrency) | financial | yes |
| I5 Interface | R0, status mismatch against model (C3, C4) | interface | **no, reported separately** |

---

## 8. Streams

`runner/streams.py`: seeded (`random.Random(seed)`), deterministic, 3 to 40 events per stream. The family is `seed % 10`, so seeds 0-99 give 10 per family:

| Family | Content |
|---|---|
| 0 | captures with injected duplicates |
| 1 | multiple payments, second-capture attempts |
| 2 | partial, exact-bound and over-bound refunds |
| 3 | refund before capture, unknown payment |
| 4 | invalid payloads: bool/float/string/null/zero/negative/huge amounts, missing `refund_id` and other fields, non-object, invalid UTF-8, invalid JSON |
| 5 | signature variants: missing, empty, wrong secret, flipped byte, uppercase, non-ASCII, signed over re-serialized JSON, bad signature on an applied id |
| 6 | rejected-then-redelivered (R8): refund before capture then capture then refund again; bad signature then good signature with the same id |
| 7 | duplicate refunds; same `refund_id` on distinct events; same `event_id` with a different payload |
| 8 | **non-canonical valid bodies** (spaced separators, reordered keys, `\u` escapes, trailing newline, pretty print) signed correctly over the raw bytes |
| 9 | long mixed streams (30-40 events) for shrinker demos |

Each step stores the raw body bytes (base64), the signature, and a debug `tag`. The oracle never trusts the tag: it recomputes signature validity and payload validity itself.

---

## 9. Mutants and the kill matrix

| ID | Bug | Must fail | Owner |
|---|---|---|---|
| m1 | no dedupe | R3 (I2) | Nikhil |
| m2 | ledger written, `payments` not updated | R7 (I3) | Nikhil |
| m3 | no refund bound | R6 (I4) | Nikhil |
| m4 | accepts negative amount | R2 (I4) | Koushik |
| m5 | rejected events marked processed | R8 (I2) | Koushik |
| m6 | signature over `json.dumps(parsed)` | R1 (I1) | Koushik |
| m7 | module-level in-memory dedupe | R9, restart mode only | Nehaa |
| m8 | check-then-insert without transaction | R10, scenario A | Nehaa |
| m9 | refund bound checked in a separate statement | R10, scenario B | Nehaa |
| x1 | accepts bool as amount | R2 | extra |
| x2 | accepts float amount | R2 | extra |
| x3 | non-ASCII signature crashes handler | R0 (I5) | extra |
| x4 | signature over `json.dumps(parsed, sort_keys=True, separators=(",",":"))` | R1, only caught by family 8 | extra |

m4-m6 are written from SPEC and the reference handler **without reading oracle code** (blindness note recorded in `mutants/MANIFEST.json`). x1-x4 model plausible LLM bugs and prove the streams have coverage. m7-m9 need the later modes.

---

## 10. Sandbox and candidate intake (hard gate before any model code runs)

### Candidate intake

1. Prompt = `prompt_full.txt` (Condition A) or `prompt_casual.txt` (Condition B).
2. Store per candidate: model id string, provider, condition, sample, attempt log, raw response, extracted code, SHA-256, timestamp, `spec_sha`, prompt hash, temperature and token usage.
3. **AST allowlist** (`runner/ast_gate.py`) rejects imports outside the list (plus harmless `__future__`, logged), and calls to `exec`, `eval`, `open`, `__import__`, `compile`. Defense in depth, not the security boundary.

### Execution

Image `paysift-sandbox:1` is built locally from `runner/Dockerfile` (`FROM python:3.12-slim`, runner baked in). The candidate is mounted as a **directory** (`/cand`, read-only) containing `handler.py`. Streams go in over stdin; results come back on stdout. Invoked from Python with an argument list (no shell), plus wrapper scripts for PowerShell and bash.

```
docker run --rm -i --network none --read-only --tmpfs /tmp:rw,size=64m
  --memory 256m --cpus 1 --pids-limit 128 --cap-drop ALL --security-opt no-new-privileges
  --user 65534 -e PYTHONDONTWRITEBYTECODE=1 -e PYTHONHASHSEED=0
  -v <abs_candidate_dir>:/cand:ro paysift-sandbox:1 python /runner/worker.py ...
```

Concurrency mode uses `--cpus 2` (recorded in `harness.cpus`). On timeout the container is killed and removed by name. The DB lives in `/tmp` inside the container and is disposable.

### Sandbox self-test (these are the gate)

Hostile handlers (run directly through the sandbox, bypassing the AST gate on purpose). All must be contained and reported as `error`, never crash the runner or leave containers behind:
1. Opens a socket to an external IP.
2. Writes to `/` and `/runner`.
3. Infinite loop.
4. Allocates 2 GB.
5. Fork bomb.
6. Reads `/proc/1/environ` and `$HOME`.
7. Tries to write into `/cand`.

**Gate 4:** all contained, plus parity: reference and mutants give identical results natively and in the sandbox. On success write `runs/GATE4_PASSED` (timestamp, image id). If it fails: **no execution of any model-generated code**; fall back to curated cached candidates a human has read line by line.

---

## 11. Candidates, pilot and headline

Owners: Koushik runs, Nehaa + Koushik first-pass classify, Nikhil final.

1. Generate **5 samples per model** for **3-4 models** (2-3 strong families + 1 small/cheap), per condition (A and B): about 30-40 candidates. Provider defaults for temperature unless set in `config/models.yaml`; always record what was used. One request per attempt; retry only on API errors (max 3); cap `max_total_api_calls` (default 120).
2. **Non-compliant candidates** (AST gate: disallowed import or call) are regenerated up to 2 extra times. Any still non-compliant are excluded from the headline denominator and reported in the pilot report.
3. Run every compliant candidate against I1-I5 on seeds 0-99 (normal), plus restart and concurrency modes once Gates 5-6 pass.
4. Each failure gets a human-reviewed class:
   - **(a)** violates a numbered rule as written (Condition A): a finding.
   - **(b)** spec was ambiguous: fix the spec, **regenerate everything**, rerun.
   - **(c)** harness or sandbox artifact: fix the harness.
   - **(d)** Condition B failure against a rule the prompt never stated: *illustrative* only.
   The overnight agent writes **proposed** classes marked `agent-proposed`; humans confirm.
5. `spec_sha` binding: a run refuses candidates whose `spec_sha` differs from the current one (marked stale).

**Never** edit a candidate or plant a bug in generated output to make it fail.

| Outcome | Action |
|---|---|
| At least one real (a) failure, reproducible | **Go.** Pick the clearest candidate for the demo hero. |
| Only (d) failures (casual prompt) | Pitch: "even good models break money rules when prompted like most developers prompt them". State that Condition A found none. |
| All pass | Make sure restart and concurrency modes ran, then rerun on the same candidates. |
| Still all pass | **No finding.** Pitch the harness: "oracle kills every hand-written mutant; 0 of N generated candidates violated the contract". Demo the kill matrix and break-it panel, labeled as hand-written mutants. |

### Headline number (only if true)

"N of M generated handlers broke at least one financial rule (I1-I4, normal + restart + concurrency; full spec, K models, 5 samples each)". M counts compliant Condition A candidates. I5-only failures are reported as "interface-only". Condition B is separate, labeled illustrative. No ranking.

### Likely real failures to watch for

R2 `True` as integer and floats; R8 rejected events consuming `event_id`; R1 signing re-serialized JSON; R9 module-level `set()`; R10 check-then-insert without a transaction; R0 crash on non-ASCII signature or huge ints.

---

## 12. Restart and concurrency (Gates 5-6)

### Restart-between-calls (R9)

Fresh child before **every** call. Run on the 20 seeds containing duplicates (families 0, 6, 7, 9, first 20). Mutant m7 must fail here and pass normal mode.

### Concurrent delivery (R10)

All processes are released together by a barrier; fresh DB per trial; 50 trials per scenario.

- **Scenario A:** 8 processes deliver the **same capture event**. Expect exactly one capture ledger entry and `captured_paise` equal to the amount.
- **Scenario B:** a capture of ₹1,000 is already applied. 4 processes deliver refund event X (₹600) and 4 deliver refund event Y (₹600), distinct `event_id`s. Expect exactly one refund applied, `refunded_paise` = 600, one refund ledger entry.
- Exceptions such as `database is locked` count as "not delivered" and are warnings. They are a violation only if they leave partial state (R7) or break the expectations above.
- **Honest limits:** a pass is probabilistic; a fail is real. Save the observed ledger as evidence; the shrinker does not apply.
- If m8 or m9 are flaky: raise processes (up to 16) and trials (up to 100). Never weaken the check. Only as a last resort, widen the race window inside the **mutant** with a 1-5 ms sleep, log it in `DECISIONS.md` and label it in the kill matrix. Never change the reference.

**Gate 5:** m7 fails restart mode and passes normal mode; reference passes restart mode.
**Gate 6:** reference passes 50/50 trials of A and B in three consecutive full runs. m8 and m9 fail within 50 trials in at least 9 of 10 repeated full runs.

---

## 13. Shrinker

Deletion-based delta debugging over the event list, with a budget and an honest minimality flag.

```python
import time
def ddmin(stream, fails, max_runs=200, max_seconds=20, on_step=None):
    """fails(stream) -> True if the SAME invariant+rule is still violated.
    Returns (stream, one_minimal)."""
    start, runs, n = time.monotonic(), 0, 2
    def test(c):
        nonlocal runs
        runs += 1
        return fails(c)
    while len(stream) >= 2:
        if runs >= max_runs or time.monotonic() - start > max_seconds:
            return stream, False
        chunk = max(1, len(stream) // n)
        parts = [stream[i:i+chunk] for i in range(0, len(stream), chunk)]
        reduced = False
        for i in range(len(parts)):
            cand = [e for j, p in enumerate(parts) if j != i for e in p]
            if cand and test(cand):
                stream, n, reduced = cand, max(n - 1, 2), True
                if on_step: on_step(stream)
                break
        if not reduced:
            if chunk == 1: return stream, True
            n = min(len(stream), n * 2)
    return stream, True
```

- `fails()` re-runs the candidate in a fresh DB, same candidate, same mode, same invariant and rule ID.
- Record every intermediate stream (`shrink_history`) so the UI can animate 40 events down to 2.
- Second pass (optional): replace amounts with small constants while the failure persists (never touch values whose type is the bug, such as bool or float).
- **Claim:** "1-minimal: removing any single remaining event removes the failure", only when `one_minimal` is true. Never "shortest possible".
- Explanation text is a template filled from the diff. No LLM.

> Example: `capture evt_1 ₹500` x2: ledger shows 2 capture entries totaling ₹1000; model expects 1 entry totaling ₹500. Rule R3.

**Gate 7:** every sequential failure shrinks to at most 4 events, and rerunning the minimal stream reproduces the same violation 10 out of 10 times. Race failures are marked `shrink: not_applicable`.

---

## 14. Repair loop

1. Send the model the failing candidate, the minimal trace, and the violated rule text. Ask for a corrected full file.
2. AST gate, sandbox, then the **full unchanged suite** (all invariants, all seeds, restart, concurrency).
3. Report per invariant, before and after. A repair that fixes one invariant and breaks another is shown as such.
4. Pre-generate and cache one successful repair for the demo, labeled `pre-run`. A stub repair (reference used as a stand-in) is for pipeline tests only, labeled `stub`, and is never cached for the demo.

---

## 15. UI (Rithvik) and API (Koushik)

CLI output is already the product. The UI only reads `runs/*.json` and calls a thin API.

### Style

Dark theme, large monospace numbers, one accent for violations (red) and one for passes (green). Skip run lists, settings and dashboards.

### Screens, in priority order

1. **Ledger + trace (the hero).** Capture ₹500, the same event fires twice, balance flips to ₹1,000 in red with a "₹ created from nothing" counter. Minimal trace timeline, expected vs observed, the arithmetic line, the rule text. Shrinker animation from `shrink_history`.
2. **Kill matrix.** Reference + m1-m9 + extras as rows, invariants as columns. Reference row all green.
3. **Before / after repair**, same suite, per-invariant.
4. **Run page.** Candidate metadata (model id, condition, sample, hash, `live` or `pre-run`), per-invariant counts, seed range, oracle and spec hashes.
5. **"Break it yourself" panel (stretch, needs API).**
6. **Race panel (stretch).** Barrier countdown, 8 processes, ledger shows 2 entries where 1 was expected. Replays saved evidence if live is flaky.

### API (thin)

- `GET /runs`, `GET /runs/{id}`, `GET /kill-matrix`: serve JSON.
- `POST /break`: `{candidate_id, scenario}` runs a fixed scenario in the sandbox and returns the verdict and ledger diff. Scenarios: `duplicate_capture`, `forged_signature`, `over_refund`, `bool_amount`, `restart_between_calls`, `rejected_redelivery`.
- `POST /repair`: `{candidate_id, failure_id}` triggers the repair loop or returns the cached `pre-run` repair.

### Fallbacks

`report/` emits one static HTML file per run (and a kill-matrix page) from the JSON: no server, no external assets. **Break-it fallback:** a static scenario replay page built from saved verdicts, so demo step 5 never depends on a live panel.

---

## 16. Demo hardening and the three-minute demo

- Everything starts with **one command** (`python cli.py demo`), with saved candidates and runs loaded offline.
- Every cached item is labeled `pre-run`. Never present a cached output as live generation. Mutants are always labeled "hand-written mutant".
- **The opening bug must come from a real pilot candidate** (label: model, condition, sample, hash). If the best real finding is Condition B, the screen says "casual prompt, illustrative". The script is written **after** the pilot; the ledger animation is generic over whichever finding is chosen.
- Do **one live generation on stage** only if the sandbox gate passed, with a pre-run backup ready.
- A recorded screen capture of the full run is the last fallback.
- Rehearse twice with the clock, on a different laptop at least once. Rehearse Q&A once.
- **Freeze features at hour 7.**

### Script (opens on the money bug; adapt step 1 to the real finding)

1. **(0:00)** "Your AI agent wrote your payment webhook. A webhook fires [twice / with a bool amount / ...]. Watch what happens to the money." Ledger screen, red. Label the candidate.
2. **(0:20)** "This is PaySift. Find the bugs before money moves. It tests the code, not the transactions."
3. **(0:35)** The contract: rules on one slide, 10 seconds.
4. **(0:50)** Run the suite with a fixed seed. One invariant goes red. Shrinker animation. "Expected X, got Y. Rule Rn."
5. **(1:25)** **Break it yourself**, or the race panel, or the static scenario replay.
6. **(1:55)** Kill matrix: "N hand-written bugs, N caught. The reference is clean." Say once that these are bugs we wrote.
7. **(2:20)** Send the trace back to the model. Same unchanged suite on the repair. Red to green.
8. **(2:50)** Headline number (only if true) and the scoped claim. No ranking.

---

## 17. Likely judge questions

| Question | Answer |
|---|---|
| Isn't Carbon Layer already doing this? | Carbon Layer tests webhook handlers for duplicates, ordering and signatures. We test generated code against a model-based financial oracle, with restart and concurrency checks, a minimal counterexample, and a repair loop. We do not claim the combination is unprecedented. |
| How do you know your oracle is correct? | It is a small state machine derived from ten numbered rules, checked by a reference handler that passes and hand-written mutants that all fail with the intended rule. Two people checked the spec independently on fresh cases. Honest limit: we wrote the mutants, so the matrix shows we catch the bugs we anticipated; extra mutants model bugs typical of LLM code. |
| Did you tune the tests so models would fail? | The spec, prompts and oracle were frozen before the final generation run. Every candidate records the spec and oracle hash. Changes after the pilot are logged and forced a full regeneration. Every Condition A failure cites a rule printed in the prompt. |
| What is the casual-prompt condition? | How developers usually prompt. Same oracle, rules not stated, results labeled illustrative, never in the headline. |
| Why not Hypothesis? | It would have worked for stateful tests and shrinking. We hand-rolled a small ddmin to control process-restart and multi-process behavior within eight hours. We do not claim shrinking is new. |
| Does this prove one model is better? | No. It shows how specific samples performed on one fixed challenge. A ranking needs more tasks, more samples and controls. |
| Can generated code escape your sandbox? | We cut the risk: no network, read-only filesystem, dropped capabilities, memory/CPU/pid limits, an import allowlist, and hostile self-tests. We do not claim arbitrary code execution is risk-free. |
| Is the contract realistic? | Modeled on common gateway webhook behavior, simplified. Not tied to any provider's schema. |
| Are concurrency results reliable? | A failure is real. A pass is probabilistic, so we report the number of trials. |
| Does it catch a crash mid-transaction? | Not directly. Atomicity is checked between calls and through ledger/payments consistency. Mid-call fault injection is future work. |
| Why SQLite? | The target is the handler's logic: dedupe, atomicity, bounds. SQLite locking is enough to expose check-then-act races between processes. |
| Is this a fraud tool like Sift? | No. It tests the code that handles payment events, not the transactions. |

---

## 18. Risk register

| Risk | Mitigation |
|---|---|
| Pilot finds no Condition A failures | Lead with Condition B (illustrative) plus the kill matrix and break-it panel. Never fake a finding. |
| Spec ambiguity creates "failures" | Classify every failure (a)-(d). Only (a) is a finding. Clarifications C1-C9 close the known ones. |
| Nikhil is overloaded | Classification split; pipeline owned by Koushik; integration only at checkpoints. |
| Single frontend (Rithvik) slips | Fixed priority order; static HTML fallback owned by Koushik. |
| Sandbox not verified | No live generation. Curated cached candidates only. |
| Concurrency flakiness | Raise processes and trials. Report trials. Save and replay evidence. |
| Docker/PowerShell differences | Docker invoked by argument list from Python; test the exact command on day one. |
| Wi-Fi or API down | Pre-run candidates and runs on disk. Static HTML report. Screen recording. |
| Event rules forbid prepared work | Rebuild from the phase prompts at the event; never present pre-built work as event work. |
| Overnight agent drifts or stalls | Phase markers, fix-attempt cap, `NEEDS_HUMAN.md`, human gates. |
| Integration chaos | One-command pipeline; checkpoints; schema frozen. |
| Name confusion with Sift | Open with "tests the code, not the transactions". |

## 19. Schedule (event day, 8 hours; adjusted so the pilot is early)

| Hours | Nikhil | Nehaa | Koushik | Rithvik |
|---|---|---|---|---|
| **0-1** | Review overnight output, Gate 1 with a second person, SPEC freeze, confirm schema | Docker/PowerShell check, sandbox image | Keys, `models.yaml`, confirm prompt files | Scaffold against `sample.json` |
| **1-2** | Oracle review, kill matrix Gate 3 | Sandbox Gate 4 | **Start candidate generation immediately after freeze** | Ledger + trace screen |
| **CP1 (h2)** | Gates 2-3 | Gate 4 | Candidates on disk | Ledger screen renders sample |
| **2-4** | Classification final review | Restart and concurrency review (Gates 5-6) | **Sequential pilot as soon as Gate 4 passes**; first-pass classification | Shrinker animation, kill matrix grid |
| **CP2 (h4)** | Know the pitch (finding vs no-finding) | | Pilot report | UI switches to real runs |
| **4-6** | Spec fixes if (b); regenerate if needed | Full-mode pilot rerun, hardening | Repair loop, API | Before/after view, race panel |
| **CP3 (h6)** | Gates 5-7 | | Pipeline selftest | Full UI on real data |
| **6-7** | Headline number, demo script (after pilot) | Hardening | Static report, break-it API | Break-it panel if time |
| **7-8** | **Feature freeze.** Rehearsals x2, screen recording | | | |

## 20. Cut line (drop in this order if behind)

1. Race panel and break-it panel polish (keep the static scenario replay).
2. Viewer polish. Ship the static HTML report.
3. Live repair. Use the pre-run repair.
4. Amount-shrinking second pass.
5. Restart-between-calls mode.
6. Scenario B (refund race). Keep Scenario A.
7. Hostile sandbox tests beyond network, filesystem, loop, fork bomb.

**Never cut:** the frozen contract, the oracle with its kill matrix, the sandbox gate, and one real reproducible failure with its minimal trace (or the honest no-finding framing).

## 21. Gates

| Gate | What | Who |
|---|---|---|
| G1 | Two people predict 10 fresh cases and agree; spec frozen | **Human** |
| G2 | Reference passes 100/100 on all invariants; repeat runs identical | Agent |
| G3 | Reference clean; m1-m6 and x1-x4 each fail with the intended rule; kill matrix printed | Agent |
| G4 | Six-plus hostile tests contained; native vs sandbox parity; `GATE4_PASSED` written | Agent |
| G5 | m7 fails restart, passes normal; reference passes restart | Agent |
| G6 | Reference 50/50 on A and B, three times; m8 and m9 caught in 9 of 10 full runs | Agent |
| G7 | Sequential failures shrink to at most 4 events, 10/10 reproducible | Agent |
| G8 | `selftest` passes end to end | Agent |

## 22. Definition of done

- [ ] SPEC.md frozen with R0-R10, C1-C9 and worked examples; G1 passed by two independent humans.
- [ ] Run JSON v1.1 frozen; `sample.json` checked in and never overwritten.
- [ ] Reference passes all invariants. m1-m9 and x1-x4 fail with the intended rules (kill matrix printed).
- [ ] Sandbox gate passed (network, filesystem, loop, fork bomb at minimum); invocation verified from PowerShell and Python.
- [ ] At least 20 compliant generated candidates run (both conditions, 3+ models including one small), each with hash, model id, condition, sample, spec hash, source label.
- [ ] Every reported failure classified by a human and cited by rule ID; Condition B results labeled illustrative; non-compliant candidates reported.
- [ ] Minimal trace for each sequential failure, 10/10 reproducible; shrink history recorded.
- [ ] Repair rerun against the unchanged suite.
- [ ] UI: ledger/trace, kill matrix, before/after (break-it and race panels if time).
- [ ] Static HTML fallback generated from run JSON; static scenario replay for the break-it step.
- [ ] One-command offline demo plus a recorded fallback.
- [ ] Pitch (opens on a real finding) and Q&A rehearsed twice with the scoped claims above.
