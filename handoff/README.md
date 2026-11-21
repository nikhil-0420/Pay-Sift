# PaySift Handoff Coordination

Marker files in this directory are lightweight, plain-text coordination records that track stage completion across distributed development tracks. Each marker records the stage identifier, owner, status, ISO-8601 completion timestamp, work commit hash, spec hash, and stage-specific artifact metadata required by downstream stages.

A marker file must strictly be created, written, or updated only by the stage and owner that owns it, as designated in the HANDOFF CONTRACT in `PROMPTS_NEHAA.md` and `PROMPTS_NIKHIL.md`. Stages must never create or spoof markers for another person's tasks.

Consuming stages never treat the mere presence of a marker as sufficient proof of correctness. When a marker is detected, the consuming stage independently executes rigorous VERIFY checks on the underlying codebase, test suites, and schema artifacts to ensure structural and invariant integrity before proceeding.
