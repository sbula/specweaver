# Design: Structural Refactoring of Workspace AST Module

- **Feature ID**: TECH-02
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-02/TECH-02_design.md

## Feature Overview

Feature TECH-02 adds bounded context separation to the workspace component.
It solves the mixing of mechanical extraction logic (Tree-Sitter) with output mapping (Universal Graph Ontology) by introducing a dedicated `ast` sub-boundary.
It interacts with `workspace.parsers` (moving to `workspace.ast.parsers`), `workspace.ast.adapters`, and refactors imports in `assurance`, `flow`, `loom`, `llm`, and `tests` modules, and does NOT touch business logic.
Key constraints: High churn risk (touches ~85 files), MUST have 100% test suite parity, NO logic changes.

## Research Findings

### Codebase Patterns
- `workspace/ast/parsers/` contains Tree-Sitter pure-logic AST extraction engines.
- `workspace/ast/adapters/` contains `graph_adapter.py`, which maps ASTs to the Universal Graph Engine.
- The `architecture_reference.md` explicitly lists `adapters` and `pure-logic` (parsers) as distinct archetypes. Mixing them or having them float alongside discovery modules (`project`) is less cohesive than a unified `ast` boundary.
- **Reuse**: The files already exist and are fully tested. We just need to move the directories (`git mv`) and create standard `__init__.py` files.
- **Rules**: `tach.toml` currently entirely lacks boundary definitions for the parsers/adapters. We must explicitly *add* `src.specweaver.workspace.ast` to the `modules` and `[[interfaces]]` blocks.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| N/A | N/A | N/A | N/A |

### Blueprint References
None.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Relocate Parsers | System | relocates `src/specweaver/workspace/ast/parsers` to `src/specweaver/workspace/ast/parsers` | Tree-Sitter logic moves without functional changes. |
| FR-2 | Relocate Adapters | System | relocates `src/specweaver/workspace/ast/adapters` to `src/specweaver/workspace/ast/adapters` | Mapping logic moves without functional changes. |
| FR-3 | Global Import Harmonization | System | refactors all namespace imports and `context.yaml` boundaries across the codebase | All ~85 files accurately reference `specweaver.workspace.ast`. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Logic Preservation | Zero functional logic changes to extraction engines or graph mappings. |
| NFR-2 | Test Parity | 100% of existing unit, integration, and E2E tests MUST pass after refactoring. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| N/A | N/A | N/A | N/A | N/A |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Create `workspace.ast` domain | Unifies AST-related tooling under a strict boundary, isolating `adapters` and `parsers` archetypes correctly. | No |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| None | This is an internal tech-debt structural change. | N/A |

## Sub-Feature Breakdown

### SF-1: Workspace AST Directory Migration
- **Scope**: Moves `src/specweaver/workspace/ast/parsers` and `src/specweaver/workspace/ast/adapters` (along with their corresponding `tests/unit/workspace/...` directories) into the new `workspace/ast/` boundary.
- **FRs**: [FR-1, FR-2]
- **Inputs**: Existing directory structures.
- **Outputs**: Relocated source and test directories, updated `context.yaml` definitions (e.g. `name: ast.parsers`), and new explicit `tach.toml` interface boundaries.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-02/TECH-02_sf1_implementation_plan.md

### SF-2: Global Import Harmonization
- **Scope**: Updates all `context.yaml` boundaries and `.py` module imports across the codebase (`assurance`, `flow`, `loom`, `llm`, `tests`) to point to the new `workspace.ast` boundary.
- **FRs**: [FR-3]
- **Inputs**: Updated namespace boundaries from SF-1.
- **Outputs**: Mass regex search-and-replace completing the architectural decoupling.
- **Depends on**: SF-1
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-02/TECH-02_sf2_implementation_plan.md

## Execution Order

1. SF-1 (no deps — start immediately)
2. SF-2 (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Workspace AST Directory Migration | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Global Import Harmonization | SF-1 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Feature COMPLETE and committed.
**Next step**: None. This feature is done.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate workflow.
