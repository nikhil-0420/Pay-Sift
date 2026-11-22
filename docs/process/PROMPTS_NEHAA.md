# PROMPTS_NEHAA.md: stage prompts for Nehaa (backend pipeline)

Repo: https://github.com/nikhil-0420/Pay-Sift (branch `main`). Companion file: `PROMPTS_NIKHIL.md`. Background plans: `PAYSIFT_BUILD_PLAN_v3.md` (backend contract), `PAYSIFT_PLAN_v4_YOUCOM.md` (track plan).

**Your goal:** a REAL model finding (or an honest "no finding") through the sandbox, then a real repair, without colliding with Nikhil's You.com layer and UI.

## WHO STARTS FIRST, AND WHEN YOU START

- **Nikhil starts first.** He runs K0 (organizer rules, collaborators, commits these prompt files). It takes about 5 minutes.
- **You start N0 only after his message** "K0 done, you are added". While you wait you may do things that need nothing from the repo: start the Docker Desktop install (it may need a restart or WSL2), and check `python --version` (3.12 is the target).
- After that you and Nikhil work in parallel. Every dependency between you is a marker file in `handoff/`; the agents check them for you and stop with a ready-to-send message if something is missing.

## YOUR STAGES IN ORDER

| Stage | Start when | Needs from Nikhil | You hand over |
|---|---|---|---|
| N0 Setup | his K0 message arrives | `K0_ACCESS_READY` | none |
| N4 Models and keys | right after N0 (no Docker needed) | none | `N4_MODELS_PUSHED`: tell him the judge model |
| N1 Docker + Gate 4 | after N4 (start the Docker install earlier) | none | `N1_GATE4_PASSED` (info) |
| N2 Leftover fixes | after N1 | none | none |
| N3 G1 record | after the G1 humans finish AND N2 has finished running | none (his gap list K4 is an optional second pass) | `G1_RESULT`: tell him if the spec changed |
| N5 Integration | after N2 and N3 | none (merges his K3 if it has landed) | `N5_INTEGRATION_OK`: API contract final |
| N6 Generate | after N5 | none | `N6_CANDIDATES_PUSHED` (info) |
| N7 Pilot (RUN, then FINALIZE) | after N6 | none; pick the demo candidate with Nikhil | `N7_PILOT_DONE`: he runs K7 and K8 |
| N8 Repair | after N7 | `K3_GROUNDING_BUILT` and `K8_EVIDENCE_READY` | `N8_REPAIR_DONE`: he runs K9 |
| N9 Final | after his K9 | `K9_PITCH_READY` | `N9_FINAL`: he runs K10 |

Human-only step, no agent: **G1 itself**. Pick Koushik or Rithvik. Each of you fills the answer sheet in `contract/GATE1_PACKET.md` independently (10 cases). Neither of you opens `contract/GATE1_KEY.md` until both are done. Compare against the key, fix `contract/SPEC.md` or the case yourselves, check SQ-001 in `NEEDS_HUMAN.md`, then run stage N3 to record the result.

**Time-box rule:** if Docker is not passing 60 minutes after N1 first started, N1 stops with a fallback message for Nikhil. The fallback pitch is "harness proven on 13 mutants plus the You.com layer, no model run". Never run model code outside the sandbox. Never present a mutant as a model result.

**Cut line if time runs out:** drop N8 (repair) before N7 (pilot). Never cut N1 to N7.

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

### N0. Setup and baseline

