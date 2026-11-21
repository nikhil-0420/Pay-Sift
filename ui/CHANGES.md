# PaySift handoff changes

## Step 1 — visual QA
- Reviewed the home, Break it, Repair, Gaps, and Method routes in the sandbox browser at the available preview viewport; checked the rendered screenshots and browser console.
- Confirmed static navigation, the 320–360px scenario rail rule in CSS, side-by-side desktop receipts, stacked receipt behavior below 1100px, internal table scrolling, static-mode action explanations, and reduced-motion rules.
- Fixed a duplicate React key in the landing hero trace that produced a console warning. Remaining console output is limited to standard React Router future-flag notices.

## Step 2 — evidence data path
- Replaced the grounding adapter mapping with the backend shape: `provider`, `generated_at`, `spec_sha`, rule labels, convention/human-review flags, quote, reason, judge metadata, and normalized source records.
- Unknown labels safely become `NOT_JUDGED`; malformed or unsafe source URLs are dropped; missing files return `null`.
- Added optional grounding/schema synchronization and conditional AJV validation. When the backend file or schema is absent, the contract check reports a skip note.
- Added adapter tests for missing data, the real shape, unknown labels/unsafe URLs, and exclusion of the development fixture marker from the production bundle.

## Step 3 — evidence features
- Added `/gaps` with Questions for review, including PARTIAL/NOT_FOUND/CONFLICT and convention-marked rules, reasons, source counts, and specification links.
- Added the route to the command palette and Method/Status areas without adding it to the primary nav.
- Added live-only `POST /evidence/search` behavior behind the single `WHY_BUG_ENDPOINT` constant with loading, rate-limit, unavailable, and cached-evidence fallback messaging. Static mode shows cached evidence only.
- Repair results now resolve `grounding.source_ids` against adapter data and distinguish grounded sources from `Repair ran ungrounded`.
- Landing proof counts only non-convention rules with cited sources and remains hidden when grounding is absent.
- Evidence panels now show label, convention tag, human-review state, quote, reason, CACHED date, source cards, and the required `supporting sources, retrieved <date>` wording.

## Step 4 — readability
- Ran Prettier over `src`, tests, scripts, and the route manifest. `src/main.tsx` remains a single route file; splitting it into page modules was intentionally not attempted because it would be a larger behavior-risking refactor for this handoff.

## Step 5 — handoff
- Updated `TODO.md` for the evidence adapter item and the route manifest.
- `npm run verify` passes: 3 test files, 11 tests, contract check, and production build.
- `npm run check:contract` passes and reports the optional grounding check skipped because this archive does not contain backend `grounding.json` or `contract/grounding_schema.json`.
- Not done: exhaustive screenshot capture at all five requested widths and splitting `main.tsx` into `src/pages/*.tsx`; no backend grounding file was available to validate with AJV.
- Preview remains running locally; nothing was published.

## Files touched
`src/data/grounding.ts`, `src/components.tsx`, `src/main.tsx`, `scripts/sync-data.mjs`, `scripts/check-contract.mjs`, `tests/grounding.test.ts`, `public/manus-routes.json`, `TODO.md`, and `CHANGES.md`.
