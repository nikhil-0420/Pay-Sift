# PROMPTS_NIKHIL.md: stage prompts for Nikhil (You.com layer, frontend, pitch)

Repo: https://github.com/nikhil-0420/Pay-Sift (branch `main`). Companion file: `PROMPTS_NEHAA.md`. Background plans: `PAYSIFT_PLAN_v4_YOUCOM.md` (section 3 is the You.com spec), `PAYSIFT_BUILD_PLAN_v3.md` (backend contract).

**Your goal:** make You.com a visible, consequential part of PaySift (cited evidence per rule, spec-gap flags, grounded repair, live "Why is this a bug?"), ship a polished frontend wired to the real backend, and own the 3-minute pitch.

## WHO STARTS FIRST, AND WHEN NEHAA STARTS

- **You start first, with K0 (about 5 minutes).** Put `PROMPTS_NEHAA.md` and `PROMPTS_NIKHIL.md` in the repo root, ask the organizers the pre-kickoff and AI-tools question, add Nehaa, Koushik and Rithvik as collaborators, fill the K0 inputs, run K0.
- **Nehaa starts N0 only after K0's DONE report.** Send her the K0 message the moment it appears.
- After that you work in parallel. Every dependency between you is a marker file in `handoff/`; the agents check them and stop with a ready-to-send message if something is missing.
- You also need to ask Nehaa for the model API key **privately** (never in chat or files) before K3B.

## YOUR STAGES IN ORDER

| Stage | Start when | Needs from Nehaa | You hand over |
|---|---|---|---|
| K0 Access and rules | first, now | none | `K0_ACCESS_READY`: Nehaa starts N0 |
| K1 Manus build (human) | right after K0 | none | none |
| K2 You.com key (human) | while Manus runs | none | none |
| K3 Grounding layer | after K0 and K2 | none (the judge run is deferred to K3B) | `K3_GROUNDING_BUILT` |
| K3B Judge the evidence | after K3 AND her N4 message | `N4_MODELS_PUSHED` and her key, shared privately | `K3B_EVIDENCE_JUDGED` |
| K4 Review evidence | after K3B | none | `K4_GAP_LIST`: send her the gap list |
| K5 Frontend into `ui/` | after K1 and K3 | none | `K5_UI_IN_REPO` |
| K6 Evidence UI + polish | after K5, K3B, and her G1 message | `G1_RESULT`; checkpoint on `N5_INTEGRATION_OK` | `K6_UI_EVIDENCE_DONE` |
| K7 Real results in the UI | after her N7 message and K6 | `N7_PILOT_DONE` | `K7_UI_REAL_DATA` |
| K8 Evidence for the failing rule | after her N7 message (parallel with K7) | `N7_PILOT_DONE` | `K8_EVIDENCE_READY`: she runs N8 |
| K9 Pitch readiness | after her N8 message | `N8_REPAIR_DONE` | `K9_PITCH_READY`: she runs N9 |
| K10 Final push | after her N9 message | `N9_FINAL` | `K10_FINAL` |

## HUMAN-ONLY STEPS (no agent prompt)

**K1. Manus frontend build (start right after K0, runs unattended).**
1. Attach the Manus files (all in the repo): `api/main.py`, `contract/run_schema.json`, `contract/validate_run.py`, `contract/SPEC.md`, `contract/SPEC_HASH`, `runs/README.md`, `runs/real_example.json`, `runs/kill_matrix.json`, `runs/scenario_verdicts.json`, `runs/sample.json`, `runs/kill_matrix.sample.json`, `pilot/PILOT_REPORT.md`, `PROGRESS.md`, `NEEDS_HUMAN.md`, plus one each of `run_m1_*`, `run_m7_*`, `run_m8_*`. Nehaa's refreshed `manus_attachments.zip` (after her N2) is optional: `sync-data` re-syncs later.
2. Paste the Manus master prompt from your chat and save it as `MANUS_PROMPT.md` in the repo so it is not lost.

