# Implementation Plan: TECH-010

- **Feature ID**: TECH-010
- **Status**: DELIVERED 2026-08-19
- **Commit boundaries**: one

## CB-1 — share the discipline, not the call shape

| Task | FR | Change |
|---|---|---|
| T1 | — | Reproduce: with a credential in this process, a server started by `MCPExecutor` reads it back |
| T2 | FR-1, FR-2 | Extract `build_child_env` to module level in `sandbox/execution/executor.py` |
| T3 | FR-1, FR-2 | `SubprocessExecutor._build_env` delegates to it, unchanged in behaviour |
| T4 | FR-1, FR-2 | `MCPExecutor` builds its child environment through it before `Popen` |

**T2 before T4, and the split matters.** Copying the allowlist into the MCP module would have given
the same test results and two definitions of what a child may see — which is how they drift.

**The persistent-executor work is not here.** `execute()` cannot host a long-lived bidirectional
process, as the filing established; what the two paths share is the environment, and that is what
moved.
