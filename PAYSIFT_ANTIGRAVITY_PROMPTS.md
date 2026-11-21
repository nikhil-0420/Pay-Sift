# PaySift: Antigravity Overnight Prompts (for PAYSIFT_BUILD_PLAN_v3.md)

Source of truth: `PAYSIFT_BUILD_PLAN_v3.md`. Every prompt below defers to it.
Eleven prompts, P0 to P10. Paste them into the Antigravity queue **in order**, one message each. Each prompt is self-contained.

Morning: read `MORNING_HANDOFF.md` first, then `NEEDS_HUMAN.md`.

| Prompt | Builds | Needs Docker | Gate |
|---|---|---|---|
| P0 | Rules files, skeleton, env, CLI stubs, git baseline | check only | none |
| P1 | Contract: SPEC, schema, events, cases, prompts, run schema, sample.json | no | G1 packet (human) |
| P2 | Oracle, reference handler, streams, runner (normal mode), m1-m3 | no | G2 |
| P3 | m4-m6, x1-x4, kill matrix | no | G3 |
| P4 | Sandbox, AST gate, hostile tests, parity | **yes** | G4 |
| P5 | Restart and concurrency, m7-m9 | yes (sandbox) | G5, G6 |
| P6 | Shrinker, explanations | partly | G7 |
| P7 | Model generation and intake (no execution) | no | none |
| P8 | Pilot runs, packets, report | **yes, needs G4** | none |
| P9 | Repair loop, scenarios, API, static report | yes | none |
| P10 | CLI pipeline, selftest, audit, morning handoff | yes | G8 |

---

## Pre-flight (human, before queueing anything)

**Project folder must contain, before P0:**

```
paysift/
  PAYSIFT_BUILD_PLAN_v3.md            (move the v2 file out of the folder)
  PAYSIFT_ANTIGRAVITY_PROMPTS.md      (this file)
  .env                                (API keys, git-ignored)
  .gitignore                          (at least: .env, .venv/, __pycache__/)
  config/models.yaml                  (filled in, template below)
  .git/                               (git init done, zero commits needed)
```

**1. `config/models.yaml` template** (you fill the exact model id strings; the agent must never guess ids):

```yaml
max_total_api_calls: 120
repair_reserved_calls: 10
samples_per_model_per_condition: 5
temperature: null            # null = provider default (recorded either way)
max_output_tokens: 4000
models:
  - name: strong_a
    provider: anthropic      # anthropic | openai | google | openai_compatible
    model_id: "FILL_ME"
    api_key_env: ANTHROPIC_API_KEY
    tier: strong
  - name: strong_b
    provider: openai
    model_id: "FILL_ME"
    api_key_env: OPENAI_API_KEY
    tier: strong
  - name: strong_c
    provider: google
    model_id: "FILL_ME"
    api_key_env: GEMINI_API_KEY
    tier: strong
  - name: small_a
    provider: openai_compatible
    model_id: "FILL_ME"
    api_key_env: SMALL_MODEL_API_KEY
    base_url: ""             # only for openai_compatible
    tier: small
```

**2. Block local commits mechanically** (PowerShell, from the project root):

```powershell
git init
Set-Content .git/hooks/pre-commit "#!/bin/sh`necho 'COMMITS BLOCKED TONIGHT'`nexit 1"
```

Morning: `Remove-Item .git/hooks/pre-commit`, then make your commits.

**3. Docker:** Docker Desktop running and set to start on login. `docker pull python:3.12-slim` done. Python 3.12 installed.

**4. Antigravity settings:** terminal command execution = auto/turbo (never "request approval"), review policy = always proceed. If a terminal deny list exists, add: `git commit`, `git add`, `git push`, `git stash`, `git reset`, `git checkout`, `git tag`, `git rebase`, `git merge`, `git cherry-pick`, `git revert`. (Setting names vary by version.)

**5. Machine:** plugged in, sleep and hibernate off, Wi-Fi on (model API calls), screen lock fine.

---

# P0: Bootstrap, rules, skeleton, git baseline