```text
STAGE N0 - Setup and baseline. Owner: Nehaa. You are the Antigravity agent for Nehaa on PaySift (repo root = current folder).
FIRST read AGENT_RULES.md, then the sections PROTOCOL and HANDOFF CONTRACT of PROMPTS_NEHAA.md, and obey them exactly (they override "no git writes" and "never stop" only as written there). Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: K0_ACCESS_READY
REQUIRES-OWN: none
ALLOWED WRITES: .venv (git-ignored), .env (git-ignored, no keys), handoff/N0_SETUP_OK
If git fetch fails here, the likely cause is that Nikhil has not added Nehaa as a collaborator yet: use the K0 message in the STOP report.

STEPS (each has a done-when check)
1. Python: run python --version. Below 3.12 = STOP (Blocked by: Me). Exactly 3.12 = fine. Newer (for example 3.14) = continue but record a WARNING: "host Python differs from the 3.12 sandbox image; prefer a 3.12 venv".
2. Virtual environment: create .venv with the best available 3.12 interpreter if one exists, else the default one. Activate it in the host shell style (Windows: .venv\Scripts\activate). Install requirements.txt. Done when pip check shows no broken requirements.
3. Run pytest -q. Hostile tests are skipped without Docker: that is expected. Any other failure: investigate and fix only inside Nehaa-owned paths, max 5 attempts, else STOP.
4. Run python cli.py check-env. Record the output summary.
5. Environment file: if .env does not exist, create it from .env.example if that exists, with EMPTY values only. Confirm .env is git-ignored (git check-ignore .env). Never write a key.
6. Expected noise: on a fresh clone the "git baseline" check in selftest or check-git fails because .agent/git_baseline.txt is missing. Run python cli.py selftest once, confirm that is the ONLY failing check, and record it as expected. Do not fix it by editing git state.
7. Confirm PROMPTS_NEHAA.md, PROMPTS_NIKHIL.md and handoff/README.md exist in the repo root.

VERIFY: steps 3 to 7 recorded in .agent/progress_N0.md.
COMMIT: nothing to commit except the marker (the stage changes no tracked files). Use the P5 end-of-stage procedure for the marker only.
MARKER N0_SETUP_OK extra lines: python_version, pytest_result (passed/skipped counts), selftest_note (the expected git-baseline failure), docker_present (yes/no, informational).
NOTIFY: none.
```

### N4. Models and keys (no Docker needed)

```text
STAGE N4 - Models and keys. Owner: Nehaa. You are the Antigravity agent for Nehaa on PaySift.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps below.

HUMAN INPUTS (fill before pasting; any <FILL> left makes you STOP, Blocked by: Me):
MODELS:
  - id: <FILL>   provider: <FILL>   api_key_env: <FILL>   role: strong
  - id: <FILL>   provider: <FILL>   api_key_env: <FILL>   role: strong
  - id: <FILL>   provider: <FILL>   api_key_env: <FILL>   role: strong
  - id: <FILL>   provider: <FILL>   api_key_env: <FILL>   role: small     (optional: delete this line if none)
JUDGE_MODEL_ID: <FILL>   (the cheapest of the above; Nikhil's evidence judge will use it)

REQUIRES-OTHER: none
REQUIRES-OWN: N0_SETUP_OK
REQUIRED ENV NAMES: every api_key_env listed above (names and non-empty values in .env; never print values)
ALLOWED WRITES: config/models.yaml, handoff/N4_MODELS_PUSHED

STEPS
1. Read config/models.yaml and understand its structure. Replace every FILL_ME using ONLY the inputs above. Never invent a model id. Never write a key into this file.
2. Confirm each api_key_env is set in .env (names only). Missing: STOP with the exact variable names to add.
3. Run python cli.py generate --dry-run. It must make no API calls. Capture the planned call count.
4. Budget check: planned generation calls + 11 (Nikhil's judge) + 10 (repair reserve) must fit the configured cap (max_total_api_calls or the equivalent in config). If it does not fit: STOP, Blocked by: Me, with the numbers and two options (raise the cap, or reduce candidates or models). Do not change the cap yourself.
5. Run pytest -q for anything touching config loading.

VERIFY: no FILL_ME left; dry run printed a plan; budget fits.
COMMIT: feat(config): fill model ids. Paths: config/models.yaml only.
MARKER N4_MODELS_PUSHED extra lines: judge_model, env_var_names (names only, comma separated), planned_generation_calls, cap.
NOTIFY (to Nikhil): "models.yaml is pushed. Judge model: <judge_model>. Put <env var name for the judge model> in your local .env (I will send you the key privately, not here). You can run K3B once K3 is finished."
```

### N1. Docker and Gate 4

