# PaySift frontend plan

## Approach
Continue the existing Vite + React 18 + strict TypeScript application without changing its routes, data-source contract, static snapshots, or required npm scripts. Keep the `DataSource` API and static snapshot fallback intact. Add UI-only adapters and shared components; isolate grounding-file parsing and its provisional schema in `src/data/grounding.ts`. Missing evidence remains an explicit empty state, not a guessed citation. Any evidence fixture is enabled only in development with `?fixture=evidence` and is stripped from production builds.

Organize the dashboard into reusable components in `src/components/` (navigation/palette, status, badges, receipt, shrink player, timeline, matrix, evidence, diagrams, and empty/skeleton states), keep pages route-driven, and leave normalization/financial calculations in `src/lib/`. Use cmdk for accessible command selection and remark-gfm with ReactMarkdown for the supplied specification. Retain `public/data/` as the offline source of truth and `scripts/` as the contract/sync/build tooling. Keep fonts self-hosted and runtime network use limited to the configured API base and links explicitly followed by a user.

## Structure
- `src/data/`: existing live/static source contract plus the isolated grounding adapter.
- `src/components/`: shared command palette, responsive navigation, status board, classification and rule badges, receipts, shrink player, event timeline, matrix heatmap, evidence panel, pipeline, diff viewer, copy affordances, skeletons and designed empty states.
- `src/pages/`: existing route views; refine them without removing routes or changing route semantics.
- `src/lib/`: money formatting, dynamic invariant keys, provenance classification, rule parsing, and source-neutral helpers.
- `src/types/`: generated and tolerant data types; grounding's provisional type stays owned by its adapter.
- `public/data/`: supplied snapshots remain offline; an absent `runs/grounding.json` is tolerated.
- `scripts/`: preserve sync-data, contract/API checks, type generation and existing npm scripts.
- `tests/`: adapter, calculations, and source-data behavior.
- `docs/`: contract notes and route/data mapping.

## Design
- Alternative styles: restrained terminal console (0.07), Swiss editorial monochrome (0.06), forensic ledger (0.87). Chosen: forensic ledger.
- Movement: receipt-printer instrument panel; restrained, tactile and precise.
- Principles: provenance visible; numbers are data-derived; financial and interface findings stay distinct; explain evidence before interpretation.
- Color: dark ink provides a quiet work surface; warm paper carries high-contrast ledger details; signal red marks violations; amber marks caution; green marks passing states. Status is never color-only.
- Layout: left-aligned editorial canvas with sticky translucent navigation, broad ledger rows and a deliberately wider scenario rail; avoid cramped dashboard grids.
- Motifs: receipt perforation, restrained VOID stamp, compact event tickets and copyable hash chips.
- Interaction: keyboard-operable command palette, menus, accordions and tables; filters and traces expose evidence without rankings; live calls are clearly separated from static replay.
- Motion: short transform/opacity-only ticket, receipt and reveal transitions; respect `prefers-reduced-motion` and do not invent shrink steps.
- Type: self-hosted Bricolage Grotesque display, Inter Tight UI, JetBrains Mono for IDs and amounts.
- Brand: forensic evidence for payment webhook maintainers; precise, calm, accountable.
- Voice: “The duplicate capture posted twice.” “This is the smallest stream that still breaks the ledger.”
- Mark: bespoke ledger glyph built from three vertical receipt rules with one red offset line.
- Signature color: signal red `#FF3B2F`.

## Serving and constraints
Keep the existing strict dev ports and API base behavior. Static mode must work without the backend and without external font, analytics, or asset requests. Preserve the preview and do not publish. Keep `public/manus-routes.json` in sync with all existing routes. Build static pages and ensure production contains no developer overlays or fixture content. Preserve npm pinning (`npm@10.9.9`) and existing scripts; new dependencies are limited to `cmdk` and `remark-gfm` requested for accessible command navigation and GFM specification rendering.
