# Design: Context Loading Pipeline Refactoring

- **Feature ID**: TECH-006
- **Phase**: Technical Debt
- **Status**: APPROVED
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_design.md

> [!IMPORTANT]
> **Direction update (2026-07-21, middle-way review):** the core of this design (delete misplaced CLI-layer
> helpers, call public Domain APIs, untangle the cross-interface spider-web) remains fully valid and
> compatible. However, any follow-up that would centralize constitution/standards **content loading inside
> the prompt factory** (the topic-doc "Highest-ROI" row) is **redirected**: under `C-INTL-06`
> (Envelope-vs-Content) + `C-FLOW-11` (agentic work units read mounted files), the destination is **domain
> loaders + canonical on-disk files** shared by both execution modes — not deeper factory centralization.

## Feature Overview

Feature TECH-006 eliminates **5 misplaced private helper functions** (in 2 copies = 6 total) from the CLI interface layer. These functions contain domain logic, infrastructure wiring, or string-dispatched repository calls that have nothing to do with the CLI. Because they are in the wrong layer, the REST API and 10+ CLI modules import them cross-interface, creating a massive spider web of forbidden boundary violations — including the REST API depending on the CLI. The fix: delete all 6 function definitions and replace them with direct calls to existing public Domain APIs. Key constraints: full backward compatibility, zero new modules, `tach check` compliance.

## Research Findings

### The 5 Functions To Delete (6 definitions)

| # | Function | Lives in (WRONG) | Why it's wrong | Replacement |
|---|----------|-----------------|----------------|-------------|
| 1 | `_load_constitution_content` | `workspace/project/interfaces/cli.py` | 2-line wrapper around existing domain API | Inline `find_constitution()` from `workspace/project/constitution.py` |
| 2 | `_load_standards_content` | `assurance/standards/interfaces/cli.py` | Wrapper that calls CLI singletons, then delegates to domain API | Direct `load_standards_content()` / `load_standards_content_async()` from `assurance/standards/loader.py` |
| 3 | `_require_llm_adapter` | `infrastructure/llm/interfaces/cli.py` | Wrapper around `load_settings()` + `create_llm_adapter()` with `typer.Exit` and a hardcoded fallback (`api_key="test-key"`) | Direct `load_settings()` + `create_llm_adapter()`. Hardcoded fallback is deliberately killed (security risk). |
| 4a | `_run_workspace_op` | `workspace/project/interfaces/cli.py` | String-dispatched generic sync wrapper. Not type-safe, not grep-friendly, not refactor-safe. | New typed `run_repo_op()` in `interfaces/cli/_core.py` |
| 4b | `_run_workspace_op` (DUPLICATE) | `core/config/interfaces/cli.py` | Second copy of the same anti-pattern | Same — replaced by `_core.run_repo_op()` |
| 5 | `_load_topology` + `_select_topology_contexts` | `graph/interfaces/cli.py` | Domain logic mixed with `console.print` output. Called by API endpoint (silent bug — Rich prints to nowhere). | New public facade in `assurance/graph/` |

### `_run_workspace_op` Replacement: Typed `run_repo_op()`