```text
STAGE N1 - Docker and Gate 4. Owner: Nehaa. You are the sandbox fixer for PaySift.
FIRST read AGENT_RULES.md and PAYSIFT_BUILD_PLAN_v3.md section 10, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps below. Rules from the old sandbox prompt still apply: never run model-generated or hostile code natively, never weaken the docker run flags from plan section 10, never fake results, do not change oracle/*.py, contract/SPEC.md, contract/schema.sql or mutants/*. Do not touch ui/, grounding/ or api/evidence.py.

REQUIRES-OTHER: none
REQUIRES-OWN: N0_SETUP_OK
ALLOWED WRITES: runner/ (Dockerfile, sandbox*.py, worker.py, child.py, sandbox_test.py), scripts/, tests/hostile/, runs/GATE4_PASSED, runs/GATE4_FAILED.md, PROGRESS.md, NEEDS_HUMAN.md, DECISIONS.md, handoff/N1_GATE4_PASSED

TIME-BOX: on the very first run record the start time in .agent/progress_N1.md. On every re-run compute elapsed time. If more than 60 minutes have passed and runs/GATE4_PASSED does not exist: STOP, Blocked by: Nikhil (decision), with the fallback message below.
FALLBACK MESSAGE TO NIKHIL: "Docker/Gate 4 has not passed after 60 minutes. Failing checks: <list>. Decision needed: keep trying for <X> more minutes, or switch to the fallback pitch (harness proven on 13 mutants plus the You.com layer, no model run). Reply with which."

STEPS (each has a done-when check)
1. Docker available: run docker version and docker info. If they fail: STOP, Blocked by: Me, instruction "start Docker Desktop (WSL2 or Hyper-V enabled), wait until it says running, then re-run N1".
2. python cli.py check-env. Confirm docker works.
3. Pull the base image if missing: docker pull python:3.12-slim. Build: docker build -t paysift-sandbox:1 -f runner/Dockerfile runner. Fix build errors in runner/Dockerfile.
4. Run python cli.py sandbox-test and the parity check. Read every failure. Likely first-run problems: Windows bind-mount paths (use --mount type=bind,source=<abs>,target=/cand,readonly), CRLF line endings in scripts or the Dockerfile, user 65534 permissions on /cand and /runner, tmpfs size, stdin/stdout encoding (force utf-8), container name cleanup, timeouts, paths for contract/events.py and schema.sql inside the container, Python 3.12 vs host differences. Fix the real cause in runner/ or scripts/. Max 5 honest attempts per problem.
5. All seven hostile handlers must be contained: socket, write to /, infinite loop, 2 GB allocation, fork bomb, /proc and $HOME read with a host canary variable that must NOT be visible, write to /cand. The runner must never crash. Run hostile tests only through the sandbox.
6. After the tests, docker ps -a --filter name=paysift- must list nothing.
7. Parity: reference and every mutant give identical per-seed result digests natively and in the sandbox on seeds 0-19; the reference also matches on seeds 0-99.
8. ONLY when ALL checks pass: write runs/GATE4_PASSED (timestamp, image id from docker image inspect, hostile summary) and delete runs/GATE4_FAILED.md. Otherwise leave GATE4_PASSED absent and write the exact failing checks to NEEDS_HUMAN.md.
9. Update the G1/G4 rows and the "Sandbox first run" notes in PROGRESS.md (append-only rules, honest wording).
10. Run pytest -q (hostile tests now included).

VERIFY: runs/GATE4_PASSED exists; seven hostile handlers contained; no leftover containers; pytest green.
COMMIT: fix(sandbox): first real Docker run (one commit for runner/scripts changes), then chore(progress): Gate 4 passed (PROGRESS.md, runs/GATE4_PASSED).
MARKER N1_GATE4_PASSED extra lines: image_id, hostile_contained (7/7), parity_seeds (0-19 all, ref 0-99).
NOTIFY (to Nikhil, info): "Sandbox is ready and pushed (Gate 4 passed). Nothing needed from you. Next on my side: leftover fixes (N2), then G1."
```

### N2. Leftover backend fixes

