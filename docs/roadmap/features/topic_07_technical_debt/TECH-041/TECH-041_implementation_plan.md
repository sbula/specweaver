# Implementation Plan: TECH-041

- **Feature ID**: TECH-041
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — the journey that shows the verdict move

| Task | FR | Change |
|---|---|---|
| T1 | FR-1 | Measure which callers pass `dal_level`, before choosing a path to test |
| T2 | FR-1 | `test_code_dal_strictness_e2e.py`: one module, one pipeline, two projects differing only in `operational.dal_level` |
| T3 | FR-1 | The lenient control, and the assertion that both runs carry the same warning count |
| T4 | FR-1 | Kill three mutants on `effective_strict`, including the always-strict inverse |

**T1 before T2 is the whole plan.** The filed approach assumed the override lived on the
`sw implement` path; it does not, and a scripted-LLM e2e written first would have proven an absence
while looking like a proof.

**Why `c05_import_direction` is removed from the shared pipeline.** It FAILs on a project this small
for reasons unrelated to the DAL, and any FAIL forces exit 1 whatever the strictness — which would
have hidden the difference the test exists to show. Removing it is scoped to the fixture pipeline and
changes nothing shipped.
