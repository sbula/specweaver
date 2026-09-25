# C-INTL-02 SF-02 — MCP Execution Atom (Loom Layer)

**Status**: APPROVED · **Feature ID**: 3.32c · **FRs owned**: FR-2 · **Depends on**: SF-01 ·
Design: [C-INTL-02_design.md](C-INTL-02_design.md) §Sub-features → SF-02

## Goal

Talk to MCP server endpoints over standard I/O (JSON-RPC), e.g. PostgreSQL schema parsing
configurations, and hand the results to the Flow Engine. Keep `subprocess.run` calls out of the
pure-logic layers (`src/specweaver/flow`) under Loom bounding rules.

The external SDK (`mcp` PyPI packet) forces async thread-pooling, so it is not used: `Loom Commons`
is `async_ready: false`.

## Changes

1. **`MCPExecutor`** · [NEW] `src/specweaver/core/loom/commons/mcp/executor.py` [✅ COMPLETED]
   - Inputs: a `command` array and an `env` dict (injected by L3 execution variables).
   - `subprocess.Popen` with `stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True`.
   - `call_rpc(method: str, params: dict)` builds a `jsonrpc=2.0` string, encoded via
     `from specweaver.commons import json` (Anti-pattern 14 override).
   - A `10000ms` stream-level timeout on `stdout.readline()`, so a `docker run` image cannot hold
     the caller (zombie holds).
   - `.close()` or `__del__` terminates the subprocess once the Atom is done.
2. **Executor boundary** · [NEW] `src/specweaver/core/loom/commons/mcp/context.yaml`
   [✅ COMPLETED] — archetype `adapter`; exposes `mcp`; forbids `specweaver/loom/tools/*`,
   `specweaver/loom/atoms/*`.
3. **`MCPAtom(Atom)`** · [NEW] `src/specweaver/core/loom/atoms/mcp/atom.py` [✅ COMPLETED]
   - Input: a `context` dict with the `intent`, the subprocess `command`, and payload params.
   - `MCPAtom.run(context)` dispatches like `GitAtom`, to `_intent_initialize` and
     `_intent_read_resource`.
   - Wraps `MCPExecutor`; returns `AtomResult(status=AtomStatus.SUCCESS)`.
   - Forbids `specweaver/loom/tools/*`.

## Tests

| File | Case |
|---|---|
| [NEW] `tests/unit/core/loom/commons/mcp/test_executor.py` [✅ COMPLETED - Including Integration] | `JSON-RPC` encoding is correct · the 10s stream timeout breaks a hung execution · cleanup calls `terminate()` on orphaned processes |
| [NEW] `tests/unit/core/loom/atoms/mcp/test_atom.py` | `_intent_initialize` returns status markers from mocked executor responses · context params bind without referencing internal model paths |

Commands: `pytest tests/unit/core/loom/commons/mcp/`, `pytest tests/unit/core/loom/atoms/mcp/`.
`tach check`: the 4 new directories must not leak across boundaries.

## As built

**Since moved** (2026-09-25 check): executor and atom now live in `sandbox/mcp/core/`
(`executor.py`, `atom.py`); tests in `tests/unit/sandbox/mcp/core/mcp/`. `call_rpc` takes a
per-call `timeout` (default 10.0s). The runtime guard allows `docker` and `podman` and rejects
host-escaping arguments (`TECH-063`).