```text
STAGE N2 - Leftover backend fixes. Owner: Nehaa. You are the follow-up backend fixer for PaySift.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the tasks below. Do NOT change oracle/*.py, contract/SPEC.md, contract/schema.sql, mutants/*, or the contents of any existing runs/*.json. If something would change oracle_sha or spec_sha, skip it and log it. Do not touch ui/, grounding/ or api/evidence.py. Docker may or may not be running; never run hostile tests natively.

REQUIRES-OTHER: none
REQUIRES-OWN: N1_GATE4_PASSED
ALLOWED WRITES: PROGRESS.md, MORNING_HANDOFF.md, README_DEMO.md, runs/README.md, pilot/PILOT_REPORT.md, docs/NAMING.md, docs/API_CONTRACT.md, docs/API_EXAMPLES.json, scripts/selftest.py (selftest hook), runner/sandbox.py (--print-cmd only), tests/ (new tests), api/main.py (additive fields only), manus_attachments/, manus_attachments.zip, handoff/N2_FIXES_DONE
Do not edit runner/sandbox.py by hand while another stage is running. Make one commit per task T1 to T7.

CHECKPOINT before T6 (API work): git fetch origin and git pull --rebase origin main, because api/main.py is shared with Nikhil. If his K3 has landed, api/main.py will contain one include line for api/evidence.py: keep it exactly as is.

T1. HONEST STATUS. PROGRESS.md: if a phase or gate depends on something that never ran (real model keys, pilot), mark it "PARTIAL (blocked: <reason>)" instead of DONE. G8 is "PASSED (skipped checks listed)" if any selftest check was skipped. scripts/selftest.py: report skipped checks as SKIP, separately from PASS; print "PASS (N skipped)" with reasons. Apply the same wording in MORNING_HANDOFF.md and README_DEMO.md. Now that Docker works, P4 should reflect the real Gate 4 result from N1.
T2. NAMING CONSISTENCY. Grep the whole repo for invariant key names. Docs disagree (I1_signature vs I1_integrity, I5_interface vs I5_totality). The canonical names are the ones the code emits (oracle/checks.py and the run JSONs). Fix every doc, README and report text to match. Do NOT rename keys in code or existing run JSONs. Fix runs/README.md: run JSON version (from contract/run_schema.json), the condition and source values as the code emits them, and the "Rs created from nothing" figure (compute it from runs/real_example.json, never quote from memory). Write docs/NAMING.md listing canonical invariant keys, modes, source values, condition values and rule ids as found in code.
T3. WORDING ACCURACY. In MORNING_HANDOFF.md and pilot/PILOT_REPORT.md replace overclaims with data: "<=2-event shrinking" becomes the real G7 numbers (max 3 for m7, <=4 overall, plus the m3 seed-2 note: 6 events under deletion-only ddmin); "100% sensitivity" becomes "13/13 hand-written mutants killed, reference clean"; remove any claim implying a model was tested unless runs with source live or pre-run exist.
T4. PYTHON 3.12 COMPATIBILITY. Parse every .py file with ast.parse(feature_version=(3,12)) and report failures. Grep for 3.13/3.14-only features (except A, B: without parentheses, t-strings, copy.replace and similar stdlib additions). If pip install into .venv works, install vermin and run it with --target=3.12-. Fix incompatibilities in non-oracle code. Add tests/test_py312_compat.py.
T5. SANDBOX CODE VERIFICATION. Add python -m runner.sandbox --print-cmd --file <path> --mode <mode> that prints the docker run argument list and executes nothing. Add tests with mocked subprocess asserting: the exact flags from plan section 10 are present; the candidate is mounted with --mount type=bind,...,readonly using a Windows-style source path (PureWindowsPath) with no colon problems; docker kill and docker rm -f by container name run in a finally block, including on timeout and exception; no shell=True anywhere; run_in_sandbox returns a structured error and never raises when docker is missing. Static check: every tests/hostile/*.py starts with the /.dockerenv guard and no module imports or execs tests/hostile files.
T6. API CONTRACT FOR THE FRONTEND (additive only). Using FastAPI TestClient (no network) capture real responses for: GET /health, GET /runs, GET /runs/{id} (one reference, one mutant, one run with failures), GET /kill-matrix, POST /break (reference and a mutant, one scenario), POST /repair (stub or cached path, and the error path), and the error cases (unknown id, path traversal attempt, untrusted candidate without runs/GATE4_PASSED). Write docs/API_EXAMPLES.json (status plus body per call; truncate long lists to 2 items and mark "truncated": true) and docs/API_CONTRACT.md (method, path, request body, response keys, error shape). Verify GET /runs list entries expose: id, candidate id/source/model/condition, created_at, spec_sha, failure count, financial and interface failure counts; add any missing field additively with tests. Add a test for the CORS preflight from http://localhost:5173 and http://127.0.0.1:5173.
T7. MANUS BUNDLE. Create or refresh manus_attachments/ and manus_attachments.zip (Python zipfile, relative paths preserved) with: api/main.py, contract/run_schema.json, contract/validate_run.py, contract/SPEC.md, contract/SPEC_HASH, runs/README.md, runs/real_example.json, runs/kill_matrix.json, runs/scenario_verdicts.json, runs/sample.json, runs/kill_matrix.sample.json, pilot/PILOT_REPORT.md, PROGRESS.md, NEEDS_HUMAN.md, the latest run_m1_*, run_m7_* and run_m8_* files, docs/NAMING.md, docs/API_CONTRACT.md, docs/API_EXAMPLES.json. List any missing file in manus_attachments/MISSING.txt.
T8. FINISH. Run python cli.py report, the full pytest suite and python cli.py selftest. Fix real failures honestly (a git-baseline failure on a fresh clone is expected: note it, do not "fix" it by editing git state). Append a "Post-handoff fixes" report to PROGRESS.md. Update MORNING_HANDOFF.md phase status, gate status and headline with corrected facts and add a "Still blocked" list (model keys if still missing, pilot, repair, G1). Do not delete any BH item from NEEDS_HUMAN.md.

VERIFY: pytest green, selftest shows PASS with skips listed.
COMMIT: one commit per task (docs(status), docs(naming), docs(wording), test(py312), test(sandbox), docs(api), chore(manus-bundle)), then the T8 report commit.
MARKER N2_FIXES_DONE extra lines: tasks_done (T1..T8), pytest_summary, selftest_summary.
NOTIFY: none (N5 notifies Nikhil that the API contract is final).
```

