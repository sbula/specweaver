# TECH-05: Context Loading Pipeline Refactoring

- **Feature ID**: TECH-05
- **Phase**: N/A (Technical Debt)
- **Status**: 🔴 PENDING
- **Discovered during**: D-INTL-06 Red Team Cycle 4 pattern analysis
- **Dependency**: D-INTL-06 SF-2 (Prompt Factory) for highest-ROI refactoring

## Goal

Eliminate three interrelated anti-patterns in the context loading pipeline that compound as new context sources are added. The refactoring cleans up architectural boundary violations that have accumulated organically as features were added to the pre-Factory codebase.

## Background

During the D-INTL-06 Red Team analysis, the existing `constitution` and `standards` loading pattern was examined as a potential model for memory hydration. The analysis revealed that this pattern itself contains multiple architectural violations that D-INTL-06 deliberately avoids. These should be fixed to prevent future features from copying the flawed pattern.

## Finding 1: Business Logic in Interface/CLI Layers

**Current State:**
- `_load_constitution_content()` — defined in `workspace/project/interfaces/cli.py` (line 328). A 3-line wrapper around `find_constitution()` which already exists in `workspace/project/constitution.py`.
- `_load_standards_content()` — defined in `assurance/standards/interfaces/cli.py` (line 448). Calls `load_standards_content()` from `assurance/standards/loader.py` but also calls `_core.get_db()`, coupling it to the CLI singleton.

**Problem:** These are data loading utilities, not CLI commands. Interface layers should be thin adapter shells that translate user input into domain calls. Placing reusable logic in the interface layer forces other modules to import from it, creating cross-boundary violations.

**Fix:** Move the logic into the domain layer:
- `_load_constitution_content()` → inline into callers (it's just `find_constitution().content`)
- `_load_standards_content()` → refactor `load_standards_content()` in `assurance/standards/loader.py` to accept `db` as a parameter instead of calling `_core.get_db()`

**Effort:** Low (~30 min each)

## Finding 2: Cross-Interface Spider Web (10+ violations)

**Current State:** These private (`_` prefixed) helpers are imported across unrelated interface modules:

| Private Helper | Defined In | Imported By |
|---|---|---|
| `_load_constitution_content` | `workspace/project/interfaces/cli.py` | `flow/interfaces/cli.py`, `review/interfaces/cli.py`, `implementation/interfaces/cli.py`, `api/v1/implement.py`, `api/v1/review.py` |
| `_load_standards_content` | `assurance/standards/interfaces/cli.py` | `flow/interfaces/cli.py`, `review/interfaces/cli.py`, `implementation/interfaces/cli.py` |
| `_run_workspace_op` | `workspace/project/interfaces/cli.py` | `assurance/standards/interfaces/cli.py`, `assurance/validation/interfaces/cli.py`, `graph/interfaces/cli.py`, `infrastructure/llm/interfaces/cli.py`, `interfaces/cli/main.py`, `interfaces/cli/_core.py` |

**Problem:** None of these are in any module's `exposes` list. The `_` prefix conventionally marks them as private. Yet they form a dependency spider web across 10+ unrelated interface modules. This violates the architectural principle that interface modules should only import from their parent domain's public API.

**Fix:** After Finding 1 is resolved (logic moved to domain layer), the cross-imports naturally disappear. For `_run_workspace_op`, extract to a shared utility in `workspace/` (public API) or replace with direct `WorkspaceRepository` usage.

**Effort:** Medium (~2h, dependent on Finding 1)

## Finding 3: RunContext God Object (23 fields)

**Current State:** `RunContext` in `core/flow/handlers/base.py` has 23 fields:
```
project_path, spec_path, llm, context_provider, topology, settings,
config, analyzer_factory, output_dir, feedback, constitution, standards,
plan, workspace_roots, api_contract_paths, db, llm_router,
project_metadata, pipeline_runner, run_id, step_records, env_vars,
pipeline_name, dal_level, stale_nodes, parsers
```

Its `model_post_init` is 67 lines of side-effect-heavy initialization (parser injection, project metadata assembly from `platform`, `sys`, YAML parsing).

**Problem:** Classic God Object / grab-bag. Every feature adds a field. The object mixes:
- Execution identity (`run_id`, `pipeline_name`)
- Infrastructure handles (`llm`, `db`, `llm_router`, `pipeline_runner`)
- Pre-loaded content (`constitution`, `standards`, `plan`)
- Runtime configuration (`settings`, `config`, `dal_level`)
- Domain state (`topology`, `feedback`, `stale_nodes`)
- Parsed tools (`parsers`, `analyzer_factory`)

**Fix (phased):**
1. **Phase 1** (with D-INTL-06 SF-2): Move `constitution`, `standards`, and `plan` loading into the prompt factory. Remove from RunContext. (-3 fields)
2. **Phase 2** (future): Split RunContext into focused sub-contexts (e.g., `ExecutionIdentity`, `InfraHandles`, `DomainState`).

**Effort:** Phase 1: ~4h (after SF-2). Phase 2: High (~8h, requires careful refactoring across all handlers).

## Highest-ROI Refactoring

After D-INTL-06 SF-2 lands the `build_base_prompt()` factory, move constitution and standards loading **inside the factory** — same pattern as memory hydration. This resolves all three findings in one shot:

| Metric | Before | After |
|---|---|---|
| RunContext fields | 23 | 20 (-3: constitution, standards, plan) |
| Cross-interface imports of private helpers | 10+ | 0 |
| Business logic in CLI layers | 2 functions | 0 |
| Context sources in factory | 1 (memory) | 4 (memory + constitution + standards + plan) |
| Modules to touch for new context source | 6+ scattered | 1 (factory) |

## Sub-Refactoring Breakdown

| # | Sub-Refactoring | Fixes | Effort | ROI | Dependency |
|---|---|---|---|---|---|
| SR-1 | Move `_load_constitution_content` to domain layer | Finding 1 | Low (~30 min) | Medium | None |
| SR-2 | Move `_load_standards_content` to domain layer | Finding 1 | Low (~30 min) | Medium | None |
| SR-3 | Extract `_run_workspace_op` to shared utility | Finding 2 | Medium (~2h) | Medium | Careful planning |
| SR-4 | Load constitution/standards/plan inside factory | All 3 | High (~4h) | **Very High** | D-INTL-06 SF-2 |
| SR-5 | Split RunContext into focused sub-contexts | Finding 3 | High (~8h) | High | SR-4 |
