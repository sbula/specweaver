# Design: TECH-001's Pre-Existing FR Traceability Gap (SF-01/02/03)

- **Feature ID**: TECH-025
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found running `python scripts/check_fr_coverage.py TECH-001` as the closure gate for
  TECH-001 SF-04 (2026-08-02), per the `dev` skill's own instruction to run it before writing
  `Status: COMPLETE` on a story whose last sub-feature just landed.

## Problem Statement

`check_fr_coverage.py TECH-001` fails:
```
FR-1    NO PLAN  NO TEST
FR-2    NO PLAN  NO TEST
FR-3    NO PLAN  NO TEST
FR-4    NO PLAN  NO TEST
FR-5    NO PLAN  NO TEST
FR-6    plan     NO TEST
FR-7    NO PLAN  NO TEST
FR-8    NO PLAN  NO TEST
```
None of `TECH-001_design.md`'s FR-1 through FR-8 (all belonging to SF-01 "Deconstruct Config
Monolith", SF-02 "Decentralize CLI Layer", or SF-03 "Consolidate Sandbox") are cited — by the
literal string `FR-N` — in any of their own implementation plans or in any test file mentioning
`TECH-001`. All three sub-features were delivered and marked `✅ Committed` in the Progress
Tracker well before this session (SF-04, the only sub-feature this session touched, is FR-9 and
is correctly cited — confirmed, not part of this gap).

This is **not** evidence the underlying work is wrong — SF-01/02/03's actual delivered behavior
has its own extensive test coverage (`tests/e2e/capabilities/infrastructure/test_cqrs_e2e.py` is
TECH-001's own declared `Verifiable Proof`, and passes). It means the specific FR-to-test
*citation convention* `check_fr_coverage.py` checks for (a test file that names both the story ID
and the literal `FR-N` string) was never followed for SF-01/02/03 — most plausibly because this
gate did not exist yet, or was not yet wired into the closure process, when those sub-features
shipped.

Per finished-stories-immutable, SF-01/02/03's own delivered files are not edited by this ticket —
this tracks the citation gap as new work.

## Candidate Approaches (not yet designed)

- For each of FR-1 through FR-8, identify which existing test(s) already exercise that
  requirement's behavior (likely several, given `TECH-001`'s broad scope) and add a citation
  (story ID + literal `FR-N`) to that test's docstring/comment — no new test logic needed if
  coverage already exists, only the citation tag.
- Where no existing test actually covers an FR, that is itself a real finding — write one.
- Re-run `check_fr_coverage.py TECH-001` after each batch to confirm the ledger closes.

## Non-Goals (proposed, pending design)

- Not a re-implementation or behavior change to any SF-01/02/03 code — citation/documentation
  work only, plus any genuinely missing test coverage discovered along the way.
- Does not touch FR-9 (SF-04's own FR) — already correctly cited.

## Next Step

Run through `specweaver-design` to plan the citation sweep, or handle directly as a small,
well-scoped documentation-and-test-citation task if a full design pass is unnecessary for its
size.
