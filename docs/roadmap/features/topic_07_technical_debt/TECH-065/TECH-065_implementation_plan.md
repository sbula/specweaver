# Implementation Plan: TECH-065

- **Feature ID**: TECH-065
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — normalise the lookup, keep the arguments

| Task | FR | Change |
|---|---|---|
| T1 | FR-1 | `_split_marker`: partition on the FIRST `(` only — an argument may contain more |
| T2 | FR-1 | `_schema_key_for`: exact key first, then the bare name, then nothing |
| T3 | FR-2 | Substitute `>>{args}<<` before `_resolve_template`, so a schema key named `args` cannot capture it |
| T4 | FR-3 | An integration test over the SHIPPED schemas, which is the test that was missing |

**T2's ordering is the whole correctness.** `actix-web.yaml` ships `derive(Clone)` as a literal key.
Falling back first reinterprets it as `derive` and silently changes what a delivered schema means —
which is why the mutant that reverses the order fails seven tests rather than one.

**T4 is not redundant with T1-T3.** The capability's own tests build fixture schemas AND fixture
markers, so the two agree by construction and no fixture test can see a mismatch with what ships.
