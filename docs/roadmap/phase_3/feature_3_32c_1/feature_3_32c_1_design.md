# Design: External DB Context Harness

- **Feature ID**: 3.32c-1
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3_32c_1/feature_3_32c_1_design.md

## Feature Overview

Feature 3.32c-1 adds an External DB Context Harness mapping to live databases via Model Context Protocol.
It solves database schema hallucination by providing a reference Docker MCP implementation that securely extracts schemas.
It interacts purely with the 3.32c ContextAssembler and requires zero modifications to native Python code.
Key constraints: MCP servers MUST run in ephemeral Docker configurations mapped natively in `context.yaml`; passwords must be injected dynamically via `.specweaver/vault.env`.

## Research Findings

### Codebase Patterns
- This feature is a **Structural Harness** built on top of 3.32c. It requires zero core python code changes, and instead consists of `scaffold` templates for bootstrapping repositories with `.specweaver_mcp/` directories.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| `@modelcontextprotocol/server-postgres` | 1.0 | Official Postgres adapter | npm |

### Blueprint References
- Details established in `docs/architecture/mcp_architecture_design.md`.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Scaffold Template | Developer | Run `sw init --mcp postgres` | Generates a boilerplate `.specweaver_mcp/postgres/` tree and automatically appends `.specweaver/vault.env` to the project's `.gitignore`. |
| FR-2 | Credentials Vault | SpecWeaver Engine | Read `.specweaver/vault.env` | Injects valid Postgres connection strings dynamically avoiding `.git` tracking. |
| FR-3 | Telemetry Scrubbing | MCP Atom | Log MCP command telemetry | Scans all emitted logs, audit messages, and Datadog traces, replacing any resolved vault strings with `***RESTRICTED***` to prevent credential leaking. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Zero Native Python Coupling | DB code cannot enter SpecWeaver's core layer. |
| NFR-2 | Least Privilege | Server must explicitly be documented to use a restricted Postgres User. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Database Driver | Any | N/A | Y | Handled natively by external Docker container. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Scaffold-based delivery | Prevents vendor lock-in for DB drivers within the orchestrator | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Setup your Project DB Harness | Instructions on read-only DB permissions and `vault.env` configuration. | ⚪ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: MCP Scaffold Templates & Telemetry Vault
- **Scope**: Implements the `sw init` template expansion to drop local MCP servers, rewrite `.gitignore` constraints, and intercept telemetry payloads to mask injected environment secrets.
- **FRs**: [FR-1, FR-2, FR-3]
- **Inputs**: CLI template config, executing Subprocesses
- **Outputs**: Masked log streams, Local user repo skeleton
- **Depends on**: Feature 3.32c implementation
- **Impl Plan**: docs/roadmap/phase_3/feature_3_32c_1/feature_3_32c_1_sf1_implementation_plan.md

## Execution Order

1. SF-1 (Scaffold templating)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | MCP Scaffold Templates & Vault integration | — | ✅ | ⚪ | ⚪ | ⚪ | ⚪ |

## Session Handoff

**Current status**: Design APPROVED!
**Next step**: Run:
`/implementation-plan docs/roadmap/phase_3/feature_3_32c_1/feature_3_32c_1_design.md SF-1`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⚪ in any row and resume from there using the appropriate workflow.
