# Implementation Plan: Domain Logic Lives in the Flow Engine [SF-05: One step table]
- **Feature ID**: TECH-082
- **Sub-Feature**: SF-05 — One step table
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf05_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-04)

## Scope

A pipeline step is declared once, in one table in `core/flow/engine` (AD-7). The dual run becomes a
real step, `orchestrate` + `dual_pipeline`, and an `orchestrate` step with `params.mode` is refused
at load. FRs: **FR-9, FR-10, FR-11**. NFRs carried: NFR-1 (same behaviour outside FR-10, FR-11),
NFR-2 (boundaries hold), NFR-4 (mutants re-pointed). NFR-3 does not apply: no module moves.
Kind: `refactor`.

Today a step is described in four places (re-measured 2026-11-04):

| Table | Where | Rows |
|---|---|---|
| `VALID_STEP_COMBINATIONS` | `core/flow/engine/models.py:106` | 21 |
| the registry | `core/flow/handlers/registry.py:97-119` | the same 21 |
| `AGENTIC_STEPS` | `core/flow/engine/models.py:390` | 2 |
| `ROLE_OF_STEP` | `core/flow/handlers/_llm.py:25` | 13 |

Handlers name their own step's role again in 12 places: `draft.py:148,344`, `review.py:35`,
`generation.py:47,343`, `scenario.py:64`, `lint_fix.py:312`, `drift.py:155`, `arbiter.py:303`,
`decompose.py:51`, `standards.py:108`; and `dual_pipeline.py:70` names its two sides' roles.

The dual run is reached by `params.mode == "dual_pipeline"` at `decompose.py:374` and
`_llm.py:72`; any other `mode` logs a warning and runs plan orchestration (`decompose.py:379-384`).

## Decisions (Phase 4, the user 2026-11-04)

- **D-0 Handlers get their role from the step** `[agreed 2026-11-04]` (F-1 A): the routing helpers
  take the step; their 8 test calls pass one. NFR-1 in the design gains the exception "FR-9 changes
  the routing helpers' arguments and replaces the hand list of model-free steps
  (`test_llm_for.py:81`)".

### F-1 (HIGH, settled: A) Handlers get their role from the step: test calls change

To read its role from the table, a handler needs its step. Three private helpers take only the
context today, and tests call them directly: `_resolve_review_routing(context)` (`review.py:31`),
`_resolve_generation_routing(context, *, task_type=None)` (`generation.py:40`),
`PlanSpecHandler._resolve_routing(context)` (`generation.py:338`). 8 test calls use them
(`test_config_helpers.py:33,41,53,63,76,87,96`, `test_handlers_ext.py:70`); one of them passes a
`task_type=` override (`:63`).

NFR-1 says test edits outside FR-10, FR-11 and FR-13..FR-20 change only imports and `mock.patch`
targets. FR-9 is not in that list.

- **A** Pass the step: `llm_for_step(context, step)` reads the role from the table; the helpers get
  `step` as a parameter; the 8 test calls pass a step too. The tests still check the same role.
  NFR-1 gets one more exception: "FR-9 changes the routing helpers' arguments".
- **B** Keep the helpers' arguments: each helper looks up a fixed key, e.g.
  `ROLE_OF_STEP[(REVIEW, SPEC)]`. No test edit, but the helper still names its step by hand, in a
  second place: half of what FR-9 removes.

➡️ **A.** The role then has one source, and the tests still prove the same role per step.

## Findings settled without a user choice

### F-2 (MEDIUM) The design's FR-9 example is wrong

FR-9 exempts "a call made for another task, such as `generation.py:343`'s plan call". That line is
`PlanSpecHandler`'s own step (`plan` + `spec` → `PLAN`), so it is not an exception. Measured: every
role a handler names is its own step's, except `dual_pipeline.py:70`, which asks which model each
side uses. That one reads the roles of `generate`+`code` and `generate`+`scenario` from the table
too, so the two-model check follows the table. The design's example becomes
`dual_pipeline.py:70`. No behaviour change.

