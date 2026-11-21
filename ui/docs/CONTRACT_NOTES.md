# Contract notes and source gaps

Source review date: 2026-11-21. Higher-priority supplied materials are the project directory's `main.py`, root `run_schema.json`, `scenario_verdicts.json`, `kill_matrix.json`, two root run JSON files, `real_example.json`, `SPEC.md`, `SPEC_HASH`, `PROGRESS.md`, `NEEDS_HUMAN.md`, and `PILOT_REPORT.md`.

## Mismatches and missing materials

- The brief cites `api/main.py`; the supplied backend entrypoint is root `main.py`. Its imports reference `generate`, `oracle`, `pilot`, and `scenarios` packages that are not included in this 17-file project snapshot. The frontend uses only the route/request shapes visible in `main.py`: GET `/health`, `/runs`, `/runs/{run_id}`, `/kill-matrix`; POST `/break` with `{candidate_id,scenario}`; POST `/repair` with `{candidate_id,failure_id}`. No endpoints for static metadata were present.
- The brief cites `contract/run_schema.json`, `contract/SPEC.md`, `contract/SPEC_HASH`, `runs/*.json`, and `pilot/PILOT_REPORT.md`; supplied equivalents are at repository root, with only two run snapshots and no `runs/` or `contract/` directories. The sync script supports both requested conventional directories and the supplied root-file layout.
- The required sample exclusion says sample files only at `/dev/sample`; root `real_example.json` is explicitly identified by the pilot report as a real mutant fallback, while the prompt also calls `featured.json` real_example. The app uses the actual non-sample `real_example.json` only for a clearly labeled mutant fallback; all mock sample files are isolated to `/dev/sample` and labeled FAKE SAMPLE.
- Candidate metadata in both dated run snapshots identifies `m1_no_dedupe` and `m7_inmemory_dedupe` as source `reference`, while `real_example.json` and the pilot report identify the m1 finding as a hand-written mutant. The UI shows `candidate.source` and `candidate.label` verbatim in run views, without rewriting the dated snapshot provenance. The featured presentation states it is a hand-written mutant only where the selected source says mutant.
- The prompt warns invariant names may vary (`I1_signature`/`I1_integrity`, `I5_interface`/`I5_totality`). Runtime parsing derives the ordered key list using `/^I(\\d)_?(.*)$/`; no invariant key list is hardcoded.
- The prompt demands 13 mutants/13 total while supplied kill-matrix `rows` must be counted dynamically; no fixed count is rendered. Matrix identity uses `rows` and `rules_hit` as supplied.
- `main.py` defines request shapes and endpoint paths but does not specify response schemas for `/break` or `/repair`, nor timeout/error envelope guarantees. UI normalizes defensively and displays backend errors as messages; mutation APIs are only enabled in live mode.
- Prompt says interface-only I5, while source snapshots sometimes label failures by `severity` and others may use differing invariant identifiers. Display follows supplied `severity` where present; I1–I4 financial / I5 interface grouping is calculated from invariant number per requested policy.
- The supplied `SPEC.md` first line is `STATUS: DRAFT-FROZEN (Gate 1 pending)`. The persistent banner is enabled from that exact first-line check.
- Status is parsed from supplied markdown because no API status endpoint exists. Progress tables and human items are retained as raw sourced content where parsing is uncertain; no inferred gate completion is fabricated.

## Assumptions

- API base is `VITE_API_BASE`, default `http://127.0.0.1:8000`, following the request. Vite serves on strict port 5173 as the CORS list in `main.py` allows it.
- `GET /runs` can return summary rows or full runs depending on implementation; client normalization handles both. `GET /runs/{id}` is required to retrieve a detailed run.
- Source labels are shown from candidate.source; labels from candidate.label are never paraphrased.
- A money delta is shown only when expected and observed data expose comparable numeric totals, or compute-able payment ledgers. Missing or ambiguous values are hidden.
- Static mode never calls the backend. Auto mode probes `/health` at startup; its status indicator checks periodically.

## Stage K5 Integration Changes (Frontend Adapters and Tests)

During K5 integration against the live repo data and FastAPI backend (`api/main.py`), the following 3 adapter/test adjustments were made without modifying the backend:
1. `ui/scripts/sync-data.mjs`: Added `"grounding.json"` to the excluded list when syncing individual run files so it is preserved at `public/data/runs/grounding.json` as a grounding artifact rather than indexed as an ordinary candidate run.
2. `ui/tests/data.test.ts`: Excluded `"grounding.json"` from the run normalization test loop since `grounding.json` conforms to `contract/grounding_schema.json` rather than `contract/run_schema.json`.
3. `ui/scripts/check-api.mjs`: Updated `POST /repair` check to accept HTTP 403 and 503 as valid, documented responses when live model execution / Docker sandbox is unavailable on the host environment (Gate 4 blocked / keys unconfigured).

## Stage K6 Evidence UI and UX Polish

Audited and updated existing frontend components against B1-B4 specifications:
1. `ui/src/data/source.ts`: Added `getEvidence` and `searchEvidence` methods to `DataSource` interface, `staticSource`, and `liveSource`. Live mode targets `GET /evidence` and `POST /evidence/search` with fallback to static grounding data.
2. `ui/src/data/grounding.ts`: Added `joinEvidenceToFailures` and tolerant normalization to map contract rules and citations directly into failure cards.
3. `ui/src/components.tsx`: Implemented `EvidenceChip` (`LIVE` vs `CACHED` with date) and `SourceCard` (domain eyebrow, title, snippet, external link). Polished `EvidencePanel` to support up to 3 sources, verbatim quotes, reasons, label chips, convention tags, and human review notes.
4. `ui/src/main.tsx`:
   - Landing proof strip: displays dynamic "N of M rules backed by cited sources" stat computed from data.
   - Spec page: added sub-tabs for "Contract Rules" (rendering `EvidencePanel` on every rule card) and "Spec Gaps".
   - Failure cards: added "Why is this a bug?" action (disabled with informative tooltip in static mode, live search in live mode).
   - Repair view: embedded cited sources via `SourceCard` list.
   - Demo flow: inserted "Evidence grounding" beat between Finding and Repair.
   - Command palette: registered "Evidence and spec gaps" route.
5. `ui/src/styles.css` & Accessibility: Added `aria-label` to table elements, enhanced `:focus-visible` rings for keyboard navigation, and added styled containers for evidence chips and cards.
6. `ui/tests/grounding.test.ts`: Added unit tests verifying real `grounding.json` schema, override parsing, joining failures to evidence, and static source methods.