```text
You are the overnight backend builder for PaySift. No human is present until morning.
NEVER ask a question. NEVER wait for approval. NEVER stop early. If something blocks you,
write it to NEEDS_HUMAN.md, log your assumption in DECISIONS.md, and keep going.

Read PAYSIFT_BUILD_PLAN_v3.md fully (it is the source of truth). Then do this phase.

GOAL OF P0: create the rules files, tracking files, repo skeleton, Python environment,
CLI scaffold and a git baseline. Nothing else.

STEP 1. Write AGENT_RULES.md with exactly this content (you may format it, not weaken it):

  AGENT RULES (binding for every phase, every prompt)
  1. NEVER ask the human anything. NEVER wait. NEVER end a turn with a question.
     Blockers go to NEEDS_HUMAN.md. Assumptions go to DECISIONS.md. Then continue.
  2. NO GIT WRITES OF ANY KIND. Forbidden: commit, add, stage, rm, mv, stash, reset,
     checkout, switch, restore, branch (create/delete), tag, merge, rebase, cherry-pick,
     revert, push, pull, fetch, clone, init, config, am, apply, clean, gc, worktree,
     submodule, and any edit under .git/ (including hooks). Never use --no-verify and never
     try to bypass or remove a hook. Allowed (read-only): git status, diff, log, show,
     ls-files, rev-parse, check-ignore, stash list, branch --list, tag --list.
     The working tree stays uncommitted and unstaged. HEAD must equal the baseline in
     .agent/git_baseline.txt at the end of every phase (python cli.py check-git).
  3. UNTRUSTED CODE ONLY IN THE SANDBOX. Model-generated candidates and hostile test
     handlers run only inside Docker with --network none and the flags in plan section 10.
     Never import, exec, or run them natively. Never run any model-generated candidate
     until runs/GATE4_PASSED exists. Trusted code (ref/ and mutants/) may run natively.
  4. NO FAKED RESULTS. Never edit a generated candidate. Never plant a bug in generated
     output. Never hardcode expected outputs to pass a gate. Never weaken an oracle check,
     seed range, trial count or threshold to pass a gate. Never fabricate numbers in
     runs/*.json or reports. A gate that cannot pass after 5 honest fix attempts is marked
     FAILED in PROGRESS.md and logged in NEEDS_HUMAN.md; then move on.
  5. SECRETS. Read keys from environment variables only (load .env at runtime). Never print,
     log, write, or commit key values. Never write keys into any file or run JSON.
  6. NETWORK. The only allowed network use is calls to the model provider APIs from
     generate/ and repair/, and package installs into .venv. No other downloads, no
     curl|sh, no global installs.
  7. SCOPE. Do not create or modify ui/. Do not modify PAYSIFT_BUILD_PLAN_v3.md or
     PAYSIFT_ANTIGRAVITY_PROMPTS.md. Do not delete files you did not create. Stay inside
     the project folder. Do not add features beyond the current prompt; spare time goes to
     tests and regression checks, not scope.
  8. SPEC DISCIPLINE. contract/SPEC.md is DRAFT-FROZEN (Gate 1 pending). Do not change
     rule text after P1 unless a clear defect blocks a gate; if you do, update SPEC_HASH,
     log it in DECISIONS.md, and mark all existing candidates stale.
  9. HUMAN-ONLY GATES: G1 (two people predict fresh cases), final classification of pilot
     failures, the organizer rules check, and choosing the demo candidate. You may only
     PROPOSE these, marked "agent-proposed".
  10. FIX CAP: at most 5 honest attempts per problem. Then record and move on.
  11. PORTABILITY: Python 3.12, works on Windows PowerShell and Linux. Use pathlib, open
     files with encoding="utf-8", call subprocess with argument lists (never shell=True),
     no bash-only constructs in Python code. Give every long command a timeout.
  12. EVERY PHASE ENDS WITH: a PHASE REPORT appended to PROGRESS.md (files created, tests
     run with results, gates with status, open items), an .agent/P<n>.done marker file with
     a timestamp, and a clean python cli.py check-git. Never end with a question.
  13. RESUME CHECK at the start of every phase: read PROGRESS.md. If .agent/P<n-1>.done is
     missing, finish the missing work of that earlier phase first, and log it.
  14. HONESTY: mutants are hand-written bugs. Candidates labeled stub or mutant are never
     presented as model output. Use the source labels from the run JSON schema.

STEP 2. Create these files:
  PROGRESS.md: a table of phases P0..P10 and gates G1..G8, all "NOT STARTED", with columns
    status, started, finished, notes. G1 shows "PENDING HUMAN".
  DECISIONS.md: append-only log. Format: "[P<n>] <date-time> decision: ... reason: ...".
  NEEDS_HUMAN.md: format per item: ID (NH-001...), phase, severity (BLOCKER | IMPORTANT |
    FYI), what is needed, what you did meanwhile, how the human resolves it.
  MORNING_HANDOFF.md: placeholder line "to be written by P10".
  .agent/ directory with logs/.

STEP 3. Git baseline (read-only commands only). Record in .agent/git_baseline.txt:
  the output of git rev-parse HEAD (or the text "NO_COMMITS" if none), git status --porcelain,
  git diff --cached --name-only, git stash list, git branch --list, git tag --list,
  and a timestamp. If this is not a git repo, add NH item (BLOCKER-level FYI) and continue.

STEP 4. Create the repo skeleton exactly as in plan section 3 (directories, empty module
  files with a one-line docstring, __init__.py for Python packages). Never overwrite existing
  files. For .gitignore, append missing lines only (.env, .venv/, __pycache__/, *.pyc,
  .pytest_cache/, report/out/). Do not touch config/models.yaml if it exists; if it does not
  exist or still has FILL_ME values, write NH-001 and continue (later phases will use stubs
  labeled "stub" and the real generation step will be skipped).

STEP 5. Python environment: create .venv, requirements.txt (pytest, pyyaml, fastapi, uvicorn,
  httpx, plus nothing else unless needed; pin the installed versions), install into .venv.
  Verify Python is 3.12; log if not.

STEP 6. cli.py (argparse). Implement for real:
  check-env: Python version; docker CLI present; docker daemon reachable; image
    python:3.12-slim present; run "docker run --rm --network none python:3.12-slim python -c
    print(1)" and report; git state; which api_key_env variables are set (names only, NEVER
    values); whether models.yaml is filled. Print a table, write .agent/check_env.json, exit 0.
  check-git: compare against .agent/git_baseline.txt. Fail (exit 1) if HEAD changed, anything
    is staged, a branch/tag/stash appeared. Print what changed.
  Stub with a clear "not implemented yet (phase Pn)" message: run, kill-matrix, sandbox-test,
    pilot, shrink, repair, report, serve, demo, selftest, generate.

STEP 7. tests/test_cli.py: minimal tests for check-env output shape and check-git logic
  (use a temp git repo fixture; never touch the real repo's git state).

STEP 8. Run pytest and python cli.py check-env and check-git. Append the PHASE REPORT to
  PROGRESS.md, write .agent/P0.done. Stop. Do not ask anything.
```

---

# P1: The contract (spec, schema, events, cases, prompts, run schema, sample)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md (source of truth)
and PROGRESS.md first. Re-state to yourself the hard rules: no git writes (HEAD must stay at
.agent/git_baseline.txt), untrusted code only in the Docker sandbox, never fake results,
blockers to NEEDS_HUMAN.md, assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P0.done is missing, finish P0 first.

GOAL OF P1: build everything under contract/ plus runs/sample.json. This is the spine. A judge
reading only SPEC.md must be able to predict the oracle's verdict on any case.

1. contract/SPEC.md. Generate it from plan section 5, complete and standalone: handler
   interface, event format, harness schema, rules R0..R10, clarifications C1..C9, worked
   examples table, required fixture classes, the invariant table (I1..I5 with severity and
   headline flag), the order of checks (C3). First line of the file:
   "STATUS: DRAFT-FROZEN (Gate 1 pending)". Do not weaken or reinterpret any rule. If you find
   a contradiction or ambiguity in the plan: do NOT silently fix it. Pick the reading most
   consistent with the worked examples, log it in DECISIONS.md, and add an item under a
   "Spec questions for Gate 1" heading in NEEDS_HUMAN.md.
   Known item to record in DECISIONS.md: the plan lists R10 under I4, but concurrency
   scenario A (duplicate capture) is really an R3 property. Decision to apply: concurrency
   failures cite rule R10; scenario A is attributed to invariant I2_idempotency, scenario B to
   I4_bounds. Both count toward the financial headline. Document this in SPEC.md's invariant table.

2. contract/schema.sql: exactly the harness schema from the plan (no UNIQUE constraints).