### N3. Record the G1 result (run only after the G1 humans have finished AND no other stage is running)

```text
STAGE N3 - Record the G1 result. Owner: Nehaa. You are the G1 recorder for PaySift. You do NOT edit the content of contract/SPEC.md or the cases: the humans already did that. You only re-hash, record and report.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps below. Never open contract/GATE1_KEY.md.

HUMAN INPUTS (fill before pasting; any <FILL> left makes you STOP, Blocked by: Me):
G1_PARTNER: <FILL: Koushik or Rithvik>
G1_OUTCOME: <FILL: PASSED | SPEC_FIXED>
SPEC_ALREADY_EDITED: <FILL: yes | no | n/a>   (yes = I already edited contract/SPEC.md or the case files; SPEC_FIXED requires yes)
SQ001_DECISION: <FILL: CONFIRMED | CHANGED: one line>
DISAGREEMENTS_SUMMARY: <FILL: one line, or NONE>

REQUIRES-OTHER: none (his K4_GAP_LIST is an optional second pass; do not wait for it)
REQUIRES-OWN: N0_SETUP_OK
ALLOWED WRITES: contract/SPEC_HASH, contract/SPEC.md and contract/GATE1_* (only the human edits already made: commit them, never change them), PROGRESS.md, NEEDS_HUMAN.md, handoff/G1_RESULT

STEPS
1. Validate inputs. If G1_OUTCOME is SPEC_FIXED but SPEC_ALREADY_EDITED is not yes, or git shows no change to contract/SPEC.md or the case files: STOP, Blocked by: Me.
2. If SPEC_FIXED: run python contract/spec_sha.py, write the new hash to contract/SPEC_HASH. Confirm the hash really changed. Run pytest -q and python cli.py selftest. If failures are caused by existing runs or candidates being bound to the old spec_sha, do NOT rewrite run JSONs: STOP, Blocked by: Me, with the failing checks listed.
3. If PASSED: confirm contract/SPEC.md and contract/SPEC_HASH are unchanged.
4. PROGRESS.md: update the G1 row honestly: outcome, partner, disagreement summary, date. NEEDS_HUMAN.md: append the SQ-001 resolution line (confirmed or changed). Never delete any BH item.
5. regen_required: true if candidates/ already contains generated candidates and the spec changed, else false.

VERIFY: SPEC_HASH matches the computed hash; tests as in step 2.
COMMIT: chore(contract): G1 result and re-hash (only if the spec changed, include SPEC.md and SPEC_HASH), docs(progress): G1 recorded.
MARKER G1_RESULT extra lines: outcome, spec_changed (true/false), regen_required (true/false), partner, sq001.
NOTIFY (to Nikhil): if spec_changed false: "G1 passed, spec unchanged (hash <first 8 chars>). No rework needed on your side." If true: "G1 changed the spec. New SPEC_HASH starts <first 8 chars>. Rule text changed in: <rule ids or 'see commit'>. Your grounding.json is now stale: pull, then re-run K3B (it re-fetches changed rules and re-judges)."
```

