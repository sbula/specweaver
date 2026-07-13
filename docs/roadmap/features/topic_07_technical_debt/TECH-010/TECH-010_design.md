# Design: MCP Persistent-Process Executor Migration

- **Feature ID**: TECH-010
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found during C-EXEC-02 SF-1's pre-commit gate (2026-07-13) while auditing repo-wide `ruff` `TID251` (banned raw `subprocess`) violations.

## Problem Statement

`src/specweaver/sandbox/mcp/core/executor.py`'s `MCPExecutor` is the last raw `subprocess.Popen()` call site in `sandbox/` after `TECH-009` migrated `GitExecutor` and `filesystem/core/search.py`'s ripgrep path. Unlike those two, it is **not** a simple `SubprocessExecutor`-injection case.

`MCPExecutor` manages a **long-lived, bidirectional JSON-RPC-over-stdio process**:
- `subprocess.Popen(..., stdin=PIPE, stdout=PIPE)` started once at construction, kept alive across many `call_rpc()` calls over the object's lifetime.
- A background reader thread (`_read_loop`) continuously drains stdout into a queue.
- `call_rpc()` writes a JSON-RPC request to stdin, then blocks (with timeout) waiting for a matching response to appear on the queue — a request/response cycle repeated many times against the *same* process.
- `close()` explicitly terminates the process when the caller is done with it (not on every call).

`SubprocessExecutor.execute()` is architecturally a **one-shot blocking call**: it runs `proc.communicate()`, which waits for the process to fully exit before returning, and closes stdin. It cannot keep a process alive across multiple calls, has no concept of "send more input, get more output, the process is still running." Forcing `MCPExecutor` through it would break the MCP bridge outright — not a regression risk, a certain break.

## What This Needs (not yet designed)

A persistent/streaming-process execution mode — either:
1. **Extend `SubprocessExecutor`** with a new mode/method for long-lived processes (e.g. an `open()`/`start()` that returns a handle supporting repeated `send`/`receive` calls, plus an explicit `close()`), while keeping `execute()`'s one-shot behavior for existing callers, or
2. **A sibling class** (e.g. `PersistentSubprocessExecutor` or `StreamingSubprocessExecutor`) in `sandbox/execution/`, reusing `SubprocessExecutor`'s env-isolation/credential-stripping/cross-platform-kill logic where it overlaps, purpose-built for the keep-alive + background-reader-thread + queue pattern `MCPExecutor` already implements by hand.

Either approach should give `MCPExecutor` the same env allowlisting + credential stripping + structured telemetry the rest of the sandbox already has, without changing its public API (`call_rpc()`, `is_alive()`, `close()`).

## Current State (interim)

`mcp/core/executor.py`'s `subprocess` import carries a documented `noqa: TID251` explaining this architectural mismatch, so the exemption doesn't look like an oversight to a future reader.

## Next Step

Run this through the `specweaver-design` skill properly (Research → Feature Detail → Decompose → Document → Consistency Check) before implementation — this stub only captures the problem statement and options, not a reviewed design.
