# Implementation Plan: TECH-011

- **Feature ID**: TECH-011
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — say it at load

| Task | FR | Change |
|---|---|---|
| T1 | — | Reproduce: `script:` at step level yields `params == {}` and `validate_flow() == []` |
| T2 | FR-1 | `_REQUIRED_PARAMS`, keyed by action, consulted for every step by `validate_flow()` |
| T3 | FR-2 | `extra="allow"` and a misplacement branch that names where the key belongs |
| T4 | FR-2 | Declare `rule`, the one real field the ignored extras were hiding |

**T3 was `extra="forbid"` first, and the suite said no.** The forward-compatibility contract is
explicit in `test_load_with_extra_fields_ignored`, and forbidding extras broke 11 of 16 shipped
pipelines. Measuring the blast radius before trusting the obvious fix is the whole of this task.

**T4 came out of that measurement.** Enumerating the undeclared keys across every shipped pipeline
found exactly one that was real.
