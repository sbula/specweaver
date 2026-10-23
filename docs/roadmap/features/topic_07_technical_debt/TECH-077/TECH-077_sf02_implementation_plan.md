# Implementation Plan: Each Entry Point Builds Its Run by Hand, and the API Gets Less [SF-02: The run builder]
- **Feature ID**: TECH-077
- **Sub-Feature**: SF-02 — The run builder
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-077/TECH-077_sf02_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-1 (one builder), FR-3 (both isolation policies with DAL escalation in every door), FR-4 (one
project for everything). Kind `bugfix`. Depends on SF-01 (committed `fdce39c9`). NFR-2, NFR-3
apply. The doors move onto the builder in SF-03 (CLI) and SF-04 (API); this SF builds and proves
the builder alone.

## Research Notes

- **The most complete door today** is `core/flow/interfaces/cli.py` `_build_run_context`: sections
  through `_core.project_sections_at`, `find_constitution(project_path, spec_path=spec_path)`,
  `load_standards_content(db, active, project_path, target_path=spec_path)`, `_apply_isolation_policy`
  (per-step and per-run, no DAL), `_wire_models` (router and `config` only when a step needs a
  model, loading settings a second time), topology by `attach_topology`.
- `sw implement` (`workflows/implementation/interfaces/cli.py:255-325`) is the only door with DAL
  escalation: `apply_session_policy(context, settings, logger, dal_auto_escalate=True)`, and it never
  sets `enforce_isolation`. Its standards come from the active project (`:298`), its settings and
  router from `project_name_for(project_path)` (`:266`).
- **Isolation** (`core/flow/engine/isolation.py`): `apply_isolation_policy(context, settings, logger)`
  sets `enforce_isolation` from `settings.sandbox.enforce_worktree_isolation`, then calls
  `apply_session_policy(context, settings, logger)` with no escalation; both swallow errors.
  `apply_session_policy(..., dal_auto_escalate=True)` turns session isolation on at or above
  `sandbox.auto_isolate_min_dal` (default `DAL_B`) and derives `allowed_paths` in one `model_copy`.
- **Routers**: `build_router(files, *, project, roles, run_model=None, ask=None, db=None)`
  (`infrastructure/llm/router.py:74`) raises `SettingsFileError` / `SettingNotSetError`.
  `command_router` (CLI, refuses), `optional_command_router` (CLI, `SettingNotSetError` → None,
  active project only), `api_router` (API, 500). The CLI passes `ask=_core.spend_asker()`; the API
  passes none. `roles_of(pipeline)` (`core/flow/handlers/_llm.py`) lists the roles a pipeline uses.
- **Settings**: `load_settings(db, project)` / `load_settings_async` (raises `SettingsFileError` for
  a broken file, `ValueError` for an unknown project); `load_llm_settings(root)`.
- **Standards**: `load_standards_content(db, project_name, project_path, target_path=None)` and
  `load_standards_content_async` (`assurance/standards/loader.py:25,82`).
- **Topology**: `load_topology(root)`, `select_topology_contexts(graph, module, *, selector_name)`
  (`assurance/graph/loader.py`); `module_stem(spec_path)` (`commons/spec_names.py`).
- **Project**: SF-01's `store.project_name_at(db, root)`; the active project through the
  repository's `get_active_project`.
- **Layering**: `interfaces/run_setup` is a new `tach` module `[agreed 2026-10-23]`. It needs
  `core.flow`, `core.config`, `core.config.bootstrap`, `workspace`, `workspace.project`,
  `assurance.standards`, `infrastructure.llm` (`assurance.graph` and `commons` have no `tach` rules).
  PEP 420: no `__init__.py`.
- **TECH-076 decision 5** stays: a settings error stops the run; any other settings-lookup failure
  leaves isolation at its defaults.

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. A folder no project is registered at has no project: the run is refused, naming the folder and
   `sw init <name> --path <folder>` (design FR-4 updated).
2. One `models` field (`required` / `optional` / `none`); the door passes its spend `ask`.

## Approach (pseudocode, ordered)

