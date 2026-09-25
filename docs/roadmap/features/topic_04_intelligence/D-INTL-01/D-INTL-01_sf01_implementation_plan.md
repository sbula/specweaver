# D-INTL-01 SF-01 — Generation Engine & Review

**Status**: COMPLETED · **FRs owned**: FR-1, FR-2, FR-3 · Design:
[D-INTL-01_design.md](D-INTL-01_design.md)

Step 5 of the original build plan: Code Generation + Code Validation + Code Review (3-4 sessions).

## Changes

- `implementation/generator.py`, `implementation/test_generator.py`
- 8 code rules: C01-C08
- `review/prompts/code_review.md`
- `config/layers.py` (per-layer rule config)
- Integration test: `test_full_loop.py`

Copied from FM: nothing.

## As built

Runnable: the full core loop F2→F3→F4→F5→F6→F7.

**Since moved** (noticed 2026-09-25): the generator is `src/specweaver/workflows/implementation/generator.py`;
code rules live in `src/specweaver/assurance/validation/rules/code/`; the review prompt is
`src/specweaver/assurance/validation/rubrics/code_review.md`.
