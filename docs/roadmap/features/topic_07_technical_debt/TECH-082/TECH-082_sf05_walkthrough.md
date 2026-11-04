# Walkthrough: TECH-082 SF-05 — One step table

## CB-1: a step is declared once (FR-9, NFR-1, NFR-2, NFR-4)

**What changed**
- `core/flow/engine/models.py`: `StepKind(action, target, role, agentic)` and `STEPS`, 21 rows.
  `VALID_STEP_COMBINATIONS`, `AGENTIC_STEPS` and `ROLE_OF_STEP` derive from it; `role_of(action,
  target)` reads it. `ROLE_OF_STEP` left `handlers/_llm.py`, which imports it.
- `handlers/_llm.py`: `llm_for_step(context, step)` asks for the row's role; a step with no role
  raises `ValueError` naming it. `llm_for(context, task_type)` stays for a call made for another task.
- `handlers/registry.py`: `_HANDLER_OF` holds the handler classes; `StepHandlerRegistry()` builds one
  instance per `STEPS` row and raises `LookupError` for a row with no class.
- 11 handler call sites read their role from the step (D-0, the user 2026-11-04). The routing helpers
  `_resolve_review_routing`, `_resolve_generation_routing`, `PlanSpecHandler._resolve_routing`,
  `LintFixHandler._llm_fix` and `DriftCheckHandler._analyze_drift` take the step. The
  `task_type=` override of `_resolve_generation_routing` is gone; `scenario.py` passes its own step.
  `dual_pipeline.py:_model_check` reads the two sides' roles from `ROLE_OF_STEP`.
- Docs: `domain_flow_engine.md` (source of truth is `STEPS`), `pipeline_engine_guide.md`
  (`llm_for_step`, a new step is one row), `developer_guide.html` (new-handler checklist).

**Tests**
- `test_no_handler_names_its_role.py` (6), red first on the 12 role reads and `_llm.py:31`.
- `test_one_step_table.py` (6), red first (no `STEPS`). The roles are written out by hand.
- `test_handler_reachability.py` (+1): every row with a role has a handler.
- `test_llm_for.py` (+2, gap analysis): `llm_for_step` asks for the table's role; a step with no
  role is refused by name, before the router is asked.
- Test edits (D-0): `test_config_helpers.py` passes a step (7 calls); the override test became
  "a scenario step gets the scenario role" and "a step with no role raises".
  `test_handlers_ext.py` (1 call), `test_drift_handler.py` (1 call, patch target `llm_for_step`),
  `test_handlers_edge_cases.py` (the `_llm_fix` call; two tests gave the generation and review
  handlers a `validate`+`feature` step, and now give each its own pair).
  `test_llm_for.py`'s hand list of model-free steps is removed; the guard replaces it.

**Mutants**
- 13 mutants whose symbols changed (B-FLOW-01 4, C-FLOW-11 2, D-INTL-03 1, D-INTL-08 2, TECH-078 1,
  TECH-081 1, TECH-082 2) were re-run before the refresh: all OBJECTED. 0 stale.
- TECH-082 FR-9 campaign: `step-gets-the-wrong-role`, `code-step-not-agentic` (both on `STEPS`, a
  module constant, so unhashed like other corpora's `MATRIX`), `handler-names-its-role`,
  `row-without-handler`. All OBJECTED.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `STEPS` and the derived tables | ✅ | ✅ every pipeline test loads through `validate_flow` | ✅ |
| `role_of` | ✅ | — | — |
| `llm_for_step` | ✅ | ✅ through the real handlers in the integration tier (e.g. `test_scenario_integration_dispatch.py`) | ✅ |
| registry from `STEPS` | ✅ | ✅ `test_handler_reachability.py` sweep of bundled pipelines | ✅ |
| handlers' role from the step | ✅ `test_config_helpers.py`, `test_lint_fix_handler.py` | ✅ | ✅ |

Agreement: the guard keeps the handlers from holding a second copy of a role.

**Red/blue (7.5)**, 2 cycles
- R1 (MEDIUM, accepted) More test edits than the plan counted: `test_handlers_edge_cases.py` and
  `test_drift_handler.py` call the step-taking helpers too, and two edge-case tests fed handlers a
  step of another pair. A handler is only reached through its own pair, so giving it its own pair
  is the real path. Within D-0.
- R2 (LOW) `models.py` now imports `infrastructure.llm.models` at module level. tach allows the
  edge; that module imports nothing from `core/flow`. No cycle.
- R3 (LOW) `models.py` is 505 lines (yellow, was 485). Below the 600 limit.
- Cycle 2: challenged R1 (does any production caller pass a foreign pair?): every `PipelineStep`
  built in `src/` names its own handler's pair (`cli_drift.py`, standards CLI, review API, drafting
  CLI). No new finding above LOW.