**FR-4 — which project**
1. `run_setup.project_for(db, project_root, *, named=None) -> str`: `named` (the API's request)
   wins; else the project registered at `project_root`; with no root given, the active project; a
   root no project is registered at raises `UnknownProject` naming the folder and `sw init` (decision 1).

**FR-1 — the builder**
2. `RunRequest`: project root, spec (or target) path, pipeline, project name, `run_model`,
   `selector`, `ask`, `models` (`required` | `optional` | `none`), `db`.
3. `async build_run(request) -> RunContext`, in order (each step raises; nothing exits):
   sections (`load_section` × 3) → rule file → standards (async) → settings (once; a
   `SettingsFileError` raises, any other failure gives no settings) → router when the pipeline
   has roles (`optional` turns `SettingNotSetError` into no router) → topology slice →
   `RunContext(... model=ModelAccess(config=settings, llm_router=router) ...)`.
4. `build_run_sync(request)` runs it through `commons.async_bridge.run_sync`.

**FR-3 — isolation**
5. Last step of the builder: with settings, set `enforce_isolation` from
   `sandbox.enforce_worktree_isolation`, then `apply_session_policy(..., dal_auto_escalate=True)`
   `[agreed 2026-10-23]`; without settings, both stay off (decision 5 of TECH-076).

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/interfaces/run_setup/builder.py` [NEW] | `RunRequest`, `build_run`, `build_run_sync`, `project_for`, `UnknownProject` |
| `src/specweaver/interfaces/run_setup/context.yaml` [NEW] | purpose, archetype (adapter), consumes |
| `tach.toml` [MODIFY] | the `specweaver.interfaces.run_setup` module and its `depends_on` |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-4 | integration | `tests/integration/interfaces/run_setup/test_project_for.py` [NEW] | real DB: registered at the root (happy); a named project wins (boundary); no root → active (boundary); an unregistered root → `UnknownProject` naming it (hostile, decision 1); project B registered at the root while A is active → B (the EP-5 mix) |
| FR-1 | integration | `tests/integration/interfaces/run_setup/test_build_run.py` [NEW] | a real project with `CONSTITUTION.md`, `[docs]`/`[autonomy]`/`[implement]`, stored standards, a topology and a model step (doubled model): every part on the context, `config` set, settings loaded once (happy); a pipeline with no model step → no router, no settings file needed for models (boundary); `optional` with no model set → no router (degradation); a broken `[sandbox]` → `SettingsFileError` raised, not an exit (hostile, NFR-3). **Agreement:** `build_run_sync` and `build_run` give equal contexts |
| FR-3 | integration | same file | DAL_B target → session isolation on with derived `allowed_paths`; `enforce_worktree_isolation = true` → per-step on; DAL_E → both off; no settings (unknown-project lookup failure) → both off |
| NFR-3 | unit | `tests/unit/interfaces/run_setup/test_no_exit.py` [NEW] | the module imports no `typer` and never raises `SystemExit` (AST scan) |

Mutants: `project_for` falls back to the active project for an unregistered root; the builder
skips the rule file / standards / topology; settings loaded twice (spy count); DAL escalation off;
`enforce_isolation` ignored.

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | `tach` module, `project_for` (FR-4), the builder's parts (FR-1) | integration green; FR-1, FR-4 mutants killed; anchor check clean |
| CB-2 | isolation (FR-3), the sync/async agreement, NFR-3 scan. Closes SF-02: stops for the user's acceptance | green; FR-3 mutants killed |

## Documentation

`docs/dev_guides/pipeline_engine_guide.md` (how a run is set up: through `run_setup`);
`docs/architecture/03_system_topology/module_dependency_graph.md` (the new module).

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | Decision 2 says "the active project only when no path is given". So a command run on a folder no project is registered at — today it silently uses the active project's settings with that folder — has no project. | A: refuse, naming the folder and `sw init <name> --path <folder>`. B: keep falling back to the active project. | A — the fallback is the mix FR-4 removes | HIGH |
| 2 | How the builder serves the three router needs (CLI must have a model; standards scan may have none; API). | A: one `models` field (`required` / `optional` / `none`) and the spend `ask` passed in by the door. B: three builder entry points. | A — one builder, the door says what it needs | LOW |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| `run_setup/builder.py` | `interfaces/run_setup` · adapter (delivery side) | reads settings, DB, files | none | builds the router, calls no model | the seven listed in Research Notes | run setup | ok, `[agreed 2026-10-23]` option B |

No cycle: nothing below `interfaces` may import `run_setup`; the engine keeps its rule (no
`workspace/project`). The only `tach.toml` change is the new module.

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-4 and FR-1 (CB-1), FR-3 (CB-2). NFR-2: the engine gains nothing; the new module is
  the only `tach.toml` change. NFR-3: the builder raises; the AST scan proves no `typer`/exit.
  TECH-076 decisions hold: a broken setting raises; another lookup failure leaves isolation off.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: decision 1 changes what the CLI does in an unregistered folder; SF-03 will meet
  tests that relied on the active-project fallback — they are fixed by registering their folder,
  not by bringing the fallback back.
- **Architecture**: one new module, links only downward; nothing lower imports it.
- **DDD/KISS/DRY/hexagonal/SoC**: one builder replaces ten setups; the doors keep only their error
  mapping and their interaction channel.
- **Code detail limit**: no code block; steps are pseudocode.
- **Red/Blue**, 2 cycles:
  - R1 (HIGH) decision 1 breaks callers that ran in unregistered folders with an active project.
    Blue: intended (the mix FR-4 removes); the refusal says how to register. Scheduled for SF-03.
  - R2 (MEDIUM) the async builder mixes blocking file reads with async loaders. Blue: the reads are
    small local files; the DB lookups use `asyncio.to_thread` (SF-01 decision 2).
  - R3 (MEDIUM) `build_run_sync` inside a running loop. Blue: `commons.async_bridge.run_sync` never
    re-enters a running loop (it runs in a worker thread then).
  - R4 (LOW) `roles_of` is a private flow helper. Blue: every door imports it today; SF-03's one-step
    helper may move it.
  - Cycle 2: no new finding. Below every threshold.
