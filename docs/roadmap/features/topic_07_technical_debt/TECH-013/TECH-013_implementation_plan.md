# Implementation Plan: TECH-013

- **Feature ID**: TECH-013
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — one resolver, both roots

| Task | FR | Change |
|---|---|---|
| T1 | FR-1 | Move the CLI's private `_apply_isolation_policy` to `engine/isolation.py` as `apply_isolation_policy`, taking RESOLVED settings |
| T2 | FR-1 | The CLI resolves settings, then delegates — behaviour unchanged |
| T3 | FR-2 | An async `_apply_isolation` in the API module, called by all three run endpoints |
| T4 | FR-2 | The API-run harness the ticket named as the missing piece |

**T1's signature is the design.** Passing a database would have forced the sync loader into an async
endpoint; passing settings shares the application of the policy, which is the part that was absent.

**T3 is three call sites, not one.** `resume_run` and `submit_gate_decision` build a `RunContext`
too, and the ticket's example named only `start_pipeline_run`.
