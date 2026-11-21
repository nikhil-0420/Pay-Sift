# PaySift Atomic Commit Plan

This document outlines the suggested atomic commit sequence to transition the overnight uncommitted work into git history.

> [!IMPORTANT]
> The overnight agent made **zero git writes**; HEAD remains at `.agent/git_baseline.txt`.
> The commands below are for human execution only.

---

## Simple Option: Single Commit

If you prefer a single clean commit of the entire baseline:

```bash
# =========================================================================
# NOT RUN BY THE AGENT. For the human only.
# =========================================================================

# Ensure no unwanted files are staged and review status
git status

# Stage all files and commit
git add -A
git commit -m "feat: complete PaySift verification platform (phases P0-P10)"
```

---

## Detailed Option: Atomic Commits by Component & Directory

To commit the repository in clean logical units, execute each step sequentially:

```bash
# =========================================================================
# NOT RUN BY THE AGENT. For the human only.
# =========================================================================

# 1. Root configuration, guidelines, and CLI entry point
git add .agent/ .gitignore AGENT_RULES.md DECISIONS.md NEEDS_HUMAN.md PAYSIFT_ANTIGRAVITY_PROMPTS.md PAYSIFT_BUILD_PLAN_v3.md PROGRESS.md README_DEMO.md requirements.txt cli.py config/
git commit -m "feat(core): project skeleton, agent rules, CLI entry point, and metadata"

# 2. Formal contract, SQLite schema, and specification test cases
git add contract/
git commit -m "feat(contract): formal payment contract, SQLite schema, and test cases"

# 3. Independent oracle and reference handler
git add oracle/ ref/
git commit -m "feat(oracle): SQLite oracle validator and verified reference implementation"

# 4. Mutants and defect catalog
git add mutants/
git commit -m "feat(mutants): hand-written payment vulnerability mutants m1-m9 and x1-x4"

# 5. Execution runner, concurrency stress-tester, and Docker sandbox harness
git add runner/
git commit -m "feat(runner): candidate execution runner, concurrency harness, and sandbox"

# 6. Counterexample delta debugging & minimization
git add shrink/
git commit -m "feat(shrink): ddmin minimization algorithm and failure explainer"

# 7. Model candidate generation, provider adapters, and AST intake gate
git add generate/ candidates/
git commit -m "feat(generate): provider adapters, candidate generation, and AST intake gate"

# 8. Pilot runner, failure packets, and pilot report
git add pilot/
git commit -m "feat(pilot): pilot execution runner, failure packets, and pilot report"

# 9. Repair loop and break-it scenario definitions
git add repair/ scenarios/
git commit -m "feat(scenarios): repair prompt generator and 6 break-it scenarios"

# 10. REST API and static HTML report generator
git add api/ report/
git commit -m "feat(api): FastAPI backend server and self-contained static HTML reports"

# 11. Run verification records and scenario verdicts
git add runs/
git commit -m "feat(runs): baseline run artifacts, scenario verdicts, and kill matrix"

# 12. Helper scripts and documentation
git add scripts/ docs/
git commit -m "docs: architecture documentation, naming reference, and demo scripts"

# 13. Test suite
git add tests/
git commit -m "test: comprehensive unit and integration test suite"
```
