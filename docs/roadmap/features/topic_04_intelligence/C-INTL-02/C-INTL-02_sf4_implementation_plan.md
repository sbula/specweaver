# Implementation Plan: Common MCP Client Architecture [SF-4: MCP Explorer Tool]
- **Feature ID**: 3.32c
- **Sub-Feature**: SF-4 — MCP Explorer Tool
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-02/C-INTL-02_sf4_implementation_plan.md
- **Status**: DRAFT

## Goal Description
Implement the `MCPExplorerTool` inside the Agent tooling layer (`loom/tools/mcp`). It provides targeted insights into external proxy configurations mapping JSON-RPC boundaries securely, allowing the L2 Architect specifically to survey external databases or tools natively without needing manual `FileSystemTool` sweeps or massive token overheads. 

It explicitly utilizes transient `MCPExecutor` sessions to prevent persistent `npx/docker` leaks, complying with ZERO-TRUST boundaries.

## Proposed Changes

### Tool Infrastructure & Registration
#### [NEW] `src/specweaver/core/loom/tools/mcp/context.yaml`
- Defines `forbids: atoms/*` to prevent agents from leaking raw flow mechanics.
- Defines `consumes: specweaver/loom/commons/mcp` strictly mapping to the raw executor.

#### [NEW] `src/specweaver/core/loom/tools/mcp/definitions.py`
- Defines 3 JSON-Schema compliant callable definitions for the LLM:
  1. `list_servers`: Returns a simple array of valid server names from context topology.
  2. `list_resources`: Invokes JSON-RPC `resources/list` for a given server name.
  3. `read_resource`: Invokes JSON-RPC `resources/read` for a specific URI on a server.

#### [NEW] `src/specweaver/core/loom/tools/mcp/interfaces.py`
- **ArchitectMCPInterface**: The only facade exported. It uniquely registers the 3 methods above granting explicit architectural visibility ONLY to L2 agents.

#### [NEW] `src/specweaver/core/loom/tools/mcp/tool.py`
- Implements `MCPExplorerTool(BaseTool)`.
- Defines Intents: `_intent_list_servers`, `_intent_list_resources`, `_intent_read_resource`.
- Looks up target `docker run` environments from `self.context.topology.mcp_servers`.
- Rapidly spins up `MCPExecutor()`, executes the required query with a safe timeout (10s), and forcefully closes the stream before returning the JSON block to the agent.
> [!CAUTION]
> **Implementation Caveat (Q1 & Q4 Resolution)**: The `mcp/tool.py` must physically construct the `/commons/` Executor inside the `_intent` method scope using a context block or try/finally. Hard-coded 10s timeouts protect against dead servers.

### Unit Tests
#### [NEW] `tests/unit/core/loom/tools/mcp/test_tool.py`
- Mocks out the `MCPExecutor` standard interactions.
- Asserts that tools properly format `mcp_servers` topology data natively.
- Ensures the 10s latency cap cascades properly inside Error exceptions.

## Open Questions / HITL Resolutions
- **Q1/Q4 Resolved**: Transitory short-lived executors correctly deployed avoiding raw `MCPAtom` leaks. Maximum latency bound to 10s.
- **Q2 Resolved**: Both `list` and `read` intents are safely enabled inside the tool for the Architect agent mapping.
- **Q3 Resolved**: Expanded upon the original design. An independent `list_servers` intent method handles local topology checks natively, removing the architectural LLM burden of guessing.

## Verification Plan

### Automated Tests
1. `pytest tests/unit/core/loom/tools/mcp/test_tool.py` natively running bounds testing.
2. `uv run python scripts/check_file_sizes.py`
3. `tach check` to ensure internal boundary containment prevents Agent leakages.