### N5. Integration checkpoint

```text
STAGE N5 - Integration checkpoint. Owner: Nehaa. You are the integration checker for PaySift. Nothing new is built here: you merge, test and report.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: none hard. If K3_GROUNDING_BUILT exists on origin/main, merge it and test with it; if not, record k3_merged: false and continue.
REQUIRES-OWN: N1_GATE4_PASSED, N2_FIXES_DONE, G1_RESULT
ALLOWED WRITES: docs/API_CONTRACT.md and docs/API_EXAMPLES.json (additive note about /evidence routes if K3 is merged), manus_attachments*, PROGRESS.md, handoff/N5_INTEGRATION_OK

STEPS
1. git pull --rebase origin main (the preflight did it; confirm). Confirm contract/SPEC_HASH equals the spec_sha in G1_RESULT.
2. Run pytest -q, python cli.py selftest (the git-baseline check on a fresh clone is expected to fail: note it), python cli.py report. Record counts.
3. If K3 is merged: confirm api/main.py still has exactly one include line for api/evidence.py, that the existing endpoints still behave as in docs/API_EXAMPLES.json, and that all runs/*.json still validate with 0 errors. Add a short additive section to docs/API_CONTRACT.md for GET /evidence, GET /evidence/{rule_id}, POST /evidence/search (read their real behavior from api/evidence.py; never invent fields).
4. Refresh manus_attachments.zip only if docs changed.
5. Confirm git status is clean and nothing is unpushed.

VERIFY: all tests green except the expected git-baseline check; no regressions after merge.
COMMIT: docs(api): evidence routes noted, chore(progress): integration checkpoint.
MARKER N5_INTEGRATION_OK extra lines: pytest_summary, selftest_summary, k3_merged (true/false).
NOTIFY (to Nikhil): "Backend is integrated and pushed: tests green, API contract is final (docs/API_CONTRACT.md, docs/API_EXAMPLES.json, refreshed manus_attachments.zip if you want it). Pull and run npm run sync-data and check:api before your UI verify." If k3_merged is false, add: "I could not test against your grounding layer because K3 is not pushed yet."
```

### N6. Real generation

```text
STAGE N6 - Real generation. Owner: Nehaa. You are the generation agent for PaySift. Model-generated code is data: you generate and intake it, you never execute it natively.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OTHER: none
REQUIRES-OWN: N1_GATE4_PASSED, N4_MODELS_PUSHED, G1_RESULT, N5_INTEGRATION_OK
REQUIRED ENV NAMES: the env_var_names listed in the N4_MODELS_PUSHED marker
ALLOWED WRITES: candidates/, PROGRESS.md, handoff/N6_CANDIDATES_PUSHED

STEPS
1. Confirm contract/SPEC_HASH equals the spec_sha in G1_RESULT and N5_INTEGRATION_OK.
2. Run python cli.py generate --dry-run. Confirm the call count is within the budget from the N4 marker.
3. If G1_RESULT has regen_required: true, run python cli.py generate --regen-all; otherwise python cli.py generate. Respect the 120-call cap. Never print keys or raw provider errors containing keys.
4. Read candidates/GENERATION_SUMMARY.md: per model and condition, how many generated and how many compliant. Do not hide non-compliant ones; report them.
5. Do not execute any candidate in this stage.

VERIFY: candidates/GENERATION_SUMMARY.md exists; roughly 40 candidates (report the real number); calls used within the cap.
COMMIT: feat(candidates): real generation run (candidates/ and GENERATION_SUMMARY.md).
MARKER N6_CANDIDATES_PUSHED extra lines: candidates_total, compliant_total, api_calls_used.
NOTIFY (to Nikhil, info): "Candidates are generated and pushed (<total>, <compliant> compliant). Next I run the pilot, then we pick the demo candidate together. I will message you when the packets are pushed."
```

