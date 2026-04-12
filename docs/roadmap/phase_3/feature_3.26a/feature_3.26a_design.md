# Design: Domain-Driven Module Consolidation

- **Feature ID**: 3.26a
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/phase_3/feature_3.26a/feature_3.26a_design.md

## Feature Overview

Feature 3.26a adds Domain-Driven Module Consolidation to the core SpecWeaver architecture. It solves the problem of flat, decoupled directories by restructuring root modules into explicit macro-domains (`workflows`, `assurance`, `workspace`, `interfaces`). It interacts meticulously with every single Python file across `src` and `tests` to update absolute import paths, and `tach.toml` to enforce boundaries, and does NOT touch the internal execution logic or behavior of the application itself. Key constraints: All 3884 tests must pass, `tach check` must be updated and pass successfully, and no information or functional implementation can be lost.

## Research Findings

### Codebase Patterns
- Currently, `src/specweaver` structure possesses a flat layout. The mapping corresponds exclusively to specific logical boundaries but doesn't denote their systemic relation.
- **Group 1 (Workflows)**: L1-L5 phases map directly into `workflows` (`drafting`, `planning`, `implementation`, `review`, and `pipelines`).
- **Group 2 (Assurance)**: Pure logic validation systems map into `assurance` (`validation`, `standards`, and topological `graph`).
- **Group 3 (Workspace)**: Physical environment representations map to `workspace` (`project`, `context`).
- **Group 4 (Interfaces)**: External system API triggers map into `interfaces` (`api`, `cli`).
- **Group 5 (Core)**: Internal state, orchestration, and executors map to `core` (`flow`, `loom`, `config`).
- **Group 6 (Infrastructure)**: External network mappings map to `infrastructure` (`llm`).

The system heavily utilizes `tach.toml` to enforce architectural imports across implicit namespace packages. Changing root folders will forcibly break all internal `import src.specweaver.<app>` syntaxes natively.

### Blueprint References
This refactoring directly reflects the `context.yaml` topological layering principles detailed in `docs/architecture/architecture_reference.md` and aligns closely with clean Domain-Driven Design (DDD). 

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Relocate L1-L5 Phases | System | Relocates directories `drafting`, `planning`, `implementation`, and `review` | Target paths reside correctly inside `src/specweaver/workflows/` |
| FR-2 | Relocate Assurance Bounds | System | Relocates pure-logic discovery `validation` and `standards` | Target paths reside correctly inside `src/specweaver/assurance/` |
| FR-3 | Relocate Workspace Bounds | System | Relocates physical project states `project` and `context` | Target paths reside correctly inside `src/specweaver/workspace/` |
| FR-4 | Relocate API Endpoint Bounds | System | Relocates exterior entry-points `cli` and `api` | Target paths reside correctly inside `src/specweaver/interfaces/` |
| FR-5 | Relocate Core Execution Suite | System | Relocates `flow`, `loom`, and `config` | Target paths reside correctly inside `src/specweaver/core/` |
| FR-6 | Relocate Infrastructure Adapters | System | Relocates the `llm` domain | Target paths reside correctly inside `src/specweaver/infrastructure/` |
| FR-7 | Mirror Unit and Integration Tests | System | Restructures `tests/unit/` and `tests/integration/` to identically match the 6 macro-domains over in `src/` | 1:1 structural parity between tests and code |
| FR-8 | Restructure E2E Test Suite | System | Restructures `tests/e2e/` from a flat tree into explicit business capability folders (by feature or story) | `tests/e2e/` map to features, not python files |
| FR-9 | Update Global Python Imports | System | Sweeps `src/` and `tests/` updating absolute Python import paths `specweaver.*` | Files natively resolve their dependencies inside the new domains |
| FR-10 | Adjust Architecture Topology Engine | System | Sweeps `tach.toml` and internal architecture graphs | Boundaries accurately describe the 6 macro-domains |
| FR-11 | Relocate Design Documents | System | Moves `docs/architecture/*` into `docs/architecture/` and permanently removes the empty `docs/proposals/design` paths | Design documents reside accurately within `architecture` |
| FR-12 | Relocate Roadmap Folder | System | Moves the entire `docs/roadmap/` directory up into `docs/roadmap/` | Project roadmap structures are cleanly elevated out of proposals |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Regression Integrity | 3,884 total test cases natively MUST pass under execution. |
| NFR-2 | Architectural Viability | `tach check` MUST yield 0 architectural domain drift validations. |
| NFR-3 | File Integrity | 0 Loss of files, configs, logic, or models during physical move (Data Retention 100%). |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Tach | Latest | `tach.toml` check | Yes | Structural constraints natively must be updated manually matching Python absolute domains. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Retain UUID UUID mapping within Tests | Prevents test regressions | No |

## Developer Guides Required

Evaluate if this feature introduces a new sub-system, paradigm, or extension layer that requires a Developer Guide for onboarding engineers.

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Architecture Bounds | Update Module Map structure inside Architecture Reference | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Domain & Documentation Realignment (File Refactoring & Path Update)
- **Scope**: Physically migrates Source directories to the 6 macro-domains, structures `tests/`, and patches all Python absolute imports in parallel. Addresses documentation moves.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-11, FR-12]
- **Inputs**: Current `src/specweaver/*` flat mapping.
- **Outputs**: 4 new macro-domains holding accurately remapped imports.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/phase_3/feature_3.26a/feature_3.26a_sf1_implementation_plan.md

### SF-2: Boundary Enforcement (Tach Matrix Matrix)
- **Scope**: Repairs the broken architectural test boundaries (Graph & Tach).
- **FRs**: [FR-10]
- **Inputs**: Updated namespace boundaries.
- **Outputs**: Valid `tach.toml` resulting in flawless `tach check` and 3884 passing execution tests.
- **Depends on**: [SF-1]
- **Impl Plan**: docs/roadmap/phase_3/feature_3.26a/feature_3.26a_sf2_implementation_plan.md

## Execution Order

1. SF-1 (No deps — Refactor file systems and strings first to repair IDE errors).
2. SF-2 (Depends on SF-1 — Locks boundary validation matrix post-file move).

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Domain File Realignment | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-2 | Boundary Matrix Sync | SF-1 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Both Implementation Plans APPROVED.
**Next step**: Start implementation for SF-1:
`/dev docs/roadmap/phase_3/feature_3.26a/feature_3.26a_sf1_implementation_plan.md`
