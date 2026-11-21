# UI Merge Plan: Adopting paysift-ui-fixed into ui/

**Date:** 2026-11-21  
**Source:** `E:\paysift-ui-fixed` (read-only import)  
**Target:** `ui/`  
**Dependencies:** No new runtime dependencies. `ui/package.json` matches `E:\paysift-ui-fixed\package.json` exactly. All fonts and assets are self-hosted. Zero remote CDN/image/font URLs.

## Component & Page Review

| Component / Page | Our Equivalent | Decision | Data Needed | Hardcoded Data / External URLs / Dependencies | Notes |
|---|---|---|---|---|---|
| `styles.css` | `ui/src/styles.css` | **MERGE** | CSS variables, tokens | None (self-hosted fonts, no external URLs) | Adopt liquid ember background, glassmorphism card styling, responsive layouts, scenario rails, pipeline diagrams. Retain K6 `.evidence-chip`, `.source-meta-row`, `.chip-live`, `.chip-cached`, and accessible focus-visible rings. |
| `PipelineDiagram` | `ui/src/components.tsx:PipelineDiagram` | **ADOPT** | `stages` (`label`, `state`, `detail`, `icon`) | None | Adopt tone-based state pill badges (`blocked`, `pending`, `complete`, `idle`), index numbers, `data-state` attribute, and responsive snake-flow support. |
| `EvidencePanel`, `EvidenceChip`, `SourceCard`, `EvidenceLanding`, `EvidenceGaps` | `ui/src/components.tsx` | **MERGE** | `GroundingData`, rule citations | Outbound URLs from verified You.com sources only | Retain K6 `EvidenceChip` (`LIVE` vs `CACHED` with retrieval date), `SourceCard` (domain eyebrow, title, snippet, external link), `EvidencePanel` (top 3 sources, quotes, reasons, review notes, "No source found"), `EvidenceLanding` stat (`N of M rules backed by cited sources`), and `EvidenceGaps` table. |
| `LedgerReceipt`, `KillMatrixHeatmap`, `ShrinkPlayer` | `ui/src/components.tsx` | **MERGE** | `rows`, `mutants` | None | Adopt refined layout and styling while keeping accessible `aria-label` attributes on tables and controls. |
| `Shell` & Navigation | `ui/src/main.tsx:Shell` | **MERGE** | `mode`, `source`, `raw` | None | Adopt smooth scroll reset on route changes (`window.scrollTo(0, 0)` and hash scroll) and translucent glass header. Retain `DataSourceBanner` and `DRAFT-FROZEN` spec banner. |
| `ruleSummary` helper | New in `ui/src/main.tsx` | **ADOPT** | Spec rule IDs (R0–R10) | Concise plain-language summaries | Provides readable 1-line rule summaries for specification cards without losing full contract text. |
| `Home` / Landing Page | `ui/src/main.tsx:Home` | **MERGE** | `runs`, `kill_matrix`, `grounding` | None | Adopt dark glass featured failure card (`featured-paper`) and refined hero layout. Retain K6 landing proof stat (`citedRuleCount(grounding)`) and "Live, cited evidence" section. Ensure "HAND-WRITTEN MUTANT" truth labeling is strictly preserved. |
| `Runs`, `RunDetail`, `Failure` | `ui/src/main.tsx:Runs` | **MERGE** | `runs`, run details, `grounding` | None | Adopt cleaner filter tabs and failure card layout. Retain "Why is this a bug?" live evidence button and rule `EvidencePanel`. |
| `KillMatrix` View | `ui/src/main.tsx:KillMatrix` | **MERGE** | `kill_matrix.json` | None | Adopt clean table formatting and legend. Keep financial (I1-I4) and interface (I5) invariants grouped separately. |
| `BreakPage` | `ui/src/main.tsx:BreakPage` | **ADOPT** | `scenario_verdicts.json`, candidate list | None | Adopt compact numbered case tiles, structured snapshot notice card, and document-level scrolling (removing nested sticky scrollbar). |
| `Repair` & `RepairResult` | `ui/src/main.tsx:Repair` | **MERGE** | `runs`, repair API, `grounding` | None | Adopt labelled input fields and structured action notices. Retain "Sources given to the model" `SourceCard` list from repair grounding. |
| `Pilot` View | `ui/src/main.tsx:Pilot` | **ADOPT** | `status.json`, `PILOT_REPORT.md` | None | Adopt candidate record tiles, refined readiness flow, and honest Condition B disclosure. |
| `Spec` View | `ui/src/main.tsx:Spec` | **MERGE** | `SPEC.md`, `SPEC_HASH`, `grounding` | None | Adopt `ruleSummary` cards, clean expandable contract sections, and aligned arrows. Retain "Contract Rules" vs "Spec Gaps" tabs and `EvidencePanel` on every rule card. |
| `Method` View | `ui/src/main.tsx:Method` | **ADOPT** | `status.json`, `SPEC_HASH` | None | Adopt balanced 8-stage snake-flow pipeline with state-coded icon nodes. |
| `Demo` / Guided Walkthrough | `ui/src/main.tsx:Demo` | **MERGE** | `runs`, `kill_matrix`, `grounding` | None | Adopt refined keyboard navigation and layout while retaining the "Evidence grounding" beat between Finding and Repair. |
| `Status` View | `ui/src/main.tsx:Status` | **ADOPT** | `status.json`, `/health` | None | Adopt clean phase cards and blocker section styling. |
| `Palette` (Command Palette) | `ui/src/main.tsx:Palette` | **MERGE** | Route manifest | None | Retain all navigation shortcuts including Questions for review (`/gaps`). |

## Implementation Strategy
1. **Styles Batch:** Merge `paysift-ui-fixed/src/styles.css` into `ui/src/styles.css`, appending the K6 evidence styles (`.evidence-chip`, `.chip-live`, `.chip-cached`, `.source-meta-row`, `.source-snippet`, `.evidence-landing-section`, `.evidence-no-source`).
2. **Components Batch:** Merge `paysift-ui-fixed/src/components.tsx` into `ui/src/components.tsx`, adopting the new `PipelineDiagram` with state tone indicators while keeping `EvidenceChip`, `SourceCard`, `EvidencePanel` (top 3 sources), and table accessibility labels.
3. **Pages Batch:** Merge `paysift-ui-fixed/src/main.tsx` into `ui/src/main.tsx`, adopting the scroll reset, `ruleSummary`, dark glass featured card, Break scenario tiles, Method snake-flow, and Repair controls, while preserving all K6 evidence hooks (`useGrounding`, "Why is this a bug?" button, landing proof stat, spec tabs, repair sources, demo beat).
4. **Verification & Checks:** Run `npm run sync-data`, `npm run verify`, URL cleanliness grep, and `npm run check:api`.
