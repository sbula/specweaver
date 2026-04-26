# Implementation Plan: Common MCP Client Architecture [SF-2: MCP Execution Atom (Loom Layer)]
- **Feature ID**: 3.32c
- **Sub-Feature**: SF-2 — MCP Execution Atom (Loom Layer)
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_sf2_implementation_plan.md
- **Status**: APPROVED

## Background and Scope

This sub-feature implements the execution and atomic orchestration components responsible for interacting with the Model Context Protocol (MCP) server endpoints via standard I/O (JSON-RPC). It bridges external infrastructure (e.g., PostgreSQL schema parsing configurations) natively down to the internal Flow Engine.

It explicitly isolates `subprocess.run` calls away from the pure-logic layers (`src/specweaver/flow`) using Loom bounding rules. 

> [!IMPORTANT]
> Because external SDKs (`mcp` PyPI packet) enforce asynchronous thread-pooling, we actively avoid them to obey our explicit `async_ready: false` bounding rules in `Loom Commons`.

## Proposed Changes

---

### Loom Commons (Executor Layer) [✅ IMPLEMENTED]

#### [NEW] `src/specweaver/core/loom/commons/mcp/executor.py` [✅ COMPLETED]
Creates the `MCPExecutor` class.
- **Inputs**: A target `command` array strings and `env` dictionary mappings (Injected cleanly by L3 execution variables).
- **Functionality**:
  - Initializes `subprocess.Popen` precisely configured with `stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True`.
  - Defines an atomic `call_rpc(method: str, params: dict)` which internally formats a `jsonrpc=2.0` string and encodes it via `from specweaver.commons import json` (Anti-pattern 14 override).
  - Implements a rigid `10000ms` stream-level timeout block waiting for `stdout.readline()` resolution to prevent recursive zombie holds against `docker run` images.
  - Implements an explicit `.close()` or `__del__` destructor to ensure subprocesses are reliably terminated upon Atom consumption completion.

#### [NEW] `src/specweaver/core/loom/commons/mcp/context.yaml` [✅ COMPLETED]
Establishes execution safety boundaries.
- **Archetype**: `adapter`
- **Exposes**: `mcp`
- **Forbids**: `specweaver/loom/tools/*`, `specweaver/loom/atoms/*`

---

### Loom Atoms (Workflow Orchestration)

#### [NEW] `src/specweaver/core/loom/atoms/mcp/atom.py` [✅ COMPLETED]
Creates the `MCPAtom(Atom)` class.
- **Inputs**: `context` dictionary mapping the `intent`, the explicit subprocess `command`, and payload params.
- **Functionality**:
  - Implements `MCPAtom.run(context)` following the exact design dispatch bindings shown in `GitAtom`.
  - Configures sequential sub-handlers: `_intent_initialize` and `_intent_read_resource`.
  - Safely wraps the `MCPExecutor` and ensures standardized `AtomResult(status=AtomStatus.SUCCESS)` returns.

- **Forbids**: `specweaver/loom/tools/*`

---

### Test Parity

#### [NEW] `tests/unit/core/loom/commons/mcp/test_executor.py` [✅ COMPLETED - Including Integration]
- Test `JSON-RPC` encoding structures are accurate.
- Test 10s stream fallback timeouts reliably break isolated execution holds.
- Test cleanup ensures orphaned processes throw `terminate()`.

#### [NEW] `tests/unit/core/loom/atoms/mcp/test_atom.py`
- Test `_intent_initialize` accurately returns status markers based on mocked executor responses.
- Test context map parameters bind effectively without referencing internal model paths.

## Verification Plan

### Automated Tests
Execute Pytest modules ensuring isolation bounds hold across both unit implementations.
`pytest tests/unit/core/loom/commons/mcp/`
`pytest tests/unit/core/loom/atoms/mcp/`

### Architectural Bounds
Verify via Tach validation sweeps that creating the 4 new directories does not trigger external boundary leakage constraints.
`tach check`