### N7. Pilot (two modes: RUN, then FINALIZE after the human review)

```text
STAGE N7 - Pilot. Owner: Nehaa. You are the pilot agent for PaySift. Failures are classified by a HUMAN; you never decide a classification and you never go looking for a failure. If nothing fails, that is a valid result.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps for the chosen mode.

HUMAN INPUTS (fill before pasting; any <FILL> left makes you STOP, Blocked by: Me):
MODE: <FILL: RUN | FINALIZE>
For FINALIZE only (ignore for RUN):
DECISION: <FILL: FINDING | NO_FINDING>
DEMO_CANDIDATE: <FILL: candidate_id, or NONE>
CLASSIFICATIONS: <FILL: one line per failing candidate: candidate_id = a|b|c|d | short note>
  a = rule violated as written, b = spec was ambiguous, c = harness or sandbox artifact, d = Condition B only (illustrative)

REQUIRES-OTHER: none
REQUIRES-OWN: RUN needs N6_CANDIDATES_PUSHED and N1_GATE4_PASSED. FINALIZE needs N7_PILOT_RAN.
ALLOWED WRITES: pilot/, runs/ (new pilot run outputs; in FINALIZE only the classification field of the run JSONs listed in CLASSIFICATIONS), PROGRESS.md, handoff/N7_PILOT_RAN, handoff/N7_PILOT_DONE

MODE RUN
1. Confirm the sandbox image is current and docker ps -a --filter name=paysift- is empty. Run python cli.py pilot. Model code runs only inside the sandbox.
2. Read pilot/PILOT_REPORT.md and every packet in pilot/packets/. Write pilot/REVIEW_SHEET.md: for each failing candidate the candidate id, model, condition, violated rule and invariant, minimal trace length, and a link to its packet. No classifications, no recommendations about which to feature.
3. If no candidate failed, say so plainly in the review sheet.
4. Commit and push the raw pilot outputs, write marker N7_PILOT_RAN, then STOP with a human-review stop (Blocked by: Me and Nikhil). The STOP report must list the failing candidates and say: "Review the packets together, then fill DECISION, DEMO_CANDIDATE and CLASSIFICATIONS and run N7 in FINALIZE mode."
   MESSAGE TO NIKHIL: "Pilot ran and the raw results are pushed (not classified yet). <n> failing candidates: <ids> (or: no failures). I need about 10 minutes with you to pick the demo candidate: clearest minimal trace, rule printed in the prompt. Do not sync the UI yet."

MODE FINALIZE
1. Validate inputs. If DECISION is FINDING: DEMO_CANDIDATE must be a real candidate id with a classification; if its classification is c (harness artifact), STOP: it is not a finding. If DECISION is NO_FINDING, DEMO_CANDIDATE must be NONE.
2. For each line in CLASSIFICATIONS set the classification field defined in contract/run_schema.json on that run JSON, nothing else. If the schema has no such field, STOP. Validate every touched run with contract/validate_run.py (0 errors).
3. If the demo candidate's only failures are class d, record illustrative_only: true.
4. Write pilot/DECISION.md with the decision, demo candidate, failing rule, classification, and the honest label to use in the pitch ("real model finding", "illustrative (Condition B)" or "no finding: harness proven, models passed").
5. Update PROGRESS.md honestly.

VERIFY: all touched run JSONs validate; PILOT_REPORT.md and DECISION.md agree.
COMMIT: RUN: chore(pilot): raw pilot outputs. FINALIZE: feat(pilot): human classifications and demo decision.
MARKER N7_PILOT_RAN (RUN): extra lines failing_candidates (ids or none). MARKER N7_PILOT_DONE (FINALIZE): extra lines decision, demo_candidate, failing_rule, classification, illustrative_only (true/false).
NOTIFY (FINALIZE, to Nikhil): "Pilot result is final and pushed. Decision: <FINDING or NO_FINDING>. Demo candidate: <id>, rule <Rn>, class <x>, label for the pitch: <label>. Please run K7 (sync UI, make the hero truthful) and K8 (evidence for <Rn>). I run the repair after your K8 message."
```

