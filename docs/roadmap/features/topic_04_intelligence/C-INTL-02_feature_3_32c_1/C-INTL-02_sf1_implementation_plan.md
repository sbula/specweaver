# Implementation Plan: External DB Context Harness [SF-1: MCP Scaffold Templates & Vault integration]
- **Feature ID**: 3.32c-1
- **Sub-Feature**: SF-1 — MCP Scaffold Templates & Vault integration
- **Design Document**: docs/roadmap/features/topic_04_intelligence/C-INTL-02_feature_3_32c_1/C-INTL-02_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/C-INTL-02_feature_3_32c_1/C-INTL-02_sf1_implementation_plan.md
- **Status**: COMPLETED

## Goal Description
Implement the scaffold bootstrapping and structural boundary limits for the first Model Context Protocol external extension. We will overload the `sw init` command to support `--mcp <type>` bindings, generate standard bare-metal node:20 templates for a Postgres adapter, securely route credentials via a local `.specweaver/vault.env`, and inject scrubbing filters at the `MCPAtom.run()` execution boundary to satisfy FR-3 Telemetry masking constraints without causing global log performance bottlenecks.

## Proposed Changes

### `src/specweaver/interfaces/cli/`
#### [MODIFY] [projects.py](file:///c:/development/pitbula/specweaver/src/specweaver/interfaces/cli/projects.py)
- **`init()`**:
  - Inject parameter: `mcp: str | None = typer.Option(None, "--mcp", help="Scaffold MCP boundary (e.g., 'postgres')")`
  - Update execution flow to pass `mcp` into `scaffold_project(project_path, mcp_target=mcp)`.

### `src/specweaver/workspace/project/`
#### [MODIFY] [scaffold.py](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/project/scaffold.py)
- **`scaffold_project()`**:
  - Add signature `mcp_target: str | None = None`.
  - Introduce `_scaffold_mcp_postgres(project_path: Path, created: list[str])`.
  - Introduce `_scaffold_vault_file(sw_dir: Path, created: list[str])`.
  - Add explicit append payload into `.gitignore` (native file) explicitly mapping `.specweaver/vault.env`.

> [!CAUTION]
> Scaffold idempotent operations must ensure `vault.env` keys are never overwritten if the file already exists locally.

### `src/specweaver/core/loom/atoms/mcp/`
#### [MODIFY] [atom.py](file:///c:/development/pitbula/specweaver/src/specweaver/core/loom/atoms/mcp/atom.py)
- **`run()` overrides**:
  - Implement a `_scrub_telemetry()` block wrapping the `self._executor.call_rpc` yields.
  - Iterate over `self._env.values()` (which holds injected `vault.env` payloads). Any non-trivial value (e.g., >8 chars) mapping exactly to an injected vault secret is mapped to `***RESTRICTED***` before returning the dictionary payload to the logging layer.

## Pre-Requisite Templates
This sequence defines what gets generated when `sw init --mcp postgres` fires:

#### `.specweaver/vault.env`
```env
# Secure Vault - Explicitly excluded from source control tracking.
# MCP Target: Postgres
# Injected automatically into the MCP runner bounds.

# NFR-2 CONSTRAINT: Ensure POSTGRES_USER is a restricted read-only account.
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
```

#### `.specweaver_mcp/postgres/context.yaml`
```yaml
name: mcp-postgres
level: internal
purpose: Dynamic Schema Context Adapter via MCP 
archetype: orchestrator
consumes: []
forbids: []
command:
  - "docker"
  - "run"
  - "--rm"
  - "-i"
  - "--env-file"
  - ".specweaver/vault.env"
  - "node:20"
  - "npx"
  - "-y"
  - "@modelcontextprotocol/server-postgres"
  - "postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@host.docker.internal/${POSTGRES_DB}"
```

> [!NOTE] 
> Because we are bypassing `docker build` constraints, variables in the command manifest array must be string-templated properly by the execution abstraction or shell expanded.

## Verification Plan
### Automated Tests
- Unit Test `scaffold.py` ensuring `vault.env` is idempotent and `.gitignore` applies correctly.
- Unit Test `atom.py` verifying synthetic vault scrub lists replace matching strings exactly in RPC return packets.
- Integration Test `projects.py` asserting `sw init --mcp postgres` drops the expected file tree accurately.

### Manual Verification
- `uv run sw init dummy-db --mcp postgres` → Check physical outputs on disk.
- Look at `specweaver.log` specifically examining `MCPAtom` RPC events; verify no passwords leak into raw text.