3. contract/events.py:
   - TEST_SECRET constant.
   - canonical_bytes(event): json.dumps with sort_keys=True, separators=(",", ":"),
     ensure_ascii=False, encoded UTF-8. Same input gives same bytes.
   - sign(raw_body, secret): lowercase hex HMAC-SHA256 over the raw bytes, UTF-8 secret.
   - Body variants (all validly signed over the raw bytes): canonical, spaced separators,
     reordered keys, \u escapes, trailing newline, pretty print.
   - Signature variants: missing, empty, wrong secret, flipped byte, uppercase hex, non-ASCII,
     signed over re-serialized JSON (json.dumps(parsed) default), bad signature on an applied id.
   - Invalid bodies: non-object, invalid UTF-8, invalid JSON, each bad amount type
     (negative, 0, 5.0, "500", true, null, 10**13), missing fields, missing refund_id.
   - A step is {"raw_body_b64": ..., "signature": ..., "tag": ...}. The oracle never trusts
     the tag.

4. contract/cases.jsonl: at least 40 hand-designed cases covering every required fixture class
   in plan section 5. Each case: id, description, ordered steps (event spec + body variant +
   signature variant), and a HAND-WRITTEN expected result: per-step status and rule, and the
   final state (payments rows, ledger entry counts and sums per kind per payment). Write
   expected values as literals from reading SPEC.md. Do NOT compute them by running any
   handler or model, so the cases stay independent of the code.

5. contract/worked_examples.jsonl: every row of the worked examples table as data.

6. Gate 1 packet (humans use it in the morning):
   - contract/GATE1_PACKET.md: 10 cases chosen from cases.jsonl, shown in readable form
     (steps only, no verdicts), with a blank answer sheet for two people.
   - contract/GATE1_KEY.md: the verdicts for those 10 cases, separate file, with a note
     "predictors must not read this until they have written their answers".
   Mark G1 as "PENDING HUMAN" in PROGRESS.md.

7. contract/run_schema.json: JSON Schema for Run JSON v1.1 exactly as in plan section 5
   (including failures[].classification, severity, shrink_history, one_minimal, noncompliant,
   repair_of, harness). Add contract/validate_run.py with validate(run_dict) -> list of errors.
   Also define and document the kill-matrix JSON shape: {oracle_sha, spec_sha, created_at,
   rows:[{id, label, source, expected_rule, expected_invariant, results (per invariant and mode),
   concurrency, killed (bool), rules_hit (list), notes}]}.

8. runs/sample.json: a realistic FAKE run that validates against run_schema.json: one I2
   failure citing R3, a 40-event stream, a 2-event minimal_stream, one_minimal true, a
   shrink_history from 40 events down to 2 (list of intermediate streams), expected vs
   observed with a ledger showing 2 capture entries totaling 100000 paise vs 1 entry of
   50000, explanation text, classification {"label":"unreviewed","by":"agent-proposed"},
   candidate.source "stub", candidate.label "FAKE SAMPLE FOR UI DEVELOPMENT". Add a top-level
   "kill_matrix" key in this file only (sample convenience, documented). Also write
   runs/kill_matrix.sample.json in the kill-matrix shape (reference + m1..m9 + x1..x4, fake
   values, reference row all green). These two files are NEVER overwritten by any later phase.

