# C-INTL-02 SF-04 — MCP Explorer Tool

**Status**: DRAFT · **Feature ID**: 3.32c · **FRs owned**: FR-1 · **Depends on**: SF-02 · Design:
[C-INTL-02_design.md](C-INTL-02_design.md) §Sub-features → SF-04

## Goal

`MCPExplorerTool` in the agent tooling layer (`loom/tools/mcp`). Lets the L2 Architect survey
external databases or tools through their JSON-RPC proxies — no manual `FileSystemTool` sweeps, no
large token cost.

Each call uses a transient `MCPExecutor` session, so no `npx/docker` process outlives it
(ZERO-TRUST boundaries).

## Changes

1. [NEW] `src/specweaver/core/loom/tools/mcp/context.yaml` — `forbids: atoms/*` (agents never touch
   flow mechanics); `consumes: specweaver/loom/commons/mcp` (the raw executor only).
2. [NEW] `src/specweaver/core/loom/tools/mcp/definitions.py` — 3 JSON-Schema tool definitions:
   1. `list_servers`: server names from the context topology.
   2. `list_resources`: JSON-RPC `resources/list` for a server name.
   3. `read_resource`: JSON-RPC `resources/read` for one URI on a server.
3. [NEW] `src/specweaver/core/loom/tools/mcp/interfaces.py` — `ArchitectMCPInterface`, the only
   exported facade; registers the 3 methods for L2 agents only.
4. [NEW] `src/specweaver/core/loom/tools/mcp/tool.py` — `MCPExplorerTool(BaseTool)`:
   - Intents `_intent_list_servers`, `_intent_list_resources`, `_intent_read_resource`.
   - Reads the `docker run` targets from `self.context.topology.mcp_servers`.
   - Starts an `MCPExecutor()`, runs the query with a 10s timeout, closes the stream, returns the
     JSON block.

> [!CAUTION]
> **Q1 & Q4**: `mcp/tool.py` constructs the `/commons/` Executor inside the `_intent` method scope,
> in a context block or try/finally. The hard-coded 10s timeout protects against dead servers.

## Tests

| File | Case |
|---|---|
| [NEW] `tests/unit/core/loom/tools/mcp/test_tool.py` | `MCPExecutor` mocked · `mcp_servers` topology data formatted correctly · the 10s timeout surfaces as an error |

Commands: `pytest tests/unit/core/loom/tools/mcp/test_tool.py`;
`uv run python scripts/check_file_sizes.py`; `tach check` (no agent leakage across boundaries).

## Decisions (audit)

| # | Resolution |
|---|---|
| Q1/Q4 | Short-lived executors, no raw `MCPAtom` exposure. Latency capped at 10s. |
| Q2 | Both `list` and `read` intents enabled for the Architect agent. |
| Q3 | Beyond the design: a `list_servers` intent answers from local topology, so the LLM does not guess server names. |

## As built

**Since moved** (2026-09-25 check): built in `sandbox/mcp/interfaces/` — `tool.py`
(`MCPExplorerTool`), `facades.py` (`ArchitectMCPInterface`, `create_mcp_interface`),
`definitions.py`; test `tests/unit/sandbox/mcp/interfaces/mcp/test_mcp_tool.py`. The Status line
above was never updated.
