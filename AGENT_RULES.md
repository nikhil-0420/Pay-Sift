# AGENT RULES (binding for every phase, every prompt)

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

Note: on 2026-11-21 the human authorized a one-time publish (git add/commit/push). All other sessions still follow rule 2.


## Git permissions and stop protocol

Stages run from `PROMPTS_NEHAA.md` and `PROMPTS_NIKHIL.md` may commit and push under the PROTOCOL section P5 and must stop under P3; the old "no git writes" rule is superseded for those stages only; all other rules remain unchanged.
