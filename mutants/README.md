# PaySift Mutants & Kill Matrix Documentation

## Nature of the Mutants

The mutants in this directory are deliberately crafted bugs written by the authors of the test harness. Because the authors wrote both the reference specification, test streams, oracle checks, and these mutant handlers, the kill matrix evaluation is inherently and partly **circular**. 

Passing the kill matrix proves that the oracle and stream generators are capable of detecting these specific architectural and contract violations; it does not constitute a proof of complete coverage against unknown real-world bugs.

## Blindness & Attestation

- **m1–m3:** Baseline structural mutants (omitted deduplication, non-atomic ledger write, omitted refund balance check).
- **m4–m6:** Written blind to `oracle/*.py` and `runner/streams.py` using only `contract/SPEC.md` and `ref/handler_ref.py`. Self-attested by the autonomous agent builder. (Because prior conversation turns contained oracle code in context memory, blindness is self-attested as **partial**, adhering strictly to minimal bug implementation without oracle-specific tuning).
- **x1–x4:** Extra mutants designed to model common failure modes observed in LLM-generated code:
  - `x1_bool_amount.py`: Permitting booleans (e.g. `true` passing as `1` due to Python's `bool` subclassing `int`).
  - `x2_float_amount.py`: Accepting float numeric values (e.g. `5.0`).
  - `x3_nonascii_sig_crash.py`: Fragile ASCII assumptions throwing uncaught `UnicodeEncodeError` when encountering unicode characters in headers/signatures.
  - `x4_sig_canonical_reserialized.py`: Canonical re-serialization prior to signature verification, which rejects valid non-canonically formatted JSON payloads.

## Kill Matrix Table

The kill matrix executes the reference implementation and all available mutants across 100 seeded pseudo-random event streams (seeds 0–99).
- Reference handler must pass all invariants across all seeds.
- Each mutant must fail its designated `must_fail_rule` and map to its designated invariant.
- Mutants requiring restart (`m7`) or concurrency (`m8`, `m9`) remain marked as `pending_modes` until Phase P5.