The string-dispatched `_run_workspace_op` cannot be replaced by inlining 5 lines × 20 call sites (that's 100 lines of boilerplate — a worse DRY violation). Instead, a **typed** replacement is added to `interfaces/cli/_core.py`:

```python
def run_repo_op(fn: Callable[[WorkspaceRepository], Awaitable[T]]) -> T:
    """Run a typed WorkspaceRepository operation synchronously (CLI only)."""
    db = get_db()
    async def _action() -> T:
        async with db.async_session_scope() as session:
            return await fn(WorkspaceRepository(session))
    return anyio.run(_action)
```

Call sites become type-safe one-liners:
```python
# Before (string dispatch, not type-safe):
active = _run_workspace_op("get_active_project")
proj = _run_workspace_op("get_project", name)

# After (typed lambda, IDE autocomplete, grep-friendly):
active = _core.run_repo_op(lambda r: r.get_active_project())
proj = _core.run_repo_op(lambda r: r.get_project(name))
```

### Cross-Interface Spider Web (complete violation count)

**`_load_constitution_content`** — 5 cross-interface imports (3 CLI + 2 API 🚨):
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`
- `interfaces/api/v1/review.py` 🚨, `interfaces/api/v1/implement.py` 🚨

**`_load_standards_content`** — 3 cross-interface imports:
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`

**`_require_llm_adapter`** — 4 cross-interface imports:
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`, `assurance/validation/interfaces/cli_drift.py`

**`_run_workspace_op`** — 6 cross-domain imports + 1 duplicate definition:
- **Definition 1** (workspace): `interfaces/cli/_core.py`, `interfaces/cli/main.py`, `infrastructure/llm/interfaces/cli.py`, `graph/interfaces/cli.py`, `assurance/validation/interfaces/cli.py`, `assurance/standards/interfaces/cli.py`
- **Definition 2** (config): used internally by `core/config/interfaces/cli.py`

**`_load_topology` / `_select_topology_contexts`** — 4 cross-interface imports (3 CLI + 1 API 🚨):
- `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`
- `interfaces/api/v1/implement.py` 🚨

**Total: 23 cross-interface import violations + 1 duplicate definition eliminated.**

### Blueprint References
- `docs/architecture/07_architectural_decision_records/adr_002_composition_root_vs_factories.md` — Confirms Composition Root stays at the Entry Point. TECH-009 was evaluated and cancelled.

## Functional Requirements

| # | FR | Action | Outcome |
|---|-----|--------|---------|
| FR-1 | Delete `_load_constitution_content` | Replace all 5 imports with inline `find_constitution()` calls | Zero cross-interface constitution imports |
| FR-2 | Delete `_load_standards_content` | Replace all 3 imports with direct `load_standards_content()` / `load_standards_content_async()` calls, passing `db` and `project_name` explicitly | Standards loading decoupled from CLI singletons |
| FR-3 | Delete `_require_llm_adapter` | Replace all 4 imports with direct `load_settings()` + `create_llm_adapter()` calls. Each CLI caller handles its own errors via `typer.Exit`. Hardcoded fallback (`api_key="test-key"`) is deliberately killed — security risk. | LLM wiring decoupled from CLI |
| FR-4 | Delete both copies of `_run_workspace_op` | Add typed `run_repo_op()` to `interfaces/cli/_core.py`. Replace all ~20 call sites across 8 modules with `_core.run_repo_op(lambda r: r.method())` (type-safe, grep-friendly, 1 line per call) | String-dispatch anti-pattern eliminated. Duplicate definition deleted. |
| FR-5 | Delete `_load_topology` + `_select_topology_contexts` | Add a small public facade in `assurance/graph/` for topology loading + selector execution. Replace all 4 imports. Remove `console.print` from domain logic. | Topology logic moved to domain layer. API silent-print bug fixed. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Compatibility | The refactoring SHALL NOT break any existing CLI commands or API endpoints. |
| NFR-2 | Architecture | The refactoring SHALL pass `tach check` with zero boundary violations. |
| NFR-3 | Architecture | No interface module SHALL import private helpers from another interface module. |
| NFR-4 | Architecture | No API module SHALL import from any CLI module. |
| NFR-5 | Minimal new code | Only 2 new public functions: `run_repo_op()` in `_core.py` and a topology facade in `assurance/graph/`. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Delete all 5 CLI wrappers (6 definitions) | Domain logic doesn't belong in the interface layer. Public APIs already exist. | No |
| AD-2 | Replace `_run_workspace_op` with typed `run_repo_op()` | Eliminates string-dispatch anti-pattern. Keeps DRY (1 helper, not 20 inlined copies). Type-safe, grep-friendly, IDE autocomplete. | No |
| AD-3 | Kill hardcoded LLM fallback | `api_key="test-key"` is a security risk and a silent behavior change. Proper error handling replaces it. | No |
| AD-4 | Add topology facade in `assurance/graph/` | Only function where the public API doesn't fully exist yet. Small facade wrapping `TopologyGraph.from_project()` + selector logic. | No |

## Sub-Feature Breakdown

### SF-01: Delete All CLI Wrappers (Single Atomic Commit)
- **Scope**: Delete all 6 function definitions. Replace all 23 import sites. Add `run_repo_op()` to `_core.py`. Add topology facade to `assurance/graph/`. One atomic commit — all files touched in one pass to avoid merge conflicts.
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5]
- **Affected files** (~15 files):
  - **Delete from**: `workspace/project/interfaces/cli.py`, `assurance/standards/interfaces/cli.py`, `infrastructure/llm/interfaces/cli.py`, `graph/interfaces/cli.py`, `core/config/interfaces/cli.py`
  - **Update imports**: `core/flow/interfaces/cli.py`, `workflows/review/interfaces/cli.py`, `workflows/implementation/interfaces/cli.py`, `assurance/validation/interfaces/cli.py`, `assurance/validation/interfaces/cli_drift.py`, `interfaces/api/v1/review.py`, `interfaces/api/v1/implement.py`, `interfaces/cli/_core.py`, `interfaces/cli/main.py`
  - **Add to**: `interfaces/cli/_core.py` (run_repo_op), `assurance/graph/` (topology facade)
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_sf01_implementation_plan.md

## Execution Order

1. SF-01 — single atomic commit covering all 5 functions.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Delete All CLI Wrappers | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Impl Plan APPROVED — ready for development.
**Next step**: Run `/dev docs/roadmap/features/topic_07_technical_debt/TECH-006/TECH-006_sf01_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
