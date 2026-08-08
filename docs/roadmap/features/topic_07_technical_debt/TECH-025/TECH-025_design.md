# Design: Pre-Existing FR Traceability Gap (TECH-001 SF-01/02/03, TECH-002 SF-1..4, TECH-005 SF-1/2)

- **Feature ID**: TECH-025
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found running `python scripts/check_fr_coverage.py TECH-001` as the closure gate for
  TECH-001 SF-04 (2026-08-02). **Widened** (2026-08-02, same day) after `check_fr_coverage.py
  TECH-005` surfaced the identical gap while closing TECH-005 SF-3 — user's explicit direction was
  to fold it into this ticket rather than mint a separate one (`TECH-026`), since it's the same
  systemic cause under a different story ID, not a second distinct problem. **Widened again**
  (2026-08-08) when `check_fr_coverage.py TECH-002` was run while verifying whether that ticket's
  amber status still reflected outstanding work. It did not — the work is complete and
  code-verified — but the same citation gap turned up, this time across all four of its
  sub-features. Same cause, same disposition.

## Problem Statement

Three TECH tickets' earlier sub-features fail `check_fr_coverage.py`'s citation check, for the same
underlying reason: they shipped before that gate existed / was wired into the closure process.

**`check_fr_coverage.py TECH-001`**:
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
Tracker well before the session that found this. (SF-04, FR-9, is correctly cited — not part of
this gap.)

**`check_fr_coverage.py TECH-005`** (found the same day, closing SF-3):
```
FR-1    NO PLAN  NO TEST
FR-2    NO PLAN  NO TEST
FR-3    NO PLAN  NO TEST
FR-4    NO PLAN  NO TEST
FR-5    NO PLAN  NO TEST
FR-6    plan     NO TEST
FR-7    NO PLAN  NO TEST
FR-8    plan     3 test file(s)
```
FR-1 through FR-7 (SF-1 "Model Refactoring", SF-2 "Alembic Migration") are uncited for the
identical reason — delivered before the citation gate existed. (SF-3, FR-8, is correctly cited —
not part of this gap.)

In both cases this is **not** evidence the underlying work is wrong — the delivered behavior has
its own test coverage (TECH-001's `tests/e2e/capabilities/infrastructure/test_cqrs_e2e.py` is its
declared `Verifiable Proof` and passes; TECH-005 SF-1/SF-2's own test suites pass). It means the
specific FR-to-test *citation convention* (a test naming both the story ID and the literal `FR-N`
string) was never followed for either story's earlier sub-features.

Per finished-stories-immutable, none of TECH-001 SF-01/02/03's or TECH-005 SF-1/2's own delivered
files are edited by this ticket — this tracks the citation gap as new work, per story.


**`check_fr_coverage.py TECH-002`** (added 2026-08-08):
```
FR-1    NO PLAN  NO TEST
FR-2    NO PLAN  NO TEST
FR-3    NO PLAN  NO TEST
FR-4    NO PLAN  NO TEST
FR-5    NO PLAN  NO TEST
FR-6    NO PLAN  NO TEST
```
None of `TECH-002_design.md`'s FR-1 through FR-6 are cited in any of its four implementation plans
or in any test naming the story. The substance is verified in code: the explicit `ToolRegistry`
exists in `sandbox/registry.py`, `__init_subclass__` appears nowhere in `src/` (the design
deliberately rejected it), the validation layer carries no runtime sandbox imports, and the
ticket's `Verifiable Proof` test passes. Citation convention only.

## Candidate Approaches (not yet designed)

- For each uncited FR (TECH-001: FR-1–8; TECH-005: FR-1–7), identify which existing test(s)
  already exercise that requirement's behavior and add a citation (story ID + literal `FR-N`) to
  that test's docstring/comment — no new test logic needed if coverage already exists, only the
  citation tag.
- Where no existing test actually covers an FR, that is itself a real finding — write one.
- Re-run `check_fr_coverage.py TECH-001` and `check_fr_coverage.py TECH-005` after each batch to
  confirm both ledgers close independently — they are separate stories with separate FR sets;
  closing one does not imply the other is closed.
- If a THIRD story surfaces this same pre-existing-citation-gap shape in the future, fold it in
  here too rather than minting again, per the same reasoning — this ticket is now explicitly the
  home for "delivered before the citation gate existed," not scoped to one story.

## Non-Goals (proposed, pending design)

- Not a re-implementation or behavior change to any of TECH-001 SF-01/02/03's or TECH-005
  SF-1/2's code — citation/documentation work only, plus any genuinely missing test coverage
  discovered along the way.
- Does not touch TECH-001 FR-9 or TECH-005 FR-8 (SF-04's and SF-3's own FRs) — already correctly
  cited.

## Next Step

Run through `specweaver-design` to plan the citation sweep across both stories, or handle directly
as a small, well-scoped documentation-and-test-citation task if a full design pass is unnecessary
for its size.
