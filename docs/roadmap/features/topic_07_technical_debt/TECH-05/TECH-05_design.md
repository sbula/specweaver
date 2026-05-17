# Design: Context Loading Pipeline Refactoring

- **Feature ID**: TECH-05
- **Phase**: Technical Debt
- **Status**: DRAFT
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-05/TECH-05_design.md

## Feature Overview

Feature TECH-05 eliminates **5 misplaced private helper functions** from the CLI interface layer. These functions contain domain logic, infrastructure wiring, or string-dispatched repository calls that have nothing to do with the CLI. Because they are in the wrong layer, the REST API and 10+ CLI modules import them cross-interface, creating a massive spider web of forbidden boundary violations — including the REST API depending on the CLI. The fix: delete all 5 functions. The public Domain APIs already exist. Each caller calls them directly. Key constraints: full backward compatibility, zero new modules, `tach check` compliance.

## Research Findings

### The 5 Functions To Delete

| # | Function | Lives in (WRONG) | Why it's wrong | Replacement (already exists) |
|---|----------|-----------------|----------------|------------------------------|
| 1 | `_load_constitution_content` | `workspace/project/interfaces/cli.py` | 2-line wrapper around existing domain API | `find_constitution()` in `workspace/project/constitution.py` |
| 2 | `_load_standards_content` | `assurance/standards/interfaces/cli.py` | Wrapper that calls CLI singletons, then delegates to domain API | `load_standards_content()` / `load_standards_content_async()` in `assurance/standards/loader.py` |
| 3 | `_require_llm_adapter` | `infrastructure/llm/interfaces/cli.py` | Wrapper around `load_settings()` + `create_llm_adapter()` with `typer.Exit` error handling | `load_settings()` in `core/config/settings_loader.py` + `create_llm_adapter()` in `infrastructure/llm/factory.py` |
| 4 | `_run_workspace_op` | `workspace/project/interfaces/cli.py` | String-dispatched generic sync wrapper. Not type-safe, not grep-friendly, not refactor-safe. Zero user-facing value. | Each caller writes explicit `anyio.run()` + `WorkspaceRepository` calls (3 lines, type-safe) |
| 5 | `_load_topology` + `_select_topology_contexts` | `graph/interfaces/cli.py` | Domain logic (TopologyGraph building, selector execution) mixed with `console.print` output | `TopologyGraph.from_project()` in `assurance/graph/topology.py` + selector logic in `assurance/graph/selectors.py`. A small public facade function will be added. |

### Cross-Interface Spider Web (complete violation count)

**`_load_constitution_content`** — 5 cross-interface imports (3 CLI + 2 API 🚨):
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`
- `interfaces/api/v1/review.py` 🚨, `interfaces/api/v1/implement.py` 🚨

**`_load_standards_content`** — 3 cross-interface imports:
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`

**`_require_llm_adapter`** — 4 cross-interface imports:
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`, `assurance/validation/interfaces/cli_drift.py`

**`_run_workspace_op`** — 6 cross-domain imports:
- `interfaces/cli/_core.py`, `interfaces/cli/main.py`, `infrastructure/llm/interfaces/cli.py`, `graph/interfaces/cli.py`, `assurance/validation/interfaces/cli.py`, `assurance/standards/interfaces/cli.py`

**`_load_topology` / `_select_topology_contexts`** — 4 cross-interface imports (3 CLI + 1 API 🚨):
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`
- `interfaces/api/v1/implement.py` 🚨

**Total: 22 cross-interface import violations eliminated.**

### Blueprint References
- `docs/architecture/07_architectural_decision_records/adr_002_composition_root_vs_factories.md` — Confirms Composition Root stays at the Entry Point. TECH-08 was evaluated and cancelled.

## Functional Requirements

