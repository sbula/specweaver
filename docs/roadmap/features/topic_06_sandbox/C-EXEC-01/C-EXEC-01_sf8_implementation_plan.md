# Implementation Plan: Internal Layer Enforcement (Tach) [SF-8: TopologyGraph to Tach Adapter]
- **Feature ID**: 3.20a
- **Sub-Feature**: SF-8 — TopologyGraph to Tach Adapter
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-01/C-EXEC-01_design.md
- **Design Section**: §Sub-Feature Decomposition → SF-8
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-01/C-EXEC-01_sf8_implementation_plan.md
- **Status**: APPROVED

## Goal Description

Build an adapter that bridges SpecWeaver's internal topological model (`context.yaml` defined via `TopologyGraph`) into Tach's native format (`tach.toml`). When SpecWeaver maps the internal bounded contexts of a target codebase, this capability synchronizes those architectural bounds into mathematical `.toml` configuration natively checked by CI/CD.

## User Decisions (Phase 4 Audits Merged)
- **Module Placement**: Implemented in `src/specweaver/project/tach_sync.py`. The `graph/` module is strictly `pure-logic` and cannot perform File I/O. The `project/` module (`adapter` archetype) owns `.specweaver/` directory setup and filesystem orchestration, making it the architecturally correct home for writing `.toml` configuration.
- **Serialization Engine**: We will add `tomlkit` to `pyproject.toml`. Python 3.11's built-in `tomllib` is read-only, and `tomli-w` strips out developer comments. `tomlkit` safely preserves existing document formatting and comments, crucial for preserving root properties in `tach.toml`.
- **Sync Strategy**: The system will read the existing `tach.toml` file (if any) using `tomlkit`. It will preserve root definitions (e.g. `exclude = []` and `source_roots = ["."]`), but it will perform a Destructive Overwrite on the `[[modules]]` and `[[interfaces]]` mappings. The single source of truth for dependencies is `context.yaml`; thus, the `tach.toml` internal structure must exactly mirror `TopologyGraph.nodes`.
- **UX Integration**: This synchronization will be appended natively to `sw scan` inside `src/specweaver/cli/projects.py`. No new CLI flags or commands are needed. The execution mimics `scaffold.py`, returning a `TachSyncResult` to standard output indicating the modified counts.

## Proposed Changes

### Configuration
#### [MODIFY] pyproject.toml
- Add `tomlkit>=0.12.0` to the main project `dependencies` array.

### Project Module (Adapter)
#### [NEW] src/specweaver/project/tach_sync.py
Create `tach_sync.py`:
- Import `TopologyGraph` and `tomlkit`.
- Implement `sync_tach_toml(graph: TopologyGraph, project_path: Path) -> TachSyncResult`
  - Loads an existing `tach.toml` via `tomlkit.parse` if `(project_path / "tach.toml").exists()`, otherwise builds a new empty TOML document using `tomlkit.document()`.
  - Sets root elements `source_roots = ["."]` and `exact = true`.
  - Delete any existing `"modules"` or `"interfaces"` node arrays.
  - Iterate through `graph.nodes.values()`. For each `TopologyNode`:
    - Add a `[[modules]]` block: `path` maps to node Python import path logic, `depends_on` array maps exactly to `consumes`.
    - If `node.exposes` is populated, add an `[[interfaces]]` block: `from` maps to the module path, `expose` maps exactly to `exposes`.
  - Dump the document string using `tomlkit.dumps()` and overwrite `tach.toml`.
- Returns a `TachSyncResult` dataclass counting updated module paths.

#### [MODIFY] src/specweaver/project/context.yaml
- Update `consumes` array to explicitly permit `specweaver/graph`.
- Update `exposes` array to include `sync_tach_toml` and `TachSyncResult`.

### CLI Orchestrator
#### [MODIFY] src/specweaver/cli/projects.py
- Update the `scan()` Typer command.
- After all `context.yaml` auto-inference completes, build the graph: `graph = TopologyGraph.from_project(project_path)`.
- Execute the adapter: `result = sync_tach_toml(graph, project_path)`.
- Append a rich console output summarizing the synchronization (e.g. `[bold]Tach Sync[/bold]: synchronized X modules boundaries into tach.toml`).

## Verification Plan

### Automated Tests
- Create `tests/unit/project/test_tach_sync.py`:
  - Verify initialization of a raw `tach.toml` when none exists, correctly mapping a mocked `TopologyGraph`.
  - Verify deep-merge: Pass an existing `tomlkit` document containing `exclude = ["dist"]` and verify that the sync removes old modules but keeps the `exclude` root target.
- Run `pytest tests/unit/project/test_tach_sync.py` natively.
- Run E2E logic checking `import tomlkit`.

### Pre-Commit Gate
- Normal autonomous `ruff check`, `mypy` tests.
- Architecture Validation will successfully evaluate since `project/context.yaml` now officially consumes `graph`.

## Session Handoff
Feature 3.20a SF-8 Implementation complete.
