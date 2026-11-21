# Route and data-source map

| Route | Data |
|---|---|
| `/` | bundled run index, featured selection, kill matrix, static status |
| `/runs` | static index or live GET `/runs`; run details via `/runs/{id}` |
| `/runs/:runId` | GET `/runs/{id}` or bundled run JSON |
| `/runs/:runId/failures/:index` | selected run JSON, failure shrink history and SPEC.md |
| `/kill-matrix` | static `kill_matrix.json` or GET `/kill-matrix` |
| `/break` | static `scenario_verdicts.json`; live POST `/break` |
| `/repair` | cached snapshot only if supplied; live POST `/repair` |
| `/pilot` | static runs, status, `PILOT_REPORT.md` |
| `/spec` | static `SPEC.md`, `SPEC_HASH`, run failure references, and EvidencePanels (Contract Rules & Spec Gaps tabs) |
| `/gaps` | static or live `grounding.json` with spec gaps and review questions |
| `/method` | static contract explanation and supplied status caveats |
| `/demo` | derives guided beats from matrix, runs, scenarios, status |
| `/status` | GET `/health` in live mode; static parsed status and blocker notes |
| `/dev/contract` | bundled schema, run checks and endpoint diagnostics |
| `/dev/sample` | sample-only files, visibly labeled FAKE SAMPLE |