9. contract/build_prompts.py (deterministic) generating contract/prompt_full.txt (full SPEC.md
   text, interface, schema, and the sentence: "single file, no explanation, allowed imports:
   sqlite3, hmac, hashlib, json, time, typing, contextlib") and contract/prompt_casual.txt
   (the casual prompt text from the plan verbatim, followed by the schema SQL and the two
   example events, no numbered rules).
   Add contract/spec_sha.py: spec_sha = sha256 over the LF-normalized bytes of SPEC.md then
   schema.sql. Write the value to contract/SPEC_HASH. Also expose prompt_hash(prompt_text).

10. tests: JSON validity of all jsonl files, at least 40 cases, hash determinism, prompt build
    determinism (two builds are byte-identical), sample.json and kill_matrix.sample.json validate
    against their schemas, case ids unique, every R0..R10 is cited by at least one case.

11. Run pytest. Append PHASE REPORT to PROGRESS.md. Write .agent/P1.done. Run check-git. Stop.
```

---

# P2: Oracle, reference handler, streams, runner, m1-m3, Gate 2

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P1.done is missing, finish P1 first.

GOAL OF P2: the oracle, a correct reference handler, seeded streams, the native runner for
TRUSTED code, mutants m1-m3, and Gate 2. Plan sections 6, 7, 8, 9 are your spec.

1. oracle/validate.py: an independent validator written from SPEC.md only. It must never import
   from ref/ or mutants/. Provide:
   - check_signature(raw, sig, secret) -> bool (lowercase hex only, ASCII only,
     hmac.compare_digest over bytes; any non-str or odd input returns False, never raises).
   - validate_payload(raw) -> (ok, event_or_None, reason). Strict UTF-8 decode, JSON object,
     R2 field rules: event_id and payment_id non-empty strings of at most 64 chars; type in the
     two allowed values; amount_paise a JSON integer from 1 to 10**12 (reject bool, reject any
     float including 5.0 and 1e3, reject string and null); refund_id required non-empty string
     for refunds; extra fields ignored. Never raises.

2. oracle/model.py: the model from plan section 7 returning (status, rule). Fix the known gap:
   record an event_id in rejected_ids on every rejection path whose body parses to an object with
   a string event_id (R1, R2, R4, R5, R6 rejections), so a later successful apply of that id is
   attributed to R8. A rejected event never enters `applied` (R8). Follow the order of checks C3.

3. oracle/checks.py: after EVERY step compare the DB snapshot to the model: payments rows, and
   per payment the ledger sum and entry count per kind. Check internal consistency (R7: payments
   agree with ledger). Compare the returned status to the model status for I5 only. Record R0
   violations (exception, wrong shape, timeout). Record the first diverging step and attribute it
   to the rule the model decided on at that step (for example a double capture entry after a
   duplicate attributes to R3; a missing apply after a prior rejection to R8; payments vs ledger
   disagreement to R7). Map to invariants per the plan section 7 table and the P1 decision for
   concurrency. A seed counts as failed for an invariant if any step violation is attributed to
   it. Build failure records in the run JSON v1.1 shape. Compute oracle_sha (sha256 over the
   oracle/*.py files, LF-normalized).

4. ref/handler_ref.py: a correct handler for the contract. Per call it opens its own sqlite3
   connection (C7), sets a busy timeout, and applies each event inside BEGIN IMMEDIATE:
   dedupe check and write in one transaction. It never raises (R0), never depends on wall-clock
   time (C8), and does not import anything from oracle/. Write it from SPEC.md.

5. runner/streams.py: seeded generator exactly as plan section 8 (random.Random(seed), family =
   seed % 10, 3 to 40 events per stream, all ten families, each step carries raw_body_b64,
   signature and tag). Use contract/events.py for bodies and signatures. Also a function that
   renders a stream as human-readable text.

6. runner/child.py and runner/worker.py (native path first; P4 wraps them in Docker):
   - Protocol: worker reads a JSON job on stdin {candidate_file, mode, sequences:[{seed, steps}]}
     and writes JSON results on stdout: per sequence, per step: the handler's return value (or
     exception text, or "timeout") and a snapshot of payments and ledger read by the WORKER's own
     connection (never the candidate's).
   - Normal mode: one fresh child process per sequence. Module-level state may persist within a
     sequence but never across sequences. Restart mode is added in P5.
   - Timeouts: 5 s per call, 30 s per sequence. On timeout kill the child and record R0 timeout.
   - Native execution is allowed ONLY for files under ref/ or mutants/. Enforce this in code
     (native_allowed(path)); any other path must raise unless running inside the sandbox flag.
   - A candidate is a single .py file; the runner stages it as handler.py in a temp directory.
   - DB in a fresh temp directory per sequence; schema from contract/schema.sql.

7. runner/run_candidate.py: for seeds 0-99 build streams, execute via the worker, run the oracle,
   aggregate into a Run JSON v1.1, validate it against contract/run_schema.json, write
   runs/<run_id>.json, print a results table. Include spec_sha and oracle_sha. Provide
   execute(candidate, job, sandbox: bool): the sandbox=True path raises NotImplementedError until P4.
   Add `python cli.py run --file <path.py> --mode normal`.

8. Mutants (trusted, hand-written, single files, each header comment says "HAND-WRITTEN MUTANT"):
   mutants/m1_no_dedupe.py (R3), mutants/m2_nonatomic.py (ledger written but payments not
   updated, R7), mutants/m3_no_bound.py (no refund bound, R6). Minimal edits of the reference
   implementing only the described bug. Create mutants/MANIFEST.json: id, file, bug, must_fail_rule,
   must_fail_invariant, modes_needed, written_blind (false for m1-m3), notes.

9. Tests: model vs every case in contract/cases.jsonl and worked_examples.jsonl (statuses and
   final state); reference handler vs the same cases; validate.py unit tests per R1/R2 class;
   stream determinism (same seed, same bytes, twice); family coverage; ddmin not needed yet.
   If the model or reference disagrees with a hand-written expectation: investigate who is wrong.
   If the case is wrong against SPEC text, fix the case and log it. If SPEC is ambiguous, log
   to NEEDS_HUMAN.md (Spec questions for Gate 1) and keep the reading most consistent with the
   worked examples. Never change an expectation just to turn a test green.

10. Gate 2: the reference passes 100/100 on all five invariants; run the reference twice and
    show the two run JSONs are identical apart from run_id and created_at; m1 fails with R3 and
    a 2-event divergence visible in the failure record; m2 fails R7; m3 fails R6. Record the
    result in PROGRESS.md. If it does not pass after 5 attempts mark G2 FAILED with details.

11. Run pytest. PHASE REPORT in PROGRESS.md. Write .agent/P2.done. Run check-git. Stop.
```

---

# P3: Remaining mutants and the kill matrix (Gate 3)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P2.done is missing, finish P2 first.

GOAL OF P3: mutants m4-m6 and extras x1-x4, the kill matrix, Gate 3. Plan section 9.

BLINDNESS RULE (honest best effort): write m4-m6 and x1-x4 from contract/SPEC.md and
ref/handler_ref.py ONLY. Do not open oracle/*.py or runner/streams.py while writing them. Make
the minimal edit that implements exactly the described bug; do not tune a mutant to what you
think the oracle detects. Record in mutants/MANIFEST.json written_blind: true plus a note
"self-attested by the agent". If you already have oracle code in your context window, say so in
the note and set written_blind to "partial".

1. Mutants (single files in mutants/, header "HAND-WRITTEN MUTANT"):
   m4_neg_amount.py: accepts negative amount (R2, I4)
   m5_reject_consumes_id.py: rejected events are marked processed, so a later valid redelivery
      is reported duplicate (R8, I2)
   m6_sig_reserialized.py: verifies the signature over json.dumps(parsed) (default separators)
      instead of the raw bytes (R1, I1)
   x1_bool_amount.py: accepts bool as amount (R2)
   x2_float_amount.py: accepts float amount including 5.0 (R2)
   x3_nonascii_sig_crash.py: non-ASCII signature crashes the handler with an exception (R0, I5)
   x4_sig_canonical_reserialized.py: verifies over json.dumps(parsed, sort_keys=True,
      separators=(",", ":")); intended to be caught ONLY by family 8 (non-canonical valid bodies)
   Update mutants/MANIFEST.json for all of them (expected rule, invariant, modes_needed).

2. `python cli.py kill-matrix`: run the reference and every available mutant in normal mode on
   seeds 0-99 (natively, they are trusted). Rows for m7-m9 appear as "pending_modes" until P5.
   Output: a printed table, runs/kill_matrix.json (shape defined in P1; include oracle_sha and
   spec_sha) and runs/kill_matrix.md. Assertions the command makes and reports:
   - the reference row is fully green;
   - every mutant's must_fail_rule appears in its rules_hit;
   - x4 is caught on family 8 seeds and NOT caught on seeds that exclude family 8 (run both and
     report; if x4 is caught elsewhere, record what that means rather than hiding it).

3. If a mutant is not killed: first check whether the mutant is faithful to its description
   (fix the mutant); then whether the streams lack coverage (extend runner/streams.py, then
   re-verify Gate 2); NEVER weaken or special-case the oracle. Log every such fix in DECISIONS.md.

4. mutants/README.md: state plainly that mutants are bugs we wrote ourselves, the kill matrix is
   partly circular (authors wrote both sides), m4-m6 were written blind to the oracle code as
   self-attested, and x1-x4 model plausible LLM bugs.

5. tests/test_kill_matrix.py: asserts the reference is clean and each mutant dies with the
   intended rule; keep it deterministic.

6. Gate 3: reference clean; m1-m6 and x1-x4 each fail with the intended rule; matrix printed and
   saved. Record in PROGRESS.md. Run pytest. PHASE REPORT. Write .agent/P3.done. check-git. Stop.
```

---

# P4: Sandbox and AST gate (Gate 4, hard gate)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P3.done is missing, finish P3 first.

GOAL OF P4: the sandbox that every model-generated candidate must run in. Plan section 10.
This phase is a HARD GATE: if it fails, no model-generated code ever executes tonight.

SAFETY FIRST: hostile handlers must NEVER be imported or executed natively. Every file under
tests/hostile/ begins with a guard that exits immediately unless it is inside a container
(check os.path.exists("/.dockerenv")), and starts with a comment "DANGEROUS: SANDBOX ONLY".
Tests that use them must skip loudly and mark G4 BLOCKED if Docker is unavailable. If Docker is
not available at all: write runs/GATE4_FAILED.md, add a BLOCKER to NEEDS_HUMAN.md, execute NO
hostile code, and end the phase.

1. runner/Dockerfile: FROM python:3.12-slim; copy runner/, contract/events.py and contract/
   schema.sql into /runner (the worker needs them); non-root user 65534; WORKDIR /tmp; no pip
   installs. Build locally as paysift-sandbox:1 (no network needed after the base image exists).

2. runner/ast_gate.py: parse with ast.parse ONLY (never exec/import the candidate). Reject
   imports outside {sqlite3, hmac, hashlib, json, time, typing, contextlib} (allow harmless
   __future__, log it), and calls to exec, eval, open, __import__, compile (also breakpoint and
   input). Return a structured result {ok, violations:[{kind, name, line}]}. Unit tests for each
   rule, including tricky forms (from X import Y, aliasing, nested functions, attribute calls).

3. runner/sandbox.py: run_in_sandbox(candidate_file, job, mode, cpus=1, timeout=...) building the
   docker run argument list from plan section 10 EXACTLY: --rm -i --network none --read-only
   --tmpfs /tmp:rw,size=64m --memory 256m --cpus <n> --pids-limit 128 --cap-drop ALL
   --security-opt no-new-privileges --user 65534, env only PYTHONDONTWRITEBYTECODE=1 and
   PYTHONHASHSEED=0. Mount the staged candidate DIRECTORY (containing handler.py) at /cand as
   read-only using --mount type=bind,source=<abs>,target=/cand,readonly (this avoids Windows
   drive-letter colon problems). Use a unique container name "paysift-<uuid>". Invoke via
   subprocess with an argument list (no shell). Job goes in on stdin, results come back on
   stdout. On any timeout: docker kill then docker rm -f by name, always in a finally block.
   Never raise to the caller: return a structured {ok, results|error}. Truncate captured stderr.
   One container per candidate per mode, running ALL sequences (the worker starts a fresh child
   process per sequence inside the container, as in plan section 6).
   Concurrency mode will use --cpus 2 (P5).

4. scripts/sandbox.ps1 and scripts/sandbox.sh: thin wrappers that call
   python -m runner.sandbox --file <path> --mode <mode>, with a header comment explaining usage.

5. Hostile handlers in tests/hostile/ (each a valid-looking handle_event file with the guard):
   h1_socket.py (opens a socket to an external IP), h2_write_root.py (writes to / and /runner),
   h3_infinite_loop.py, h4_alloc_2gb.py, h5_forkbomb.py, h6_read_proc_environ_home.py (reads
   /proc/1/environ and $HOME), h7_write_cand.py (writes into /cand).
   tests/test_sandbox_hostile.py runs each THROUGH THE SANDBOX with the AST gate bypassed on
   purpose. Expectations: each is contained and reported as an error result; the runner never
   crashes; after each test "docker ps -a --filter name=paysift-" shows no leftovers; each run
   finishes within a bounded time (about 40 s). For h6: set a canary environment variable
   PAYSIFT_CANARY=<random> on the host before the test and assert it never appears in anything
   the hostile handler could read or print. Confirm the container environment contains only
   the two allowed variables.

6. Parity test: the reference and every available mutant produce identical per-seed result
   digests natively and in the sandbox on seeds 0-19 (digest excludes timing); the reference also
   matches on all of seeds 0-99. Wire runner/run_candidate.py so sandbox=True works, add
   `--sandbox` to `python cli.py run`, and implement `python cli.py sandbox-test` (hostile
   tests plus parity).

7. Gate 4: all seven hostile handlers contained, parity holds, no leftover containers. On success
   write runs/GATE4_PASSED (timestamp, docker image id from docker image inspect, summary of the
   hostile results). On failure write runs/GATE4_FAILED.md with details, add a BLOCKER to
   NEEDS_HUMAN.md, make sure runs/GATE4_PASSED does NOT exist, and state in PROGRESS.md that
   P8 and later execution of model code is blocked.

8. Run pytest (hostile tests only if Docker works). PHASE REPORT. Write .agent/P4.done.
   check-git. Stop.
```

---

# P5: Restart mode and concurrency (Gates 5 and 6)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P4.done is missing, finish P4 first.

GOAL OF P5: restart-between-calls mode (R9), concurrent delivery (R10), mutants m7-m9,
Gates 5 and 6. Plan section 12. Trusted code (reference, mutants) may run natively; anything
else runs only in the sandbox (and only if runs/GATE4_PASSED exists).

1. Restart mode in runner/worker.py: a FRESH child process before EVERY call. Run it on 20 seeds
   with duplicates: the first 20 seeds in 0-99 whose family (seed % 10) is in {0, 6, 7, 9}.
   Results go into the run JSON under results.<invariant>.restart (counts) and failures with
   mode "restart".

2. mutants/m7_inmemory_dedupe.py: module-level set() dedupe (R9). It must PASS normal mode and
   FAIL restart mode.

3. runner/concurrency.py:
   - All processes are released together by a barrier (multiprocessing with the spawn context, or
     subprocesses released by a shared start event; your choice, log it). Fresh DB per trial with
     the schema initialized by the harness. Each delivery process calls the candidate's
     handle_event with its own connection per call.
   - Scenario A: 8 processes deliver the SAME capture event. Expect exactly one capture ledger
     entry and captured_paise equal to the amount.
   - Scenario B: a capture of 100000 paise (rupees 1,000) is already applied. 4 processes deliver
     refund event X (60000 paise) and 4 deliver refund event Y (60000 paise), distinct event_ids,
     same barrier. Expect exactly one refund applied, refunded_paise 60000, one refund entry.
   - 50 trials per scenario. Exceptions such as "database is locked" count as "not delivered" and
     are recorded as warnings; they are a violation only if they leave partial state (R7) or break
     the expectations above.
   - Save evidence: for each failing scenario, the observed ledger snapshot of the first failing
     trial goes into the run JSON (concurrency.scenario_X.evidence). The shrinker does not apply
     (failures carry shrink "not_applicable").
   - In the sandbox, concurrency runs with --cpus 2 and harness.cpus is recorded as 2.
   - Attribution (from the P1 decision): rule R10; scenario A to I2_idempotency, B to I4_bounds.

4. Mutants (hand-written, header "HAND-WRITTEN MUTANT"):
   m8_check_then_insert.py: duplicate check and insert as separate autocommit statements with no
      transaction (isolation_level=None), so concurrent deliveries can both pass the check
      (R10, scenario A).
   m9_bound_race.py: refund bound checked in a separate statement before the update (R10,
      scenario B).
   Update MANIFEST.json and the kill matrix (rows now include restart and concurrency columns;
   m7-m9 no longer pending). Keep the Run JSON valid against run_schema.json.

5. Flakiness policy (exactly this order, log each step in DECISIONS.md): if m8 or m9 are not
   reliably caught, first raise processes up to 16 and trials up to 100; only as a LAST resort,
   widen the race window INSIDE THE MUTANT with a 1-5 ms sleep, label it in the kill matrix
   ("window widened"). NEVER change the reference. NEVER weaken the check or the expectations.

6. Tests: restart mode behavior on m7 vs reference; concurrency unit tests for the scenario
   expectations using a tiny trusted handler; a quick smoke test of both scenarios on the reference.

7. Gate 5: m7 fails restart mode and passes normal mode; the reference passes restart mode.
   Gate 6: the reference passes 50/50 trials of A and B in three consecutive full runs; m8 and m9
   are each caught within 50 trials in at least 9 of 10 repeated full runs. Run these honestly
   (ten repeated full runs of each mutant; in the sandbox if Docker works, otherwise natively
   for these trusted files and say so). Record counts in PROGRESS.md. Mark FAILED after 5
   honest attempts with analysis, never by loosening the thresholds.

8. Run pytest. PHASE REPORT. Write .agent/P5.done. check-git. Stop.
```

---

# P6: Shrinker and explanations (Gate 7)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P5.done is missing, finish P5 first.

GOAL OF P6: the shrinker. Plan section 13.

1. shrink/ddmin.py: implement ddmin(stream, fails, max_runs=200, max_seconds=20, on_step=None)
   -> (stream, one_minimal) as in the plan. one_minimal is true only if the loop finished at
   chunk size 1 with no further reduction; false if the budget stopped it. on_step is called with
   every accepted intermediate stream. Keep it deterministic.

2. shrink/predicate.py: make_predicate(candidate, mode, invariant, rule, sandbox) returns
   fails(stream) that re-runs the SAME candidate in a FRESH DB, SAME mode, and returns True only
   if the SAME invariant AND rule ID are still violated. Native only for trusted candidates (ref/,
   mutants/); otherwise through the sandbox (requires runs/GATE4_PASSED). Cache predicate results
   by stream hash within one shrink to save runs.

3. Optional second pass (flag --amount-pass, default off): replace amounts with small constants
   while the failure persists. Never touch values whose TYPE is the bug (bool, float, string,
   null, negative, zero, huge). Recompute signatures when a body is rebuilt.

4. shrink/explain.py: template text, NO LLM. One template per rule R0..R10 filled from the
   expected vs observed diff, with amounts shown in rupees and paise. Example output: "capture
   evt_1 (Rs 500) delivered twice: the ledger shows 2 capture entries totaling Rs 1,000; the model
   expects 1 entry totaling Rs 500. Rule R3."

5. Integration: run_candidate automatically shrinks, for each distinct (invariant, rule), the first
   failing sequential seed. Each failure record gets minimal_stream, shrink_history (every
   intermediate stream), one_minimal, explanation, and repro {runs: 10, reproduced: N} from
   rerunning the minimal stream 10 times. Race failures get shrink "not_applicable". Minimal
   streams also carry a human-readable event summary (for the UI). Add
   `python cli.py shrink --run <run.json> --failure <index>`.

6. Tests: ddmin unit tests with synthetic predicates, including a 1-minimality property check
   (removing any single remaining event stops the failure), the budget-stop returning
   one_minimal false, determinism, and the on_step history being strictly decreasing in length.

7. Gate 7 (using trusted mutants as stand-ins; real candidates are shrunk in P8): m1, m2, m3, m4,
   m5, m6, x1, x2, x3, x4 in normal mode and m7 in restart mode. Each sequential failure must
   shrink to at most 4 events and the minimal stream must reproduce the same violation 10 out of
   10 times. Expected rough sizes: m1 two events, m5 three events. Report any that exceed 4 events
   as G7 FAILED for that mutant with an analysis; do not loosen the limit.

8. Run pytest. PHASE REPORT. Write .agent/P6.done. check-git. Stop.
```

---

# P7: Candidate generation and intake (no execution)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P6.done is missing, finish P6 first.

GOAL OF P7: generate model candidates and run intake on them. This phase NEVER executes a
candidate. ast.parse is allowed; import, exec and running are not. Plan sections 10 and 11.

1. Config: read config/models.yaml. If any model_id is FILL_ME, or its api_key_env variable is
   unset, skip that model, add an item to NEEDS_HUMAN.md (naming the variable, never a value),
   and continue with the others. If NO model is usable, build everything anyway, test with a
   fake provider, and write NH item BLOCKER "no usable model config". Never guess model ids.

2. generate/providers.py: a small provider interface with adapters for anthropic, openai, google
   and openai_compatible (base_url from config), using httpx or the stdlib (your choice, log it).
   One request per attempt. Retry only on API errors (rate limit, 5xx, network), max 3 with
   backoff. Record per attempt: model id string, provider, temperature (provider default when
   null, say so), max tokens, token usage, latency, timestamp. Keys come from environment
   variables (load .env at runtime) and must never appear in logs, exceptions, meta files or
   run JSONs; scrub them from any error text.

3. generate/generate.py: for each model x condition (A = prompt_full.txt, B = prompt_casual.txt)
   x sample (default 5) write candidates/<model>/<condition>/<sample>.py, <sample>.meta.json and
   <sample>.raw.txt. meta.json holds: model id string, provider, condition, sample number,
   attempt log, sha256 of the code, timestamp, spec_sha, prompt hash, temperature, token usage,
   compliant (bool), violations, regeneration count. Global cap max_total_api_calls (default 120;
   keep repair_reserved_calls unspent for P9). EVERY API call counts, including retries and
   regenerations. When the cap would be exceeded, stop and log. Flags: --dry-run (print the plan
   and the call count, no API calls), --limit N, --models a,b, --stale-only, --regen-all.
   --regen-all moves old candidates to candidates/_stale/<old_spec_sha>/ before regenerating.

4. generate/intake.py: extract the code from a fenced block if present, else the raw text; keep
   exactly one file; store the raw response untouched; the ONLY transformation is extraction from
   markdown fences (document exactly how). Run runner/ast_gate.py. Non-compliant candidates are
   regenerated up to 2 extra times (counted against the cap); if still non-compliant, set
   compliant false, store the violations, and exclude from the headline denominator (they are
   listed in the pilot report). NEVER edit the code to make it compliant or to make it fail.

5. spec_sha binding: add a shared function used by runner/run_candidate.py: a candidate whose
   meta.spec_sha differs from the current contract/SPEC_HASH is marked stale and refused, with a
   clear message.

6. Tests using a fake provider function (no network): fence extraction, raw fallback, cap
   enforcement, regeneration limit, meta schema, key scrubbing (put a fake key in an error string
   and assert it is removed), stale detection.

7. Real generation: after tests pass, run the real generation for all usable models, both
   conditions, 5 samples each (about 40 candidates with 4 models). Work through provider errors
   gracefully (log, continue). Print a summary table: per model per condition, how many generated,
   how many compliant, how many calls used of the cap. Write the table to
   candidates/GENERATION_SUMMARY.md.

8. Run pytest. PHASE REPORT. Write .agent/P7.done. check-git. Stop.
```

---

# P8: The pilot (requires Gate 4)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P7.done is missing, finish P7 first.

GOAL OF P8: run the pilot on the generated candidates and prepare everything the humans need to
classify the results. Plan section 11.

PRECONDITION (check first): runs/GATE4_PASSED exists AND its recorded docker image id equals the
current "docker image inspect paysift-sandbox:1" id. If not: write pilot/PILOT_REPORT.md saying
"PILOT BLOCKED: sandbox gate not passed", add a BLOCKER to NEEDS_HUMAN.md, execute NO candidate,
write .agent/P8.done, and stop.

1. Pilot runner (`python cli.py pilot`, idempotent: skip a candidate already run for the same
   spec_sha and oracle_sha unless --force): for every compliant, non-stale candidate, run in the
   SANDBOX, sequentially: normal mode on seeds 0-99; restart mode only if G5 passed; concurrency
   scenarios only if G6 passed (check PROGRESS.md). Write runs/<run_id>.json per candidate and
   validate each against the schema. A candidate that crashes or hangs the runner is recorded as
   an error and the pilot continues with the next one.

2. Shrink every distinct sequential failure (P6 machinery). Races keep evidence only.

3. Failure packets: pilot/packets/<candidate_id>__<failure_index>.md containing: model id,
   condition, sample, sha256, spec_sha, source label; the text of the violated rule from SPEC.md;
   the minimal trace in readable form; expected vs observed; the run JSON path; the candidate's
   code (whole file if 150 lines or fewer, otherwise the first 150 lines plus the path); and the
   AGENT-PROPOSED classification with a short justification. Classes (plan section 11):
   (a) violates a numbered rule as written, Condition A: a finding;
   (b) the spec was ambiguous (name the clause that is ambiguous);
   (c) harness or sandbox artifact (say why you suspect it);
   (d) Condition B failure against a rule the prompt never stated: illustrative only.
   Write each proposal into the run JSON as classification {label, by: "agent-proposed", note}.
   Humans make the final call.

4. pilot/PILOT_REPORT.md. Include: per model per condition tables (generated, compliant, passed
   all, failed, which invariants and rules); I5 interface-only failures reported separately from
   the financial invariants I1-I4; the list of non-compliant and stale candidates; Condition B in
   its own section labeled "illustrative"; NO ranking language, no "best model"; a headline draft
   computed ONLY from the data ("N of M compliant Condition A handlers broke at least one
   financial rule (I1-I4 ...)"), and if N is 0 say so plainly; a PROPOSED row from the plan's
   outcome table with the reason; up to 3 demo-candidate proposals (clearest minimal trace, rule
   printed in the prompt) marked HUMAN DECISION. State that results are provisional because the
   spec is DRAFT-FROZEN: if humans change SPEC.md the spec_sha changes, all candidates become
   stale, and the morning fix is python cli.py generate --regen-all then python cli.py pilot.

5. runs/real_example.json: a copy of the run with the clearest REAL (model-generated) failure for
   the UI developer. If there is no real failure, use the best mutant run and make the label say
   so ("hand-written mutant, not model output"). Never overwrite runs/sample.json.

6. If you conclude the oracle or harness is wrong (class c): do not edit candidates. Log evidence
   in NEEDS_HUMAN.md. You may fix a harness bug only if the TRUSTED reference reproduces the bug
   as a harness artifact; after any oracle or harness change, re-run Gates 2 and 3 and rerun
   the affected pilot runs, and log everything in DECISIONS.md.

7. Run pytest. PHASE REPORT. Write .agent/P8.done. check-git. Stop.
```

---

# P9: Repair loop, scenarios, API, static report

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P8.done is missing, finish P8 first.

GOAL OF P9: repair loop, break-it scenarios, thin API, static HTML report. Plan sections 14-16.
Do NOT create or modify ui/.

1. repair/repair.py: input = a failing candidate, its minimal trace, the violated rule text from
   SPEC.md. Ask the SAME model for a corrected full file (same constraints, same allowed
   imports). Intake with the AST gate (at most 1 regeneration). Then run the FULL UNCHANGED
   suite in the sandbox (all invariants, all seeds, restart and concurrency where those gates
   passed). Write a repair run JSON with repair_of = the original run id and a per-invariant
   before/after comparison; a repair that fixes one invariant and breaks another is shown as such.
   Cache the result in repair/cache/<candidate>__<failure>.json plus the code, labeled "pre-run".
   Use only the reserved API calls (repair_reserved_calls).
   If there is no real failure, or Gate 4 did not pass, or no usable keys: build and test the
   pipeline with a trusted mutant as the "failing candidate" and the reference as the stand-in
   repair, labeled "stub" everywhere; stubs are for pipeline tests only and are NEVER cached as the
   demo repair. Add an item to NEEDS_HUMAN.md saying a real repair must be generated.
   If a real failure exists: pre-generate ONE real repair for the clearest failure.

2. scenarios/scenarios.py: six fixed scenarios as streams with a mode and an explanation text:
   duplicate_capture, forged_signature, over_refund, bool_amount, restart_between_calls,
   rejected_redelivery. run_scenario(candidate, name) returns the oracle verdict and a ledger
   diff, executed through the sandbox (native only for trusted files). Generate
   runs/scenario_verdicts.json by running every scenario against the reference, every mutant,
   and the chosen real candidates (if any), so a static replay exists.

3. api/main.py (FastAPI, thin): GET /health, GET /runs, GET /runs/{id}, GET /kill-matrix,
   POST /break {candidate_id, scenario}, POST /repair {candidate_id, failure_id}.
   CORS for http://localhost:5173 and http://localhost:3000 (and 127.0.0.1 variants). Validate
   inputs; candidate ids and run ids must match existing records (no path traversal). Any
   non-trusted candidate runs ONLY through the sandbox and only if runs/GATE4_PASSED exists;
   otherwise return a clear JSON error. /repair returns the cached pre-run repair if it exists,
   else triggers the loop if keys exist, else a clear JSON error. Tests with TestClient.

4. report/generate.py: static HTML with no external assets (inline CSS and JS only, no CDN, no
   fonts), dark theme, large monospace numbers, red for violations and green for passes.
   Outputs in report/out/: one page per run, kill_matrix.html, scenarios.html (static scenario
   replay built from runs/scenario_verdicts.json, so the break-it demo step never needs the API),
   and index.html linking everything. Each run page shows the candidate label and a visible
   badge: live, pre-run, stub, mutant, or reference; per-invariant counts; seeds; spec_sha and
   oracle_sha; the shrink history as steps; expected vs observed; the rule text. A mutant must
   always say "hand-written mutant".

5. runs/README.md for the frontend developer: what each runs/ file is, which are fake
   (sample.json, kill_matrix.sample.json), the schema location, and how to read shrink_history.

6. `python cli.py repair`, `python cli.py report` and `python cli.py serve` (uvicorn on
   127.0.0.1:8000) work end to end.

7. Run pytest. PHASE REPORT. Write .agent/P9.done. check-git. Stop.
```

---

# P10: Pipeline, selftest, audit, morning handoff (Gate 8)

```text
You are the overnight backend builder for PaySift. No human is present. NEVER ask a question,
NEVER wait, NEVER stop early. Read AGENT_RULES.md, PAYSIFT_BUILD_PLAN_v3.md and PROGRESS.md
first. Hard rules: no git writes (HEAD stays at .agent/git_baseline.txt), untrusted code only
in the Docker sandbox, never fake results or weaken checks, blockers to NEEDS_HUMAN.md,
assumptions to DECISIONS.md, max 5 honest fix attempts per problem.
Resume check: if .agent/P9.done is missing, finish P9 first.

GOAL OF P10: the one-command pipeline, the selftest, a final audit, and the handoff the human
reads first in the morning.

1. Complete cli.py so every subcommand works with consistent exit codes and --help text:
   check-env, check-git, run, kill-matrix, sandbox-test, generate, pilot, shrink, repair,
   report, serve, demo, selftest.
   - demo: fully offline. Loads saved candidates, runs, kill matrix and scenario verdicts;
     regenerates the static report; starts the API on 127.0.0.1:8000; prints the URLs and the
     labels of what is shown. Makes NO network calls. Live execution paths require
     runs/GATE4_PASSED.
   - selftest (G8), fast by default (target under about 10 minutes): check-env; unit tests that
     do not need Docker; spec_sha consistency (contract/SPEC_HASH matches SPEC.md and schema.sql);
     kill-matrix assertions (reference clean, every mutant killed with the intended rule); if Docker
     works, a quick hostile subset plus a small parity check; shrink check on two mutants; report
     generation; schema validation of every runs/*.json; check-git. Print a PASS/FAIL table, exit
     non-zero on any FAIL. --full runs everything (all hostile tests, full parity, Gates 5-7 checks).

2. Run the full pytest suite and fix failures honestly (cap 5 attempts per problem). Run
   python cli.py selftest --full once and record the true outcome, including failures.

3. Audit:
   - Every runs/*.json validates; every run and candidate spec_sha equals the current SPEC_HASH or
     is flagged stale; oracle_sha is present everywhere.
   - Secret scan: search all project files (excluding .venv and .env) for key-looking strings and
     for the actual values of the api_key_env variables (compare in code, never print a value). If
     anything is found, remove it and add a BLOCKER to NEEDS_HUMAN.md.
   - git check-ignore .env confirms .env is ignored.
   - Final python cli.py check-git: HEAD equals the baseline, nothing staged, no new branch,
     tag or stash.

4. README_DEMO.md: how to run the one-command demo and the selftest, requirements, and what is
   cached or pre-run versus live.

5. Write MORNING_HANDOFF.md with these sections:
   1. Phase status table P0-P10 (done / partial / failed with one-line reasons).
   2. Gate table G1-G8 with status, and which are human-only.
   3. Headline draft copied from pilot/PILOT_REPORT.md (or the plain no-finding wording).
   4. NEEDS_HUMAN.md summary ordered BLOCKER, IMPORTANT, FYI.
   5. DECISIONS.md highlights (spec readings, flakiness measures, anything that changed a gate).
   6. Morning checklist, in order: delete .git/hooks/pre-commit; run python cli.py check-env;
      Gate 1 with two people using contract/GATE1_PACKET.md; if SPEC.md changes then run
      python cli.py generate --regen-all and python cli.py pilot; review failure packets and set
      final classifications; pick the demo candidate; do the organizer rules check; hand
      runs/real_example.json and runs/README.md to the frontend developer.
   7. Suggested commit grouping: a list of proposed commit messages grouped by phase, with the
      exact git add and git commit commands written out inside a fenced block headed
      "NOT RUN BY THE AGENT. For the human only." Also note which generated files the human may
      prefer to leave out of git (for example candidates/_stale/ and .agent/logs/).

6. Append the final PHASE REPORT to PROGRESS.md, write .agent/P10.done. Do not make any git
   write. Stop. Do not ask anything.
```