### F-3 (MEDIUM) Where the table lives

The table needs `StepAction` and `StepTarget`, defined in `engine/models.py`; a new file would
import them, and `validate_flow` (same file) would import the table back: a cycle. So the table
goes in `models.py`. `models.py` is 485 lines (yellow, limit 600); the table replaces
`VALID_STEP_COMBINATIONS` and `AGENTIC_STEPS` (about 35 lines) with about 35 lines, so the size stays
about the same. `TaskType` comes from `infrastructure.llm.models`; `core.flow.engine` already
depends on `infrastructure.llm` (tach, manifest).

### F-4 (MEDIUM) How the registry derives from the table

The engine knows no handler (AD-7, `layer_isolation_and_di.md`), so the table cannot name the
handler class. The registry keeps a map `(action, target) → handler class` and builds its rows by
walking the table: a table row with no handler raises at construction, naming the row. A handler
with no table row is caught by the reachability test (invariant 1 stays).

### F-5 (MEDIUM) `roles_of` reaches the sides through the table

The row `orchestrate`+`dual_pipeline` carries `runs_sides=True`. `roles_of` adds the sides' roles for
a step whose row says so, not for a `params.mode` value. The side pipelines still come from
`dual_side_pipelines()` (`dual_pipeline.py`, same module family as `_llm.py`).

### F-6 (MEDIUM) Pipelines built in code skip the load check

FR-11 refuses `params.mode` in `validate_flow`, which `load_pipeline` runs. Every user pipeline goes
through `load_pipeline` (`core/flow/interfaces/cli.py:322,468`, `interfaces/api/v1/paths.py:75`,
`parser.py:76`). Pipelines built in code (`decompose.py:243,350`, `dual_pipeline.py:140`,
`workflows/drafting/interfaces/cli.py:55`) never set `mode`. So the handler's mode branch and the
warning are removed, not kept as a second check. `test_decompose.py`'s two mode tests are replaced
by load tests (FR-10, FR-11 behaviour, allowed by NFR-1).

### F-7 (LOW) A guard against roles named by hand

