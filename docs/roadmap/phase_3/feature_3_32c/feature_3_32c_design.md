# Design: Common MCP Client Architecture

- **Feature ID**: 3.32c
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3_32c/feature_3_32c_design.md

## Feature Overview

Feature 3.32c adds a Common MCP Client Architecture to the workspace context provider.
It solves the need for external infrastructure schemas by establishing a standardized JSON-RPC over `stdio` protocol engine.
It interacts with `context.yaml`, the `TopologyGraph`, and `ContextAssembler`, and does NOT touch SpecWeaver validation logic or downstream domain engines.
Key constraints: Must use the Pre-Fetched Context Envelope pattern to avoid System Prompt token saturation; must restrict native `npx` execution securely.

## Research Findings

### Codebase Patterns
- **Reusability**: `src/specweaver/workspace/context/provider.py` already defines a `ContextProvider` abstract layer that can be extended for MCP standard hooks.
- **Boundaries**: All integrations must be driven natively by the `context.yaml` boundaries.
- **Constraints**: Mandated isolated process execution to prevent Zombie database connections.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| Model Context Protocol | 1.0.0 | JSON-RPC Client over Stdio | Anthropic |

### Blueprint References
- Reference Architecture completed manually via Red-Team investigation in `docs/architecture/mcp_architecture_design.md`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Parse Constraints | Workspace Parser | Read the `mcp_servers` block from `context.yaml`. | System extracts remote execution targets. |
| FR-2 | Execute Stdio | Context Assembler | Boot external MCP server using `docker run -i --rm`. | System establishes a JSON-RPC pipeline over `stdio`. |
| FR-3 | Pre-Fetch Context | Context Assembler | Submit `read_mcp_resource` JSON-RPC requests per the boundary `consumes_resources` array. | Extracts accurate schema string states from the external MCP. |
| FR-4 | Inject Envelope | LLM Adapter | Inject the serialized context strings into the `<environment_context>` prompt block. | Provides zero-latency reality checkpoints directly to the agent prompt. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Token Bloat Prevention | Must explicitly use the Pre-Fetch Resource pattern. Forbid global tool injection into LLM prompts. |
| NFR-2 | Process Isolation | MCP Executions MUST run through Docker via `docker run -i --rm` (No bare CLI Node.js execution). |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Docker | v20+ | `docker run -i --rm` | Y | Standard platform prerequisite. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Pre-Fetched Envelopes | Eliminates tool-call LLM latency and token bloat | No |
| AD-2 | Docker Mandate | Solves RCE & Node zombie connection exhaustion | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| MCP Implementation | Guide on structuring `context.yaml` MCP injections. | ⚪ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Context YAML & Vault Bindings
- **Scope**: Updates the Pydantic boundary schema to seamlessly accept `mcp_servers` mappings and dynamic `.specweaver/vault.env` token replacement.
- **FRs**: [FR-1]
- **Inputs**: `context.yaml`
- **Outputs**: Updated Boundary config models
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3_32c/feature_3_32c_sf1_implementation_plan.md

### SF-2: MCP Execution Atom (Loom Layer)
- **Scope**: Implements the raw subprocess connection logic bridging JSON-RPC via `stdio` inside `loom/commons/mcp/executor.py` and exposes it via `loom/atoms/mcp/atom.py` to strictly adhere to the `context.yaml` isolation boundaries.
- **FRs**: [FR-2]
- **Inputs**: Docker launch command
- **Outputs**: active JSON-RPC Atom connection
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/phase_3/feature_3_32c/feature_3_32c_sf2_implementation_plan.md

### SF-3: The Pre-Fetch Assembler (Flow Engine)
- **Scope**: Implements the context extraction logic inside `flow/handlers.py` (which is legally permitted to execute Atoms). Identifies `consumes_resources`, executes the `MCPAtom` pre-fetch, and binds the envelope to the LLM step config.
- **FRs**: [FR-3, FR-4]
- **Inputs**: `MCPAtom`, `consumes_resources` array.
- **Outputs**: Injected Context Envelope.
- **Depends on**: SF-2
- **Impl Plan**: docs/roadmap/phase_3/feature_3_32c/feature_3_32c_sf3_implementation_plan.md

### SF-4: MCP Explorer Tool (Architect Layer)
- **Scope**: Implements `MCPExplorerTool` in `loom/tools/mcp/tool.py`, exposing the MCP `resources/list` endpoint strictly to L2 Architect roles, allowing them to map available URIs to `context.yaml` dependencies without seeing heavy schemas.
- **FRs**: [FR-1]
- **Inputs**: MCP URIs, Agent queries
- **Outputs**: Lightweight array of available URIs
- **Depends on**: SF-2
- **Impl Plan**: docs/roadmap/phase_3/feature_3_32c/feature_3_32c_sf4_implementation_plan.md

## Execution Order

1. SF-1 (Boundary schemas updates)
2. SF-2 (Stdio connection logic)
3. SF-3 and SF-4 in parallel (Assembler string injection & Explorer Tool)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Context YAML & Vault Bindings | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | MCP Execution Atom | SF-1 | ✅ | ✅ | ⚪ | ⚪ | ⚪ |
| SF-3 | The Pre-Fetch Assembler | SF-2 | ✅ | ⚪ | ⚪ | ⚪ | ⚪ |
| SF-4 | MCP Explorer Tool | SF-2 | ✅ | ⚪ | ⚪ | ⚪ | ⚪ |

## Session Handoff

**Current status**: SF-2 IMPL PLAN APPROVED!
**Next step**: Run:
`/dev docs/roadmap/phase_3/feature_3_32c/feature_3_32c_sf2_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⚪ in any row and resume from there using the appropriate workflow.
