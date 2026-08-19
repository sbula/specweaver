# Implementation Plan: TECH-062

- **Feature ID**: TECH-062
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — measure first, then guard what is true

| Task | FR | Change |
|---|---|---|
| T1 | — | Measure FR-4's hazard: 8 then 32 concurrent `worktree_add` against a real repo. Zero failures on git 2.53.0 |
| T2 | — | Measure FR-3's hazard: nothing in `core/flow/` allocates or reads a port, so it cannot occur |
| T3 | FR-1 | The concurrent fan-out over real worktrees that no test ran, asserting what git knows |

**T1 and T2 are the deliverable as much as T3.** The filing said to measure before choosing among
three approaches, and the measurement removed all three: implementing a lock would have shipped a
mechanism with no failure to point at, which is exactly how FR-3 and FR-4 came to be claimed without
being built.

**T3 asserts existence, not status.** A guard reading only the returned status passes an
implementation that reports success and creates nothing.