| # | FR | Action | Outcome |
|---|-----|--------|---------|
| FR-1 | Delete `_load_constitution_content` | Replace all 5 imports with inline `find_constitution()` calls | Zero cross-interface constitution imports |
| FR-2 | Delete `_load_standards_content` | Replace all 3 imports with direct `load_standards_content()` / `load_standards_content_async()` calls, passing `db` and `project_name` explicitly | Standards loading decoupled from CLI singletons |
| FR-3 | Delete `_require_llm_adapter` | Replace all 4 imports with direct `load_settings()` + `create_llm_adapter()` calls. Each CLI caller handles its own errors via `typer.Exit`. Remove the hardcoded fallback. | LLM wiring decoupled from CLI |
| FR-4 | Delete `_run_workspace_op` | Replace all ~20 call sites with explicit `anyio.run()` + `WorkspaceRepository` calls (3 lines per site, type-safe, grep-friendly) | String-dispatch anti-pattern eliminated |
| FR-5 | Delete `_load_topology` + `_select_topology_contexts` | Add a small public facade in `assurance/graph/` for topology loading + selector execution. Replace all 4 imports with calls to the new facade. Remove `console.print` from domain logic. | Topology logic moved to domain layer |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Compatibility | The refactoring SHALL NOT break any existing CLI commands or API endpoints. |
| NFR-2 | Architecture | The refactoring SHALL pass `tach check` with zero boundary violations. |
| NFR-3 | Architecture | No interface module SHALL import private helpers from another interface module. |
| NFR-4 | Architecture | No API module SHALL import from any CLI module. |
| NFR-5 | No new modules | Zero new packages or `tach.toml` entries (except the small topology facade in `assurance/graph/`). |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Delete all 5 CLI wrappers | Domain logic doesn't belong in the interface layer. Public APIs already exist. | No |
| AD-2 | Delete `_run_workspace_op` entirely | String-dispatched generic wrapper is not type-safe, not grep-friendly, not refactor-safe. Zero user benefit. Each caller writes explicit async calls. | No |
| AD-3 | Add topology facade in `assurance/graph/` | Only function where the public API doesn't fully exist yet. Small facade wrapping `TopologyGraph.from_project()` + selector logic. | No |

## Sub-Feature Breakdown

### SF-01: Delete Constitution + Standards + LLM Wrappers
- **Scope**: Delete `_load_constitution_content`, `_load_standards_content`, and `_require_llm_adapter`. Update all 12 import sites to use existing public Domain APIs directly.
- **FRs**: [FR-1, FR-2, FR-3]
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-05/TECH-05_sf01_implementation_plan.md

### SF-02: Delete `_run_workspace_op`
- **Scope**: Delete the string-dispatched wrapper. Replace all ~20 call sites across 8 modules with explicit type-safe `anyio.run()` + `WorkspaceRepository` calls.
- **FRs**: [FR-4]
- **Depends on**: none (can run in parallel with SF-01)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-05/TECH-05_sf02_implementation_plan.md

### SF-03: Delete Topology CLI Wrappers
- **Scope**: Add a small public facade in `assurance/graph/`. Delete `_load_topology` and `_select_topology_contexts` from `graph/interfaces/cli.py`. Update 4 import sites. Remove `console.print` from domain logic.
- **FRs**: [FR-5]
- **Depends on**: none (can run in parallel)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-05/TECH-05_sf03_implementation_plan.md

## Execution Order

All 3 SFs are independent — they can run in any order or in parallel. Recommended sequence for minimal merge conflicts:
1. SF-01 (highest ROI — kills the API→CLI violations)
2. SF-02 (highest volume — ~20 call sites)
3. SF-03 (moderate — needs new facade function)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Delete Constitution/Standards/LLM Wrappers | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-02 | Delete `_run_workspace_op` | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | Delete Topology CLI Wrappers | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: Design DRAFT — awaiting HITL approval.
**Next step**: After approval, run:
`/implementation-plan docs/roadmap/features/topic_07_technical_debt/TECH-05/TECH-05_design.md SF-01`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