## CB-2: the dual run is a step; `params.mode` is refused (FR-10, FR-11)

**What changed**
- `StepTarget.DUAL_PIPELINE`; `StepKind` gains `runs_sides`; row `orchestrate`+`dual_pipeline`
  (no role, `runs_sides=True`); `SIDE_RUNNING_STEPS` derives from it.
- Registry: the row runs `ArbitrateDualPipelineHandler`.
- `_validate_orchestrate`: an `orchestrate` step with `params.mode` gives "Step '<name>':
  `params.mode` is no longer read on orchestrate steps; for a dual run use `target: dual_pipeline`"
  at load (AD-8, never translated).
- `OrchestrateComponentsHandler`: the mode branch and its warning are gone (`fan_out` untouched).
- `roles_of` adds the sides' roles for a step in `SIDE_RUNNING_STEPS`, not for a param value.
- `scenario_integration.yaml`: `target: dual_pipeline`, no `params`.
- Docs: `pipeline_engine_guide.md` (the dual step and the refusal), `domain_flow_engine.md` (handler
  table row); the design's guides row turns ✅.

**Tests**
- `test_dual_pipeline_step.py` (10), red first (no target): the dual step loads; `components` still
  loads; `roles_of` brings the sides' roles; `params.mode` is refused for 3 values on both targets;
  a `mode` on another action is not judged here.
- `test_dual_step_reaches_its_handler.py` (integration, 1): `load_pipeline` on the bundled YAML, then
  the real registry gives `ArbitrateDualPipelineHandler`. Red first: it gave
  `OrchestrateComponentsHandler`.
- `test_scenario_integration_yaml.py`: the step is `orchestrate`+`dual_pipeline` with no `mode`.
- `test_one_step_table.py` (+1, gap analysis): only the dual step runs sides.
- `test_decompose.py`: the two mode-dispatch tests are replaced by "a mode no longer reaches the dual
  handler"; the no-runner test now drives the dual handler with its own step (FR-10, FR-11).
- `test_engine_models.py`: target count 12, pair count 22.

**Mutants**
- B-FLOW-01 FR-17 `side-roles-unchecked` re-anchored on the `SIDE_RUNNING_STEPS` check: OBJECTED.
- TECH-082 FR-10 `dual-row-runs-the-orchestrator` (17 tests, the e2e included),
  `dual-row-runs-no-sides`; FR-11 `mode-loads-silently`. All OBJECTED. 0 stale.

**Coverage matrix**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| the dual row and `SIDE_RUNNING_STEPS` | ✅ | ✅ `test_dual_step_reaches_its_handler.py`, `test_two_models.py` | ✅ `test_scenario_verification_e2e.py` (real `sw run scenario_integration`) |
| `_validate_orchestrate` | ✅ | ✅ through `load_pipeline` | — |
| `roles_of` sides | ✅ | ✅ `test_two_models.py::test_a_dual_run_checks_every_role_its_sides_use` | ✅ |

**Red/blue (7.5)**, 2 cycles
- R1 (MEDIUM, accepted `[agreed 2026-11-02]`) A user's own pipeline with `mode: dual_pipeline` no
  longer loads; the message names the fix (design Risk table).
- R2 (LOW) A pipeline built in code skips `validate_flow`. No builder in `src/` sets `mode`; a step
  that carries it runs plan orchestration and fails on the missing plan, and never starts a dual run
  (pinned in `test_decompose.py`).
- R3 (LOW) A parked run resumes by reloading its pipeline by name (`core/flow/interfaces/cli.py:468`).
  The bundled YAML keeps the step name `run_dual_pipelines`, so a parked dual run resumes at the
  same step.
- Cycle 2: challenged R2 (is the refusal on the right action only?) — `bash` with a `mode` param is
  not judged (test). No new finding above LOW.