### N8. Real repair (grounded when his evidence is ready)

```text
STAGE N8 - Real repair. Owner: Nehaa. You are the repair agent for PaySift. A repair that breaks another invariant is a valid, honest result: report it, never hide it.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OWN: N7_PILOT_DONE
REQUIRES-OTHER: K3_GROUNDING_BUILT and K8_EVIDENCE_READY. EXCEPTION: if N7_PILOT_DONE has decision NO_FINDING, require nothing from Nikhil: write marker status SKIPPED (summary "no finding, nothing to repair") and use the NOTIFY below.
REQUIRED ENV NAMES: the env_var_names listed in the N4_MODELS_PUSHED marker (repair model)
ALLOWED WRITES: repair/cache/, runs/ (new repair run outputs), PROGRESS.md, handoff/N8_REPAIR_DONE

STEPS
1. Read demo_candidate and failing_rule from N7_PILOT_DONE. Confirm GATE4 passed and that the candidate's run exists.
2. Confirm runs/grounding.json has an entry for failing_rule. If it has sources, the repair prompt will include them. If it has none (convention: true), the repair runs ungrounded and the result must say so.
3. Check the remaining API call budget; repair needs only a few calls.
4. Run python cli.py repair --candidate <demo_candidate>. Model code runs only in the sandbox.
5. Inspect the cached result in repair/cache/: it must be labeled pre-run (or live), never stub. Record: was the violated invariant fixed, did any other invariant break, and the grounding source ids used.
6. Append the result to PROGRESS.md in plain words, including a bad outcome if that is what happened.

VERIFY: repair cache file exists and is labeled correctly; run JSON validates.
COMMIT: feat(repair): real repair on <demo_candidate>.
MARKER N8_REPAIR_DONE extra lines: repair_file, fixed_rule (true/false), broke_other (true/false), grounding_used (true/false), source_ids.
NOTIFY (to Nikhil): "Repair is cached and pushed. Result: <fixed/did not fix> <Rn>; <broke / did not break> another invariant; grounded: <yes/no>. Run K9 (pitch readiness) and use this exact result in the repair beat." If SKIPPED: "No finding, so no repair. Use the no-finding pitch in K9."
```

### N9. Final checks

```text
STAGE N9 - Final checks. Owner: Nehaa. You are the release checker for PaySift backend.
FIRST read AGENT_RULES.md, then PROTOCOL and HANDOFF CONTRACT in PROMPTS_NEHAA.md, and obey them. Run the PROTOCOL preflight, then the steps below.

REQUIRES-OWN: N8_REPAIR_DONE
REQUIRES-OTHER: K9_PITCH_READY
ALLOWED WRITES: PROGRESS.md, MORNING_HANDOFF.md, README_DEMO.md, handoff/N9_FINAL

STEPS
1. git pull --rebase origin main (preflight did it). Run pytest -q, python cli.py selftest (expected git-baseline noise on a fresh clone), python cli.py report.
2. Run python cli.py demo and confirm it works with no network calls.
3. Check PROGRESS.md, MORNING_HANDOFF.md and README_DEMO.md against the markers: every status word must match what actually ran (no DONE for anything blocked or skipped; the honest labels from pilot/DECISION.md; stub repairs never described as real). Fix wording only.
4. Confirm: git status clean, nothing unpushed, .env untracked, no key value anywhere in the tree (scan using the values in .env, never print them).
5. List the definition-of-done items with PASS/FAIL: GATE4 passed, G1 recorded, models.yaml filled, candidates generated, pilot classified, demo candidate or honest no-finding, cached repair or documented reason, tests green, everything pushed.

VERIFY: all of the above.
COMMIT: docs(status): final honest status.
MARKER N9_FINAL extra lines: pytest_summary, selftest_summary, definition_of_done (list of PASS/FAIL).
NOTIFY (to Nikhil): "Backend is final and pushed. Everything on my side is green (<summary>). Run K10 (README and submission). Human step for both of us: the offline rehearsal with Wi-Fi off, before you submit."
```