**K2. You.com key (about 10 minutes, during K1).**
1. Create a key at https://you.com/platform (new accounts include free credits). Put `YDC_API_KEY=...` in your local `.env`. Never paste it anywhere.
2. Quick test (endpoint per You.com docs; if it fails, read https://you.com/docs/openapi.json):
   `curl -X POST https://ydc-index.io/v1/search -H "X-API-Key: %YDC_API_KEY%" -H "Content-Type: application/json" -d "{\"query\":\"webhook signature verification\",\"count\":3}"`
3. K3 stops if `YDC_API_KEY` is missing from your `.env`.

**Rehearsal and recording (after K9 and N9):** run the 3-minute script twice, once online and once with Wi-Fi off, and record a backup screen video. Do the GitHub repo description and the submission yourself in K10.

**Cut line (drop in this order):** repair A/B experiment (never started), the live "Why is this a bug?" button (keep cached evidence), the spec-gaps view, extra polish on `/method`. **Never cut:** cited evidence per rule with honest labels, the real-data hero, the offline rehearsal.

## HOW THIS WORKS (read once)

1. Each **stage prompt** below is one Antigravity run. Open the stage, fill its `HUMAN INPUTS` block (if it has one), paste the whole text block into Antigravity, let it run.
2. Every run does: **preflight → work → verify → commit + push → marker → DONE report**.
3. If a run prints `=== STOPPED ===`, nothing is broken. Do what it says (wait for the other person, commit something, fix a local problem), send the **MESSAGE** it prints to whoever it names, then **paste the same stage prompt again**. It resumes at the first unfinished step.
4. `<FILL>` left in an inputs block means "I don't know yet": the agent stops instead of guessing.
5. Both files (`PROMPTS_NEHAA.md`, `PROMPTS_NIKHIL.md`) must sit in the repo root. Nikhil commits them in stage K0. The sections PROTOCOL and HANDOFF CONTRACT are identical in both files.
6. Only one agent run per working tree at a time. Do not paste a second stage while one is running.
7. Do not create or edit files in `handoff/` by hand. They are written by the stage that owns them. Consumers re-verify the real artifacts, so a hand-made marker does not unlock anything.

---

## PROTOCOL (every stage agent obeys this; stage prompts add only stage-specific rules)

### P0. Authority and overrides
- This protocol extends `AGENT_RULES.md`. It overrides exactly two things, and only for stages run from these files:
  (a) "no git writes": git writes are now allowed, but only as described in P5.
  (b) "never ask questions / never stop early": the agent still never asks questions mid-run, but it MUST stop at a preflight or checkpoint failure as described in P3.
- Everything else in `AGENT_RULES.md` stays in force: never run model-generated or hostile code natively, never fake or invent results, never weaken sandbox flags, never change `oracle/*.py`, `contract/schema.sql` or `mutants/*`, at most 5 honest attempts per problem, no secrets in output.
- Do not open `contract/GATE1_KEY.md` in any stage.
- The host may be Windows (PowerShell or cmd). Do not assume bash. Use the host's shell syntax and `python -m` forms.

### P1. Ownership (who may edit what)

| Area | Owner |
|---|---|
| `runner/` (sandbox*, Dockerfile, worker.py, child.py, sandbox_test.py), `scripts/` (except the selftest hook below), `tests/hostile/`, tests she adds for her own areas | Nehaa |
| `config/models.yaml`, `candidates/`, `pilot/`, `runs/` (all run outputs except `runs/grounding.json`), `repair/cache/` | Nehaa |
| `contract/SPEC.md`, `contract/SPEC_HASH`, `contract/GATE1_*` (only through stage N3) | Nehaa |
| `MORNING_HANDOFF.md`, `README_DEMO.md`, `docs/API_*`, `docs/NAMING.md`, `manus_attachments*`, `runs/README.md` | Nehaa |
| `grounding/`, `api/evidence.py`, `runs/grounding.json`, `contract/grounding_schema.json`, `docs/YOUCOM_NOTES.md`, `docs/SPEC_GAP_LIST.md`, `docs/EVIDENCE_REVIEW.md`, `docs/ORGANIZER_RULES.md` | Nikhil |
| `repair/prompt.py`, `repair/repair.py` (grounding additions only), `ui/`, `MANUS_PROMPT.md`, `README.md` | Nikhil |
| `AGENT_RULES.md`, `PROMPTS_*.md`, `handoff/README.md`, `.gitignore` | Nikhil (stage K0 only) |
| `handoff/<MARKER>` | only the owner named in the HANDOFF CONTRACT |
| **Shared hot files**: `api/main.py`, `cli.py`, `scripts/selftest.py`, `generate/providers.py` (secret scrubber function only), `contract/run_schema.json` (Nikhil: additive optional fields only), `PROGRESS.md`, `NEEDS_HUMAN.md`, `DECISIONS.md` | both, under the P8 rules |

Never touched by any stage unless the stage text says so: `oracle/*.py`, `contract/schema.sql`, `mutants/*`, and the contents of existing `runs/*.json` (single exception: stage N7 FINALIZE sets the classification field).

An agent never edits a file owned by the other person. If a fix is needed there, STOP and write a MESSAGE asking the owner.

### P2. Preflight (always, in this order, before any work)
Each stage lists `REQUIRES-OTHER` (markers owned by the other person) and `REQUIRES-OWN` (markers owned by you). Do all of this:

1. **Lock.** If `.agent/RUNNING.lock` exists and is less than 3 hours old: STOP (another stage is running in this folder; Blocked by: Me). If it is older: STOP and tell the human to delete it only if no agent is running. Otherwise create it with the stage id and UTC time. Remove it on every exit (DONE or STOPPED).
2. **Remote.** `git fetch origin`. If it fails (no access, no network): STOP, Blocked by: Me. For stage N0 this usually means K0 is not done: use the K0 message.
3. **Branch.** Must be `main`. Otherwise STOP.
4. **Working tree.** Run `git status --porcelain`.
   - Changes outside this stage's allowed paths, or inside the other person's area: STOP and list them. Never touch, stash, reset or commit them.
   - Uncommitted changes inside your own area from an earlier stage: this is "should commit". Run that earlier stage's checks if known (otherwise `pytest -q`), scan for secrets (P5), and commit them with message `chore(<stage>): commit leftover work` using explicit paths. If checks fail, STOP and list the files.
5. **Sync.** Compare with `origin/main`.
   - Ahead (unpushed local commits): `git pull --rebase origin main`, then `git push origin main` now.
   - Behind: `git pull --rebase origin main`.
   - Rebase conflict: apply P5 conflict rules.
6. **Dependencies.** For every marker in `REQUIRES-OTHER` and `REQUIRES-OWN`:
   - The marker file `handoff/<MARKER>` must exist on `origin/main` (`git show origin/main:handoff/<MARKER>`), with `status: DONE` (or `SKIPPED` where the contract allows it).
   - Run the marker's VERIFY checks from the HANDOFF CONTRACT on the working tree. Marker present but VERIFY fails = STOP, "marker exists but artifact is missing or invalid", Blocked by: the marker's owner.
   - Spec-bound markers (marked "spec-bound" in the contract): the marker's `spec_sha` must equal the current `contract/SPEC_HASH`. If not, STOP, "stale after spec change", Blocked by: the marker's owner.
   - Marker missing: STOP, Blocked by: the marker's owner.
7. **Secrets and env.** `.env` must be git-ignored and untracked. Required env var names (listed in the stage) must exist with non-empty values. Check names only; never print values.
8. **Progress file.** Create or append `.agent/progress_<stage>.md` with the start time and the step list. On resume, read it and skip steps whose "done when" check already passes.

### P3. STOP protocol (the only allowed way to stop early)
Stop when: preflight fails, a CHECKPOINT fails, a `<FILL>` input is missing, a human decision is needed, or 5 honest attempts fail. Never continue past a STOP. Never build, fake or bypass the other person's part (for example: never invent model ids, never create a marker for someone else, never write grounding data by hand).

On STOP:
1. If completed owned work exists and the tests for it pass, commit it as `wip(<stage>): <what exists>` and push. No marker. If tests fail, leave it uncommitted and list the files.
2. Write `.agent/STOPPED_<stage>.md` and print exactly this as the final output:

    === STOPPED: <stage> ===
    Reason: <one line>
    Blocked by: <Nikhil | Nehaa | Me | External>
    Missing or wrong: <exact marker, file, commit or command result>
    What to do now:
      1. <exact step or command for the human>
      2. ...
    Resume: paste stage <stage> again. It will resume at step <n>.
    MESSAGE TO SEND (copy-paste), to <person>:
    > <2 to 6 plain lines: what you need, why, which marker or file, which commands, what happens next>

   If Blocked by is "Me", the MESSAGE line may say "none needed".
3. Remove `.agent/RUNNING.lock`.

A CHECKPOINT is a mid-stage copy of the dependency check. At a checkpoint, run `git fetch origin`, re-verify the named marker as in P2.6, and STOP with the format above if it fails.

### P4. Resume
Every step has a "done when" check. Before doing a step, check it; if it already holds, skip it. A re-run must never duplicate work, duplicate commits or overwrite human edits.

### P5. Git rules (agents may commit and push)
Allowed: `git fetch`, `git status`, `git log`, `git diff`, `git show`, `git pull --rebase origin main`, `git add <explicit paths>`, `git commit`, `git push origin main`, `git rebase --abort`.
Forbidden: force push or `--force-with-lease`, `git reset --hard`, `git clean`, `git checkout` or `git restore` on files you do not own, `git stash`, amend or rewrite pushed commits, `--no-verify`, branch create/delete, `git add -A` or `git add .`, committing `.env`, `.agent/`, `node_modules/`, build output or `report/out/`.

**End-of-stage procedure (every stage that changes files):**
1. Run the stage's VERIFY commands. Do not commit a failing state (except `wip` under P3).
2. Secret scan: read the values from `.env` (do not print them) and confirm none appears in `git diff --cached`, and no common key prefix pattern appears. Also run the repo's own secret scan if one exists. Any hit: STOP, Blocked by: Me, and never print the match.
3. `git pull --rebase origin main`.
4. `git add` only the stage's explicit paths. Commit messages: `<type>(<scope>): <summary>` with a final line `Stage: <ID>`. Make one commit per logical task when the stage text says so.
5. Write the marker file (P6) and commit it alone as `handoff(<ID>): <summary>`.
6. `git push origin main`. If rejected: `git pull --rebase origin main`, push again, at most twice, then STOP.
7. `git fetch origin`, confirm `git status -sb` shows in sync and `git log origin/main -1` is your marker commit (or later).
8. Print the DONE report (P7) and remove the lock.

**Conflict rules.** On a rebase conflict: if every conflicting file is an append-only doc (`PROGRESS.md`, `NEEDS_HUMAN.md`, `DECISIONS.md`), keep both sides in order and continue. Anything else: `git rebase --abort`, STOP, list the files and their owners. If a pre-commit hook blocks a commit, STOP and report the hook output; never bypass it.

### P6. Marker file format
Path `handoff/<MARKER>` (no extension), plain text:

    stage: <ID>
    owner: <nehaa|nikhil>
    status: <DONE|SKIPPED|BLOCKED>
    completed_at: <UTC ISO-8601>
    work_commit: <sha of the last work commit>
    spec_sha: <current contents of contract/SPEC_HASH>
    summary: <one line>
    <stage-specific key: value lines, as listed in the contract>

Never put secret values in a marker. Env var names are fine.

### P7. DONE report (final output on success)

    === DONE: <stage> ===
    Marker: handoff/<MARKER> pushed to origin/main (commit <sha>)
    What changed: <3 to 6 lines, real numbers from the run>
    Warnings: <anything skipped or noisy, or "none">
    Next for you: <the next stage id and when to start it>
    MESSAGE TO <person> (send now): <the text from the stage's NOTIFY>
      (or "No message needed.")

### P8. Shared hot files
Before editing a shared hot file run `git fetch origin` and `git pull --rebase origin main`. Make the smallest additive edit. Commit it on its own and push in the same phase. `PROGRESS.md`, `NEEDS_HUMAN.md` and `DECISIONS.md` are append-only: add a dated section for your stage, never rewrite the other person's sections, never delete any BH item.

### P9. Honesty and secrets
A hand-written mutant is never presented as model output. No model rankings. "Supported by sources" never means "spec verified". Status words must match reality: if something never ran, mark it PARTIAL or SKIPPED. Keys live only in the local `.env`; never print, log, commit or put them in a message.

---

## HANDOFF CONTRACT (identical in both files)

"Notify" = the stage's DONE report must include a MESSAGE to that person. "Spec-bound" = the marker must carry the current `spec_sha`.

| Marker | Owner | Written by | Required by | VERIFY (consumer runs these) | Spec-bound | Notify |
|---|---|---|---|---|---|---|
| `K0_ACCESS_READY` | Nikhil | K0 | N0, K3 | `docs/ORGANIZER_RULES.md` exists and its decision is not NOT_ALLOWED; `PROMPTS_NEHAA.md`, `PROMPTS_NIKHIL.md`, `handoff/README.md` exist | no | Nehaa (and Koushik, Rithvik): clone and start N0 |
| `N0_SETUP_OK` | Nehaa | N0 | N4, N1 | marker lists python version and pytest result | no | none |
| `N4_MODELS_PUSHED` | Nehaa | N4 | K3B, N6 | `config/models.yaml` has no `FILL_ME`; marker has `judge_model`, `env_var_names`, `planned_generation_calls` | no | Nikhil: judge model and env var name |
| `N1_GATE4_PASSED` | Nehaa | N1 | N2, N6, N7 | `runs/GATE4_PASSED` exists | no | Nikhil (info) |
| `N2_FIXES_DONE` | Nehaa | N2 | N5 | `docs/NAMING.md`, `docs/API_CONTRACT.md`, `docs/API_EXAMPLES.json`, `manus_attachments.zip` exist | no | none |
| `G1_RESULT` | Nehaa | N3 | N5, N6, K6 | marker has `outcome`, `spec_changed`, `regen_required`; `spec_sha` equals `contract/SPEC_HASH` | yes | Nikhil: spec changed or not |
| `N5_INTEGRATION_OK` | Nehaa | N5 | N6, K6 (checkpoint) | marker records pytest and selftest results and `k3_merged` | yes | Nikhil: API contract final, resync UI |
| `N6_CANDIDATES_PUSHED` | Nehaa | N6 | N7 | `candidates/GENERATION_SUMMARY.md` exists | yes | Nikhil (info) |
| `N7_PILOT_RAN` | Nehaa | N7 (RUN) | N7 (FINALIZE) | `pilot/PILOT_REPORT.md` exists | yes | Nikhil: review packets together |
| `N7_PILOT_DONE` | Nehaa | N7 (FINALIZE) | N8, K7, K8, K9 | marker has `decision` (FINDING or NO_FINDING); if FINDING also `demo_candidate`, `failing_rule`, `classification`; the candidate's run JSON exists in `runs/` | yes | Nikhil: run K7 and K8 |
| `N8_REPAIR_DONE` | Nehaa | N8 | K9, N9 | status DONE or SKIPPED; if DONE the repair file named in the marker exists under `repair/cache/`; marker has `fixed_rule`, `broke_other`, `grounding_used` | yes | Nikhil: run K9 |
| `N9_FINAL` | Nehaa | N9 | K10 | marker records pytest and selftest results; nothing unpushed | yes | Nikhil: run K10 |
| `K3_GROUNDING_BUILT` | Nikhil | K3 | K3B, K4, K6, N8 | `grounding/`, `api/evidence.py`, `contract/grounding_schema.json` exist; `repair/prompt.py` has a Sources section; `python cli.py ground --help` runs | no | Nehaa: pull, `ground` commands exist |
| `K3B_EVIDENCE_JUDGED` | Nikhil | K3B | K4, K6, K8 | `runs/grounding.json` validates against the schema; its `spec_sha` equals `contract/SPEC_HASH`; no rule is NOT_JUDGED | yes | Nehaa (info) |
| `K4_GAP_LIST` | Nikhil | K4 | none (optional input to N3, N5) | `docs/SPEC_GAP_LIST.md` exists | yes | Nehaa: gap list as second-pass input |
| `K5_UI_IN_REPO` | Nikhil | K5 | K6 | `ui/package.json` exists; marker records `check:contract` result | no | none |
| `K6_UI_EVIDENCE_DONE` | Nikhil | K6 | K7 | marker records `npm run verify` result | yes | none |
| `K7_UI_REAL_DATA` | Nikhil | K7 | K9 | marker records the hero-copy check | yes | none |
| `K8_EVIDENCE_READY` | Nikhil | K8 | N8 | status DONE or SKIPPED; if DONE, `failing_rule` equals the one in `N7_PILOT_DONE` and its entry in `runs/grounding.json` has sources or `convention: true` | yes | Nehaa: run N8 |
| `K9_PITCH_READY` | Nikhil | K9 | N9, K10 | `docs/PITCH_READINESS.md` exists | yes | Nehaa: rehearsal time, run N9 |
| `K10_FINAL` | Nikhil | K10 | none | README updated, everything pushed | yes | team |
---

## STAGE PROMPTS

Common first lines of every stage (already written into each block): read `AGENT_RULES.md`, then the PROTOCOL and HANDOFF CONTRACT sections of this file, and obey them.

### K0. Access, rules, and the coordination scaffold

```text
STAGE K0 - Access, organizer rules, coordination scaffold. Owner: Nikhil. You are the setup agent for Nikhil on PaySift (repo root = current folder).
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them (they override "no git writes" and "never stop" only as written there). Run the PROTOCOL preflight, then the steps below. This is the one stage allowed to edit AGENT_RULES.md, .gitignore and handoff/README.md.

HUMAN INPUTS (fill before pasting; any <FILL> left makes you STOP, Blocked by: Me):
ORGANIZER_ANSWER: <FILL: ALLOWED | ALLOWED_WITH_CONDITIONS: <text> | NOT_ALLOWED>
ORGANIZER_ANSWER_SOURCE: <FILL: who said it, when, where>
COLLABORATORS_ADDED: <FILL: yes | no>   (Nehaa, Koushik, Rithvik, via GitHub Settings > Collaborators; you cannot verify this, so the input is the record)
(Before pasting: copy PROMPTS_NEHAA.md and PROMPTS_NIKHIL.md into the repo root.)

REQUIRES-OTHER: none
REQUIRES-OWN: none
ALLOWED WRITES: docs/ORGANIZER_RULES.md, AGENT_RULES.md, .gitignore, handoff/README.md, PROMPTS_NEHAA.md and PROMPTS_NIKHIL.md (commit exactly as provided, never edit them), MANUS_PROMPT.md (only if it already exists), handoff/K0_ACCESS_READY

STEPS
1. Confirm PROMPTS_NEHAA.md and PROMPTS_NIKHIL.md exist in the repo root. Missing: STOP, Blocked by: Me ("copy both files into the repo root").
2. Confirm COLLABORATORS_ADDED is yes. If no: STOP, Blocked by: Me.
3. Write docs/ORGANIZER_RULES.md: the answer (decision: ALLOWED, ALLOWED_WITH_CONDITIONS or NOT_ALLOWED), the verbatim conditions if any, the source and date. Keep the line "decision: <value>" machine-readable.
4. AGENT_RULES.md: append a section "Git permissions and stop protocol". Say: stages run from PROMPTS_NEHAA.md and PROMPTS_NIKHIL.md may commit and push under the PROTOCOL section P5 and must stop under P3; the old "no git writes" rule is superseded for those stages only; all other rules unchanged. Do not delete or reword existing rules.
5. .gitignore: make sure it contains .env, .agent/, node_modules/ and report/out/ (add only what is missing).
6. Create handoff/README.md: three short paragraphs: what the marker files are, that only the owning stage writes them, and that consumers re-verify artifacts instead of trusting markers.
7. If decision is NOT_ALLOWED: still commit steps 3 to 6, write the marker with status: BLOCKED, push, and STOP with a message to the whole team: "Organizers say pre-built work or AI-written code is not allowed (<verbatim>). Do not start any stage. We need to decide how to proceed." Otherwise continue.

VERIFY: all files exist; decision line present; .gitignore entries present; git status clean after the commit.
COMMIT: chore(coordination): organizer rules, agent git protocol, handoff scaffold (explicit paths only).
MARKER K0_ACCESS_READY extra lines: organizer_decision, conditions (verbatim or none).
NOTIFY (to Nehaa, and Koushik and Rithvik): "K0 is done. You are added to https://github.com/nikhil-0420/Pay-Sift. Organizer answer: <decision><, conditions if any>. Clone the repo, open PROMPTS_NEHAA.md and start with stage N0. While waiting you can already install Docker Desktop and check python --version (3.12 target)."
```

### K3. You.com grounding layer (judge run deferred to K3B)

```text
STAGE K3 - You.com grounding layer. Owner: Nikhil. You are the integration agent for PaySift's You.com layer.
FIRST read AGENT_RULES.md and PAYSIFT_PLAN_v4_YOUCOM.md (section 3 is your spec), then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps below.
Rules: never run model-generated candidates; do not change oracle/*.py, contract/SPEC.md, contract/schema.sql, mutants/*, or the contents of any existing runs/*.json; changes to contract/run_schema.json are additive only and every existing run must still validate with 0 errors; max 5 honest attempts per problem. Do not touch ui/, runner/, candidates/ or pilot/.
AUTHORIZED for this stage: network calls to https://you.com/docs/... (reading docs) and to the You.com API using YDC_API_KEY from the environment or .env. Never print, log or write the key anywhere.

REQUIRES-OTHER: none (the model-judge RUN is K3B; here the judge is code plus tests only)
REQUIRES-OWN: K0_ACCESS_READY
REQUIRED ENV NAMES: YDC_API_KEY
ALLOWED WRITES: grounding/, api/evidence.py, runs/grounding.json, contract/grounding_schema.json (new), contract/run_schema.json (additive), docs/YOUCOM_NOTES.md, repair/prompt.py and repair/repair.py (grounding additions only), tests/ (new tests for the above), PROGRESS.md and NEEDS_HUMAN.md (append-only), handoff/K3_GROUNDING_BUILT
Shared hot files you will touch, each in its OWN small commit after a fresh git pull --rebase origin main (P8): api/main.py (exactly one include line), cli.py (the ground subcommand), scripts/selftest.py (one new check), generate/providers.py (the secret scrubber only).

Y1. READ THE DOCS. Fetch https://you.com/docs/openapi.json and https://you.com/docs/guides/search.md. Write docs/YOUCOM_NOTES.md: endpoint(s), method, auth header, request fields, the response fields you actually use, limits and error codes, and every difference from the plan. The OpenAPI spec wins over the plan. Verify: POST https://ydc-index.io/v1/search with X-API-Key and body {query, count}; GET https://api.you.com/v1/search; the keyless route https://api.you.com/v1/agents/search (limits unverified; explicit fallback only).
Y2. grounding/queries.yaml. Read rule ids and titles from contract/SPEC.md (R0-R10; never invent rule text). 2-3 deterministic queries per rule. Use site: operators for official provider docs (stripe.com/docs, razorpay.com/docs) for rules those docs plausibly cover (signature verification over the raw body, idempotency and duplicate events, refund limits, amount validation). Broader queries for rules docs rarely cover (rejected events not consuming ids, restart durability, concurrent delivery). Human-reviewable. Store a hash of each rule's text next to its queries so a later spec change can be detected per rule.
Y3. grounding/youcom.py: client with X-API-Key from env, 10 s timeout, at most 2 retries on 429/5xx with backoff, a global call cap (default 60, configurable), an explicit opt-in flag for the keyless fallback, error text scrubbed of the key. Extend the existing secret scrubber (generate/providers.py scrub_secrets or equivalent) so YDC_API_KEY is also removed from logs and exceptions.
Y4. Fetch and cache. grounding/fetch.py plus python cli.py ground --fetch [--rules R1,R3] [--refresh]. For each rule and query store the RAW API response and the parsed sources in grounding/cache/<rule>.json: {id, url, title, snippet, rank, query, retrieved_at, provider: "you.com"}. Short snippets only, no full page text. Skip rules already cached unless --refresh. Respect the call cap.
Y5. Judge CODE. grounding/judge.py plus python cli.py ground --judge [--rules ...]. It uses a model from config/models.yaml through the existing provider adapters, sends the rule text and the retrieved snippets, and demands strict JSON {label: SUPPORTED|PARTIAL|NOT_FOUND|CONFLICT, sources_used: [ids], quote, reason}. Enforce in code: quote is a verbatim substring of a retrieved snippet and at most 25 words; every sources_used id exists; otherwise downgrade to NOT_FOUND. Record model id, temperature and token usage. Rules with NOT_FOUND or no sources get convention=true. Support grounding/overrides.yaml (a human sets label/note per rule; shown as human_reviewed=true) and an offline rebuild that applies overrides and cache to runs/grounding.json WITHOUT calling any model. In THIS stage do NOT call a real model: test only with a fake model client. If config/models.yaml still has FILL_ME, that is expected here.
Y6. runs/grounding.json plus contract/grounding_schema.json and a validator. Shape: {generated_at, spec_sha, provider: "you.com", rules: {R1: {label, convention, human_reviewed, sources: [...], quote, reason, judge: {model, temperature}}}}. In this stage write it from the fetched cache with every label "NOT_JUDGED" and convention=true only for rules with no sources. Assert that every source url appears in the stored raw response for that rule; fail the build otherwise.
Y7. Additive schema work. Add an OPTIONAL failures[].evidence_refs (list of source ids) to contract/run_schema.json. Do not modify existing run files (the UI joins evidence by rule id). Re-validate every runs/*.json: 0 errors. Do not change spec_sha or oracle_sha.
Y8. API. Create api/evidence.py as an APIRouter. Endpoints: GET /evidence, GET /evidence/{rule_id} (validate ^R(10|[0-9])$), POST /evidence/search {rule_id, extra_terms?} (live search from the rule's template query plus optional extra terms, max 80 chars, sanitized; rate limit 10 per minute; per-process cap; writes to the cache; clear JSON error with no key or API down). Tests with FastAPI TestClient and a fake You.com client (no network), including bad rule ids and the CORS preflight from http://localhost:5173. Then add the single include line to api/main.py (shared file, own commit).
Y9. Grounded repair. In repair/prompt.py add an optional "Sources" section built from runs/grounding.json for the violated rule (title, url, short snippet). In repair/repair.py record an additive field grounding: {used: bool, source_ids: [...]} on the repair run JSON and include it additively in the POST /repair response. Behavior unchanged when no grounding exists. Tests.
Y10. Tests and checks. Unit tests with a fake client: query building, cache read/write, call cap, key scrubbing, retries, judge substring check, 25-word cap, unknown source id, malformed JSON, per-rule text-hash change detection. Add a "grounding.json valid" check to scripts/selftest.py (SKIP with a reason if the file is absent; shared file, own commit).
Y11. Real fetch. With YDC_API_KEY set: python cli.py ground --fetch (cap 60 calls total). Then rebuild runs/grounding.json. Leave labels NOT_JUDGED. Do not run --judge here.
Y12. Finish. Run pytest and python cli.py selftest. Append a "You.com layer" report to PROGRESS.md (commands, files, honesty rules, calls used).

VERIFY: pytest -q green; selftest passes (grounding check included); all runs/*.json validate with 0 errors; runs/grounding.json validates and every displayed URL traces to a stored raw response; python cli.py ground --help works.
COMMIT: separate commits: feat(grounding): client, fetch, cache, judge code; feat(api): evidence routes (include line in its own commit); feat(repair): grounded prompt; chore(security): scrubber covers YDC_API_KEY; test(selftest): grounding check; docs(youcom): notes and progress.
MARKER K3_GROUNDING_BUILT extra lines: rules_fetched, you_calls_used, judged: false.
NOTIFY (to Nehaa): "Grounding layer is pushed. Pull before you touch api/main.py (it now has one include line for the evidence router) or scripts/selftest.py. New commands: python cli.py ground --fetch and --judge (the judge run waits for your models.yaml). Repair prompts can now include cited sources. Nothing else needed from you right now."
```

### K3B. Judge the evidence (needs Nehaa's models.yaml and a key)

```text
STAGE K3B - Judge the evidence. Owner: Nikhil. You are the evidence judge runner for PaySift. Labels are LLM-assigned and stay marked unreviewed until a human overrides them in K4.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: N4_MODELS_PUSHED
REQUIRES-OWN: K3_GROUNDING_BUILT
REQUIRED ENV NAMES: YDC_API_KEY, and the api_key_env of the judge model named in the N4_MODELS_PUSHED marker (look it up in config/models.yaml; names only, never print values)
If the judge model's key is missing from .env: STOP, Blocked by: Nehaa, with the MESSAGE: "Please send me the <ENV VAR NAME> key privately (not in chat history or files) so I can run the evidence judge. Model: <judge_model>."
ALLOWED WRITES: grounding/cache/, runs/grounding.json, docs/YOUCOM_NOTES.md, PROGRESS.md, handoff/K3B_EVIDENCE_JUDGED

STEPS
1. Spec check: compare spec_sha in runs/grounding.json with contract/SPEC_HASH. If they differ (G1 changed the spec): use the stored per-rule text hashes to find rules whose text changed and run python cli.py ground --fetch --rules <those> --refresh. If no per-rule hash exists, refresh all rules. Check the remaining You.com call budget (cap 60 in total) first; if it will not fit, STOP, Blocked by: Me, with the numbers.
2. Check the model budget: 11 judge calls must fit within the remaining max_total_api_calls. If not, STOP, Blocked by: Nehaa, asking her to raise the cap or free calls.
3. Run python cli.py ground --judge. Hard checks stay in code: quote is a verbatim substring of a retrieved snippet and at most 25 words, every sources_used id exists, otherwise NOT_FOUND. Do not hand-edit labels; do not touch grounding/overrides.yaml in this stage.
4. Validate runs/grounding.json against contract/grounding_schema.json. No rule may remain NOT_JUDGED. Its spec_sha must equal contract/SPEC_HASH.
5. Print the label distribution (SUPPORTED, PARTIAL, NOT_FOUND, CONFLICT). Do not smooth a bad result: "docs are silent on most rules" is a valid, honest outcome.
6. Append a short "Evidence judged" note to PROGRESS.md.

VERIFY: grounding.json valid; no NOT_JUDGED; spec_sha matches; pytest -q still green.
COMMIT: feat(grounding): judged evidence (grounding/cache and runs/grounding.json).
MARKER K3B_EVIDENCE_JUDGED extra lines: judge_model, label_counts, you_calls_used_total, model_calls_used.
NOTIFY (to Nehaa, info): "Evidence is judged and pushed: <label counts>. Nothing needed from you. Next I review the labels by hand and send you the list of rules where public docs are silent or disagree, as an optional second pass for the spec."
```

### K4. Review the evidence by hand (two modes: REVIEW, then APPLY)

```text
STAGE K4 - Evidence review. Owner: Nikhil. You are the evidence review assistant for PaySift. A human decides every override; you prepare the sheet and apply the decisions exactly.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps for the chosen mode.

HUMAN INPUTS (fill before pasting; any <FILL> left makes you STOP, Blocked by: Me):
REVIEW_STATUS: <FILL: NOT_DONE | DONE>
OVERRIDES (only when DONE; one per line, or NONE):
  <FILL: R3: label=SUPPORTED|PARTIAL|NOT_FOUND|CONFLICT note=<one line> | NONE>

REQUIRES-OTHER: none
REQUIRES-OWN: K3B_EVIDENCE_JUDGED
ALLOWED WRITES: docs/EVIDENCE_REVIEW.md, grounding/overrides.yaml, runs/grounding.json (offline rebuild only), docs/SPEC_GAP_LIST.md, PROGRESS.md, handoff/K4_GAP_LIST

MODE NOT_DONE
1. Write docs/EVIDENCE_REVIEW.md: for each rule R0-R10 the label, convention flag, judge model, reason and quote; for each source the title, domain, URL, retrieved date and snippet; a re-run of the substring and 25-word check; flags for sources whose domain is not an official provider docs site; a checkbox "reviewed" per rule.
2. Commit and push the sheet (docs only, no marker). STOP with a human-review stop (Blocked by: Me): "Open every source link, check the source is real and relevant and the label is fair, then fill REVIEW_STATUS: DONE and OVERRIDES and run K4 again." MESSAGE: none needed.

MODE APPLY
1. Validate every override: rule id exists, label is one of the four, a note is present. Write grounding/overrides.yaml exactly from the input (human_reviewed will show in the UI). Never override a rule you were not told to.
2. Rebuild runs/grounding.json offline (cache + stored judge outputs + overrides). Do NOT call the judge model or You.com again just to apply overrides. If the CLI has no such step, add an offline --rebuild option in grounding/ with a test.
3. Write docs/SPEC_GAP_LIST.md: every rule labeled PARTIAL, NOT_FOUND or CONFLICT (after overrides) with one line "question for review". Wording rule: these are questions for the spec review, never statements that the spec is wrong. Rules with no support are "PaySift convention".
4. Validate grounding.json again; spec_sha unchanged.

VERIFY: grounding.json valid after the rebuild; overrides match the input; gap list matches the labels.
COMMIT: docs(evidence): review sheet (NOT_DONE) or feat(grounding): human overrides and spec gap list (APPLY).
MARKER K4_GAP_LIST (APPLY only) extra lines: overrides_applied, gap_rules (ids).
NOTIFY (APPLY, to Nehaa): "Evidence review is done. Rules where public docs are silent or disagree: <one line per rule: Rn, label, question for review>. This is an optional second pass for the spec; it does not block G1 or generation. If you change the spec because of it, re-record G1 so I can re-run K3B."
```

### K5. Frontend into `ui/`

```text
STAGE K5 - Frontend into ui/. Owner: Nikhil. You are the frontend integration agent for PaySift. Work ONLY inside ui/ (and ui/public/data via the sync script). Do not change the backend, contract/, oracle/ or runs/.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps below.

HUMAN INPUTS (fill before pasting; any <FILL> left makes you STOP, Blocked by: Me):
MANUS_OUTPUT_PATH: <FILL: path to the unzipped Manus output folder, or to its zip>

REQUIRES-OTHER: none
REQUIRES-OWN: K3_GROUNDING_BUILT
ALLOWED WRITES: ui/, ui/docs/CONTRACT_NOTES.md, handoff/K5_UI_IN_REPO

STEPS
1. Unzip or copy the Manus output into ui/. Do not overwrite a ui/ you already changed by hand: if ui/ is non-empty and not empty-of-changes, STOP, Blocked by: Me.
2. cd ui, npm install, npm run sync-data (copies runs, spec and status from the repo root), npm run check:contract.
3. Start the backend: python cli.py serve (API on 127.0.0.1:8000) in the background, then npm run dev (port 5173) and confirm the data-source banner flips to LIVE API. Run npm run check:api.
4. If check:contract or check:api fail: fix the frontend adapters and types to match the real data. Do NOT edit the backend. List every change in ui/docs/CONTRACT_NOTES.md. Max 5 attempts, then STOP.
5. Stop the background servers. Do not leave processes running.

VERIFY: check:contract passes; check:api passes against the live backend.
COMMIT: feat(ui): Manus frontend wired to real data.
MARKER K5_UI_IN_REPO extra lines: check_contract (pass/fail), check_api (pass/fail), adapter_changes (count).
NOTIFY: none.
```

### K6. Evidence UI and UX polish

```text
STAGE K6 - Evidence UI and UX polish. Owner: Nikhil. You are the frontend agent for PaySift. Work ONLY inside ui/ (and ui/public/data via the sync script). Do not change the backend, contract/, oracle/ or runs/.
FIRST read AGENT_RULES.md, ui/README.md, ui/docs/CONTRACT_NOTES.md, ui/docs/PAGES.md and docs/YOUCOM_NOTES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then B1 to B5.
Hard truth rules (keep them): every number comes from data; mutants are always labeled "HAND-WRITTEN MUTANT"; never rank models; financial (I1-I4) and interface (I5) invariants are shown separately; no external network requests except the API base; fonts self-hosted; never show a source that is not in grounding data; "supported by sources" never means "spec verified".

REQUIRES-OTHER: G1_RESULT
REQUIRES-OWN: K5_UI_IN_REPO, K3B_EVIDENCE_JUDGED
CHECKPOINT before B5: N5_INTEGRATION_OK (owner Nehaa). If it is missing at that point, finish B1 to B4, commit them as wip(K6) if the ui tests pass, and STOP with a message to Nehaa asking for N5 (the API contract must be final before the live check).
ALLOWED WRITES: ui/, ui/docs/CONTRACT_NOTES.md, ui/docs/PAGES.md, handoff/K6_UI_EVIDENCE_DONE

B1. Data layer. Extend the DataSource: getEvidence() (live: GET /evidence; static: ui/public/data/grounding.json) and searchEvidence(ruleId, extraTerms) (live only: POST /evidence/search). Extend scripts/sync-data.mjs to copy runs/grounding.json into public/data (skip with a clear message if missing). Add types and normalizers tolerant to unknown fields, and a vitest suite against the real grounding.json plus a fixture with missing sources. Join evidence to failures by rule id.
B2. Components: EvidencePanel (label chip SUPPORTED / PARTIAL / NOT_FOUND / CONFLICT / NOT_JUDGED, "PaySift convention" tag, "human-reviewed" or "LLM-judged, unreviewed" note, up to 3 sources with title, domain, snippet, retrieved date and external link, the quote when present), SourceCard, EvidenceChip with LIVE or CACHED plus the retrieved date, and a "No source found" empty state. If there is no grounding data show "Evidence not retrieved yet" (never made-up sources).
B3. Placement. /spec: an EvidencePanel on every rule card, and a "Spec gaps" tab listing rules labeled PARTIAL, NOT_FOUND or CONFLICT as questions for review. Failure deep-dive: a collapsible "Evidence for R<n>" panel plus a "Why is this a bug?" button (live mode only; it calls searchEvidence and shows the new cited sources; in static mode disabled with a tooltip while cached evidence still shows). /repair: a "Sources given to the model" list under the before/after table, read from the repair result's grounding field when present. Landing: one proof-strip stat computed from data ("N of M rules backed by cited sources") and a "Live, cited evidence" section with a real rule card. Add the evidence page to the command palette and /demo (a new beat between the finding and the repair, skipped gracefully when there is no grounding data).
B4. UX polish (verify each in the browser): loading skeletons matching final layouts; empty and error states on every page; keyboard navigation and visible focus; aria labels on the ShrinkPlayer and the tables; prefers-reduced-motion respected; contrast AA; responsive from 360px to 1920px with nothing overflowing; the DataSourceBanner and the DRAFT-FROZEN spec banner always visible; consistent copy tone (precise, forensic, calm); the hero says exactly what it shows (real model finding, or "hand-written mutant, not model output"); no console errors; no layout shift.
B5. Verify (after the checkpoint). git pull --rebase, npm run sync-data, npm run verify (typecheck, tests, check:contract, build). Run npm run check:api against python cli.py serve. Check the Network tab: no requests except the API base. Update ui/docs/CONTRACT_NOTES.md and ui/docs/PAGES.md with the new routes, data sources and assumptions.

VERIFY: npm run verify passes; check:api passes.
COMMIT: feat(ui): evidence panels and spec gaps (B1 to B3), feat(ui): UX polish (B4), docs(ui): notes (B5).
MARKER K6_UI_EVIDENCE_DONE extra lines: verify (pass/fail), check_api (pass/fail), routes_added.
NOTIFY: none.
```

### K7. Real results into the UI

```text
STAGE K7 - Real results into the UI. Owner: Nikhil. You are the frontend data agent for PaySift. Work ONLY inside ui/ (and ui/public/data via the sync script). Do not change the backend, contract/ or runs/.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: N7_PILOT_DONE
REQUIRES-OWN: K6_UI_EVIDENCE_DONE
ALLOWED WRITES: ui/ (including hero and landing copy), handoff/K7_UI_REAL_DATA

STEPS
1. Read decision, demo_candidate, failing_rule, classification and illustrative_only from N7_PILOT_DONE, and pilot/DECISION.md.
2. cd ui, npm run sync-data. Confirm the bundled runs include the demo candidate's run.
3. Hero and landing copy must say exactly what the data shows:
   - FINDING, not illustrative: feature the real failure and label it a real model finding (name the candidate source as the data does; no ranking of models).
   - FINDING with illustrative_only: label it "illustrative (Condition B)".
   - NO_FINDING: say so plainly ("harness proven on 13 hand-written mutants; the models tested passed") and feature a failure that is clearly labeled "HAND-WRITTEN MUTANT, not model output".
   Every number must come from data. Remove any sentence that overclaims.
4. Run npm run verify. Run npm run check:api if the backend is up (python cli.py serve), else skip with a note.
5. Make sure no background processes are left running.

VERIFY: npm run verify passes; the hero copy matches pilot/DECISION.md.
COMMIT: feat(ui): real pilot data and truthful hero.
MARKER K7_UI_REAL_DATA extra lines: hero_label (the exact label used), verify (pass/fail).
NOTIFY: none.
```

### K8. Evidence for the real failing rule

```text
STAGE K8 - Evidence for the failing rule. Owner: Nikhil. You are the evidence agent for PaySift. Never invent a source; sources come only from You.com responses.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: N7_PILOT_DONE
REQUIRES-OWN: K3B_EVIDENCE_JUDGED
REQUIRED ENV NAMES: YDC_API_KEY (and the judge model's api_key_env if a re-judge is needed)
EXCEPTION: if N7_PILOT_DONE has decision NO_FINDING, write marker status SKIPPED (summary "no finding, no failing rule") and use the SKIPPED notify below.
ALLOWED WRITES: grounding/cache/, runs/grounding.json, grounding/overrides.yaml (never delete existing human overrides), PROGRESS.md, handoff/K8_EVIDENCE_READY

STEPS
1. Read failing_rule from N7_PILOT_DONE. Open its entry in runs/grounding.json.
2. If the entry already has at least one real source and a label other than NOT_JUDGED, do not spend more calls: just verify it. If it has no sources or is NOT_FOUND, run python cli.py ground --fetch --rules <Rn> --refresh (check the call cap first), then python cli.py ground --judge --rules <Rn> (or the equivalent). Keep any human override for that rule.
3. Validate runs/grounding.json. Confirm every displayed URL appears in the stored raw response for that rule.
4. Record the honest outcome: label, number of sources, convention flag. A convention rule is a valid outcome; the repair then runs ungrounded and says so.

VERIFY: grounding.json valid; spec_sha equals contract/SPEC_HASH.
COMMIT: feat(grounding): evidence for <Rn> (only if anything changed).
MARKER K8_EVIDENCE_READY extra lines: failing_rule, label, sources_count, convention (true/false).
NOTIFY (to Nehaa): "Evidence for <Rn> is in runs/grounding.json (label <label>, <n> sources, convention: <true/false>). Pull and run N8 (real repair). If convention is true, the repair will be ungrounded and the result will say so." SKIPPED: "No finding, so no failing rule to ground. N8 will skip the repair."
```

### K9. Pitch readiness

```text
STAGE K9 - Pitch readiness. Owner: Nikhil. You are the demo readiness agent for PaySift. You verify and document; you do not change results.
FIRST read AGENT_RULES.md and the 3-minute demo script in PAYSIFT_PLAN_v4_YOUCOM.md section 5, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: N8_REPAIR_DONE
REQUIRES-OWN: K7_UI_REAL_DATA, K8_EVIDENCE_READY
ALLOWED WRITES: docs/PITCH_READINESS.md, ui/ (copy fixes only if a check below finds an overclaim), PROGRESS.md, handoff/K9_PITCH_READY

STEPS
1. git pull --rebase origin main (preflight did it), cd ui, npm run sync-data, npm run verify.
2. Static mode: build the UI and confirm every beat of the demo script renders from cached data with the backend OFF, including the evidence panels (CACHED chip with retrieved date), the failure page, and the repair page (or the honest skipped state).
3. Offline: confirm the built UI makes no requests except the API base and outbound source links (static check of the build output). Run python cli.py demo and confirm it needs no network.
4. Write docs/PITCH_READINESS.md. For each beat of the 3-minute script: the screen, whether its data is a real model result, a hand-written mutant, cached evidence or a skipped state, the exact honest line to say (from pilot/DECISION.md, the N8 marker and the K8 marker), the fallback if the network or live search fails, and the numbers computed from data (for example the kill matrix 13/13, rules backed by sources). Add the rehearsal checklist: one run online, one run with Wi-Fi off, one backup screen video, and the "Honest limits" beat (mutants are ours, spec still DRAFT-FROZEN or frozen per G1, not a model ranking, LLM labels unreviewed unless overridden).
5. If any screen says something the data does not support, fix the copy in ui/ and note it.

VERIFY: all beats render offline; docs/PITCH_READINESS.md matches the markers.
COMMIT: docs(pitch): readiness sheet (and fix(ui): copy if needed).
MARKER K9_PITCH_READY extra lines: offline_beats_ok (n of n), copy_fixes (count).
NOTIFY (to Nehaa): "Pitch readiness sheet is pushed. Let's rehearse offline together at <time you choose>: one run online, one with Wi-Fi off, and record a backup video. Pull, then run N9 (final backend checks) before the rehearsal."
```

### K10. Final push and submission

```text
STAGE K10 - Final push and submission. Owner: Nikhil. You are the release agent for PaySift.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NIKHIL.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: N9_FINAL
REQUIRES-OWN: K9_PITCH_READY
ALLOWED WRITES: README.md, handoff/K10_FINAL

STEPS
1. Update README.md: what PaySift is (one paragraph), how You.com is used (the four features E1 to E4 and what is cached), how to run the backend (python cli.py serve) and the UI (ui/: npm install, npm run sync-data, npm run dev), how to reproduce (python cli.py selftest, python cli.py demo), and an honest status section taken from pilot/DECISION.md and the markers (real finding or no finding, mutants are hand-written, spec status, LLM-judged labels unreviewed unless overridden, not a model ranking). Never state anything the data does not support.
2. Full-tree secret scan: read the values from .env (never print them) and confirm none appears anywhere in the tracked tree; confirm .env is untracked.
3. Confirm git status is clean, nothing is unpushed, and every marker needed for the demo exists.
4. In the DONE report print the submission checklist for the human: set the GitHub repo description, confirm the repo is public or shared as the organizers require, final offline rehearsal done, backup video saved, submission form filed.

VERIFY: README accurate; scans clean; nothing unpushed.
COMMIT: docs(readme): final README with You.com usage and honest status.
MARKER K10_FINAL extra lines: readme_updated (true), secrets_scan (clean).
NOTIFY (to the team): "Final push is done. README updated, scans clean, everything is on origin/main (commit <sha>). Submission is next."
```