`test_every_step_that_calls_a_model_has_a_role` (`test_llm_for.py:81`) keeps a hand list of
model-free steps. It is replaced by an AST guard: no module under `core/flow/handlers` reads a
`TaskType.<member>`. A future call for another task adds itself to the guard's allow list with a
reason (FR-9's exemption). Red today: the 12 places above.

### F-8 (LOW) Two commit boundaries

CB-1 builds the table (FR-9). CB-2 adds the dual step (FR-10, FR-11) on top of it. Each guard is red
before its own boundary's code, so each boundary can fail first.

### Phase 3 (architecture), no violation

| Mechanism | `core/flow/engine/models.py` (pure-logic data model) | Verdict |
|---|---|---|
| I/O, state | none: a constant table | ok |
| Execution | none | ok |
| LLM | `TaskType` enum only (a value, no call) | already consumed |
| Dependencies | `infrastructure.llm.models` | existing edge |
| Domain | which steps exist and what each needs | matches its `purpose` |

- Zoom-out: no other step table exists; this one replaces four.
- No cycle: `models.py` imports `infrastructure.llm.models`, which imports nothing from `core/flow`
  (checked: `grep -rn "core.flow" src/specweaver/infrastructure/llm/models.py` is empty).
- Boundary rule (FR-15): no manifest changes; `core/flow/engine` already consumes
  `specweaver/infrastructure/llm`.

## Decisions (no user choice needed)

### D-1 The table

- `engine/models.py`: a frozen row type `StepKind(action, target, role: TaskType | None,
  agentic: bool = False, runs_sides: bool = False)` and `STEPS: tuple[StepKind, ...]`, 22 rows (the
  21 of today plus `orchestrate`+`dual_pipeline` in CB-2).
- Derived, same names, so readers do not change: `VALID_STEP_COMBINATIONS`, `AGENTIC_STEPS`,
  `ROLE_OF_STEP` (moves from `_llm.py` to `models.py`; `_llm.py` imports it). One helper
  `role_of(action, target) -> TaskType | None`.
- `handlers/_llm.py`: `llm_for_step(context, step)` = `llm_for(context, <the row's role>)`; a step
  with no role raises `ValueError` naming the step and its pair (a programming error, never a user
  path: every caller passes a step whose row has a role). `llm_for(context, task_type)` stays for a call made for another task.
- `ROLE_OF_STEP` stays importable from `_llm.py` (it imports the name from `models.py` for
  `roles_of`), so `test_llm_for.py`'s import does not move.

### D-2 Handlers (F-1 A)

| Handler | Today | After |
|---|---|---|
| `draft.py:148,344` | `llm_for(context, TaskType.DRAFT)` | `llm_for_step(context, step)` |
| `review.py:35` | `_resolve_review_routing(context)` | `_resolve_review_routing(context, step)` |
| `generation.py:47` | default `IMPLEMENT`, `task_type=` override | `_resolve_generation_routing(context, step)`; the override goes, `scenario.py:64` passes its own step; `test_config_helpers.py:63` (override `VALIDATE`) becomes "a step with no role raises" |
| `generation.py:343` | `_resolve_routing(context)` → `PLAN` | `_resolve_routing(context, step)` |
| `lint_fix.py:312`, `drift.py:155`, `arbiter.py:303`, `decompose.py:51`, `standards.py:108` | a named role | `llm_for_step(context, step)`; the step is passed down where a helper lacks it |
| `dual_pipeline.py:70` | `TaskType.IMPLEMENT`, `TaskType.SCENARIO` | `ROLE_OF_STEP[(GENERATE, CODE)]`, `ROLE_OF_STEP[(GENERATE, SCENARIO)]` (F-2; indexing, so mypy sees a `TaskType`, never `None`) |

### D-3 The dual step (CB-2)

- `StepTarget.DUAL_PIPELINE = "dual_pipeline"`; row `(ORCHESTRATE, DUAL_PIPELINE, role=None,
  runs_sides=True)`; registry row → `ArbitrateDualPipelineHandler`.
- `scenario_integration.yaml`: `target: dual_pipeline`, no `params`.
- `decompose.py:371-384`: the mode branch and the warning are removed (F-6).
- `_validate_params` (or a sibling `_validate_orchestrate`): an `orchestrate` step whose `params`
  has `mode` gives "Step '<name>': `params.mode` is no longer read; use `target: dual_pipeline`"
  (FR-11 `[agreed 2026-11-02]`, AD-8).
- `_llm.roles_of`: `runs_sides` replaces the `params.mode` check (F-5).

### D-4 Mutants to re-point (NFR-4)

| Corpus | Mutant anchor | Change |
|---|---|---|
| B-FLOW-01 | `_llm.py` `roles_of`: `if step.params.get("mode") == "dual_pipeline":` | re-anchor on the `runs_sides` check |
| B-FLOW-01 | `dual_pipeline.py` `_model_check` | refresh `symbol_sha` |
| B-FLOW-07 | `_llm.py` `llm_for` | refresh if the body changes |
| C-FLOW-11 | `models.py` `_validate_mode`, `autonomy.py` `requested_mode` (read `AGENTIC_STEPS`) | anchors hold (name kept); refresh if a symbol changed |

Refresh: `python scripts/_corpus.py --corpus <file> --refresh "<derived id>"`, then
`stale_mutants.py` reports none.

### D-5 Which documents change

- `docs/dev_guides/pipeline_engine_guide.md`: "a step is one row in `STEPS`"; the `dual_pipeline`
  target. The design's guides row turns ✅.
- `docs/architecture/02_bounded_contexts/domain_flow_engine.md:73-94`: the handler table gains
  `orchestrate+dual_pipeline`; the rule names `STEPS`.
- `docs/dev_guides/developer_guide.html:1149`: the new-handler checklist names a row in `STEPS`.
- The design: FR-9's example (F-2); NFR-1's exception (D-0).
- Closed stories' documents keep the old text (`finished-stories-immutable`).

### D-6 Out of scope

- `roles_of` becoming public, the side step names in the arbiter: SF-06 (FR-12).
- `fan_out()` in `OrchestrateComponentsHandler` stays as it is (`pipeline_engine_guide.md:152`).

## Path List rows this SF owns

| Row | Interface first exists | Test |
|---|---|---|
| P-7 `sw run scenario_integration` → `orchestrate`+`dual_pipeline` → two sides → arbiter | CB-2 | new integration test (CB-2 red 3); existing `test_scenario_verification_e2e.py` (real `sw run`), `test_scenario_integration_e2e.py` (sequence), `test_two_models.py` pass |

## Commit Boundaries

### CB-1 (interior): one table — FR-9

**Red first**:

1. `tests/unit/core/flow/handlers/test_no_handler_names_its_role.py` (`Proves: TECH-082 FR-9`): an
   AST scan of `core/flow/handlers/*.py` finds no `TaskType.<member>` read. Red: the 12 places.
   - happy: a clean file passes.
   - boundary: `TaskType` as a type hint (`task_type: TaskType`) passes; `from ... import TaskType`
     passes.
   - degradation: an unparsable file is named, not skipped.
   - hostile: an aliased `from ... import TaskType as T; T.REVIEW` is found (today
     `generation.py:45-47` reads `_TaskType.IMPLEMENT`); `getattr(TaskType, "REVIEW")` is found.
2. `tests/unit/core/flow/engine/test_one_step_table.py` (`Proves: TECH-082 FR-9`), red (no `STEPS`):
   - happy: `VALID_STEP_COMBINATIONS`, `AGENTIC_STEPS` and `ROLE_OF_STEP` equal what `STEPS` says;
     each row's role equals today's role (the 13 written out by hand, not read from the table).
   - boundary: a row with no role is absent from `ROLE_OF_STEP`; no two rows share a key.
   - degradation: a registry built against a table with an extra row raises, naming it.
   - hostile: `role_of` of an undeclared pair is `None`.
3. `test_handler_reachability.py` gains: every row with a role resolves to a handler (roles checked,
   as FR-9's outcome asks). Red: no `STEPS`.

**Green**: D-1, D-2, F-4; replace `test_every_step_that_calls_a_model_has_a_role` (F-7); edit the
8 helper test calls (F-1 A); `test_drift_handler.py:104` patches `drift.llm_for_step`; re-point mutants (D-4).

**Done when**: `tach check`, `stale_mutants.py` pass; these mutants are killed:
- in `STEPS`, set `review`+`code`'s role to `CHECK` → `test_one_step_table.py` and
  `test_llm_for.py::test_a_pipeline_names_the_roles_its_steps_use` go red.
- in `STEPS`, drop `agentic=True` from `generate`+`code` → C-FLOW-11's tests go red.
- in a handler, put `TaskType.REVIEW` back → the guard goes red.
- in the registry, skip one row's handler → construction raises; the reachability test goes red.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, `specweaver-pre-commit`, commit.

### CB-2 (closes SF-05, HITL): the dual step — FR-10, FR-11

**Red first**:

1. `tests/unit/core/flow/engine/test_dual_pipeline_step.py` (`Proves: TECH-082 FR-10, TECH-082
   FR-11`), red (no target):
   - happy: a pipeline with `orchestrate`+`dual_pipeline` loads with no error.
   - boundary: `orchestrate`+`components` with no params still loads.
   - degradation: `roles_of` of a pipeline with the dual step includes the sides' roles.
   - hostile: `orchestrate` with `params: {mode: dual_pipeline}` is refused at load, and the message
     names `target: dual_pipeline`; `params: {mode: Dual_Pipeline}` too.
2. `test_scenario_integration_yaml.py`: the bundled step is `target: dual_pipeline` with no
   `mode`. Red: the YAML has `mode`.
3. `tests/integration/core/flow/engine/test_dual_step_reaches_its_handler.py`
   (`Proves: TECH-082 FR-10`): `load_pipeline` on the bundled `scenario_integration.yaml`, then the
   real `StepHandlerRegistry` resolves `run_dual_pipelines` to `ArbitrateDualPipelineHandler`. Red:
   today it resolves to `OrchestrateComponentsHandler` (the seam: loader → table → registry).

**Green**: D-3; replace `test_decompose.py`'s two mode tests (F-6); re-point the `roles_of` mutant;
docs (D-5).

**Done when**: P-7's tests pass; these mutants are killed:
- remove the `params.mode` refusal → red 1 (hostile) goes red.
- in `roles_of`, ignore `runs_sides` → red 1 (degradation) and `test_two_models.py::
  test_a_dual_run_checks_every_role_its_sides_use` go red.
- point the dual row at `OrchestrateComponentsHandler` → red 3 and the e2e go red.

**Gate**: `python scripts/tests.py cb TECH-082 --kind refactor`, then `specweaver-pre-commit`,
stage, **STOP** for the user.

## Research Notes

- `PipelineDefinition.validate_flow()` (`models.py:325`) checks the pair, the gate, the router,
  `_validate_params(step)` and `_validate_mode(step)`; `load_pipeline` (`parser.py:30`) runs it.
- `_validate_mode` reads `AGENTIC_STEPS` (`models.py:400`); `requested_mode` reads it lazily
  (`autonomy.py:50`).
- `roles_of(pipeline)` (`_llm.py:66`) is imported by `interfaces/run_setup/builder.py:79,156`.
- `ArbitrateDualPipelineHandler.execute` reads no `step.params` key of its own; it sets
  `params["component"]` on the side steps it builds (`dual_pipeline.py:131`).
- No engine code branches on `ORCHESTRATE` or `COMPONENTS` (grep); `hydration.py:62-144` branches
  only on `decompose`+`feature` and `plan`+`spec`.
- `check_story_preconditions.py:322` builds `StepHandlerRegistry()` and resolves every bundled step:
  it covers the new row once the YAML changes.
- `step.mode` (`oneshot`/`agentic`, `_validate_mode`) is a different field from `params.mode`; FR-11
  touches only `params.mode`.

## Red/Blue (Phase 5), 2 cycles

- R1 (MEDIUM) The guard first matched only the name `TaskType`; `generation.py` reads it as
  `_TaskType.IMPLEMENT`. Fixed: the guard resolves import aliases (hostile case).
- R2 (MEDIUM) `role_of` returns `TaskType | None`; `dual_pipeline.py` passes it to `model_of`, so mypy
  would fail. Fixed: index `ROLE_OF_STEP`.
- R3 (MEDIUM) `test_config_helpers.py:63` tests an override that goes away. Fixed: it becomes "a step
  with no role raises" (D-2).
- R4 (LOW) Code paths build steps outside a pipeline (`cli_drift.py:66,178`,
  `assurance/standards/interfaces/cli.py:90`, `interfaces/api/v1/review.py:43`, the drafting CLI).
  Each builds a real pair whose row has a role, so `llm_for_step` works for them; no change.
- R5 (LOW) `test_llm_for.py` imports `ROLE_OF_STEP` from `_llm.py`. Kept importable there (D-1).
- Cycle 2: challenged D-0 (does NFR-1's exception let other test edits in?) — it names the helpers
  and one test only. Challenged F-4 (does raising in the registry break `_PartialRegistry`?) — it
  pops rows after `super().__init__()`, so no. No new finding above LOW.

## Backlog
