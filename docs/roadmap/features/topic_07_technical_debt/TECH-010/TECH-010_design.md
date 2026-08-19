# Design: MCP Persistent-Process Executor Migration

- **Feature ID**: TECH-010
- **Epic**: Topic 07 (Technical Debt)
- **Status**: DELIVERED 2026-08-19
- **Origin**: Found during C-EXEC-02 SF-01's pre-commit gate (2026-07-13) while auditing repo-wide `ruff` `TID251` (banned raw `subprocess`) violations.

## Problem Statement

`src/specweaver/sandbox/mcp/core/executor.py`'s `MCPExecutor` is the last raw `subprocess.Popen()`
call site in `sandbox/` after `TECH-009` migrated `GitExecutor` and `filesystem/core/search.py`'s
ripgrep path. Unlike those two, it is **not** a simple `SubprocessExecutor`-injection case.

`MCPExecutor` manages a **long-lived, bidirectional JSON-RPC-over-stdio process**:
- `subprocess.Popen(..., stdin=PIPE, stdout=PIPE)` started once at construction, kept alive across many `call_rpc()` calls over the object's lifetime.
- A background reader thread (`_read_loop`) continuously drains stdout into a queue.
- `call_rpc()` writes a JSON-RPC request to stdin, then blocks (with timeout) waiting for a matching
  response to appear on the queue — a request/response cycle repeated many times against the *same*
  process.
- `close()` explicitly terminates the process when the caller is done with it (not on every call).

`SubprocessExecutor.execute()` is architecturally a **one-shot blocking call**: it runs
`proc.communicate()`, which waits for the process to fully exit before returning, and closes stdin.
It cannot keep a process alive across multiple calls, has no concept of "send more input, get more
output, the process is still running." Forcing `MCPExecutor` through it would break the MCP bridge
outright — not a regression risk, a certain break.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | The MCP child gets a built environment, never an inherited one | `MCPExecutor` | constructs the child environment through the executor's allowlist before `Popen` | a variable this process holds and the allowlist does not name is absent from the server, instead of the whole parent environment being handed over |
| FR-2 | Credentials are stripped, including configured ones | `MCPExecutor` | applies the same credential strip `SubprocessExecutor` already applies | `ANTHROPIC_API_KEY` is absent from the server, and a `context.yaml` naming `OPENAI_API_KEY` in `mcp_servers[].env` does not put it back |

## What was reproduced

With `ANTHROPIC_API_KEY` set in this process, a server started by `MCPExecutor` read it back
verbatim. `Popen(env=None)` hands the child the entire parent environment, and when a `context.yaml`
declares no `env` — the common case — `None` is exactly what was passed. The server is an external
binary named by the analysed project's own configuration.

## What was NOT done, and why the ticket was still closable

**`MCPExecutor` still owns its own `Popen`.** The ticket's own analysis is why: `execute()` is
one-shot, `communicate()` waits for the process to exit, and MCP is a long-lived bidirectional
JSON-RPC bridge with a background reader thread. Forcing it through `execute()` was described in the
filing as "not a regression risk, a certain break", and that has not changed.

Neither approach as filed was taken. Extending `SubprocessExecutor` with a persistent mode, or
building a `PersistentSubprocessExecutor` sibling, both move the *call shape*; what the two paths
genuinely share is **what the child is allowed to see**. `build_child_env` is that, extracted to
module level and used by both, so the allowlist and the credential strip have one definition and
`SubprocessExecutor._build_env` delegates to it unchanged.

**Timeout escalation and structured telemetry remain `MCPExecutor`'s own.** `call_rpc` already
carries a per-call timeout; unifying the telemetry shape is a call-shape change and belongs with a
persistent-executor design if one is ever wanted. This ticket closes the security half, which is what
`TECH-063` kept naming as its consequence (4).

## Verifiable Proof

| FR | Test |
|---|---|
| FR-1 | `tests/integration/sandbox/mcp/test_mcp_child_environment.py` — passing the raw config env again fails 3; ignoring the allowlist fails 1. The `PATH` control is what stops an empty environment satisfying both |
| FR-2 | the same file — removing the credential strip fails 3, including the config-injected case |

## Candidate Approaches (as filed)

A persistent/streaming-process execution mode — either:
1. **Extend `SubprocessExecutor`** with a new mode/method for long-lived processes (e.g. an
   `open()`/`start()` that returns a handle supporting repeated `send`/`receive` calls, plus an
   explicit `close()`), while keeping `execute()`'s one-shot behavior for existing callers, or
2. **A sibling class** (e.g. `PersistentSubprocessExecutor` or `StreamingSubprocessExecutor`) in
   `sandbox/execution/`, reusing `SubprocessExecutor`'s
   env-isolation/credential-stripping/cross-platform-kill logic where it overlaps, purpose-built for
   the keep-alive + background-reader-thread + queue pattern `MCPExecutor` already implements by
   hand.

Either approach should give `MCPExecutor` the same env allowlisting + credential stripping +
structured telemetry the rest of the sandbox already has, without changing its public API
(`call_rpc()`, `is_alive()`, `close()`).

## Non-Goals

Written 2026-08-13. This ticket sits in the sandbox execution layer, which is the easiest place in
the repo for a fix to become a rewrite — so the boundaries are stated before anyone starts.

- **Changing `MCPExecutor`'s public API.** `call_rpc()`, `is_alive()` and `close()` stay as they
  are. Callers must not need editing; if they do, the new executor's shape is wrong.
- **Touching `SubprocessExecutor.execute()`'s one-shot behaviour.** Every existing caller depends on
  `communicate()` semantics. A persistent mode is *additive*, whether it lands as a new method or a
  sibling class.
- **The MCP protocol or transport.** JSON-RPC over stdio stays; this is about how the process is
  spawned and supervised, not how it is spoken to. Anything about HTTP or SSE transports is a
  different capability.
- **The other sandbox executors.** `TECH-009` already migrated `GitExecutor` and the ripgrep path,
  and they are one-shot — they gain nothing here.
- **Removing the `noqa: TID251`** before the replacement is proven. The suppression is the honest
  marker of a known architectural mismatch; deleting it early would hide the gap rather than close
  it, and it must be **removed rather than relocated** when the fix lands — `TECH-020`'s rule.

Execution constraint: its own commit, never bundled into a feature commit. The reader thread and
the queue drain are the risky part, and a bisect needs them isolated.

## Current State (interim)

`mcp/core/executor.py`'s `subprocess` import carries a documented `noqa: TID251` explaining this architectural mismatch, so the exemption doesn't look like an oversight to a future reader.

## Next Step

Run this through the `specweaver-design` skill properly (Research → Feature Detail → Decompose →
Document → Consistency Check) before implementation — this stub only captures the problem statement
and options, not a reviewed design.
