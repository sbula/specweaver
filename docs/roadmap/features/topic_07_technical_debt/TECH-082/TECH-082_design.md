# Design: Domain Logic Lives in the Flow Engine

- **Feature ID**: TECH-082
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (the user, 2026-11-02)
- **Kind**: `refactor`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 9 below. Started
  2026-10-31 as the first of `TECH-082` then `TECH-079` (the user). These are gaps in delivered
  work; `finished-stories-immutable` bars editing the closed stories, so they are owned here.

## Feature Overview

TECH-082 moves domain work out of the flow engine (`core/flow`) into the modules that own it, and
cleans the engine's own seams. Language layouts, framework detection, contract rendering, lint
repair, verdict arbitration, drift analysis and validation policy leave `core/flow`; the engine
keeps thin step handlers that call them. Inside the engine, the runner's helpers stop reading its
private fields, a step is declared in one table, `context.feedback` gets named keys, and two
modules stop sharing one name. It also carries one behaviour fix agreed elsewhere: `sw check` and
`POST /check` count skipped rules `[agreed 2026-10-31]`. It does not touch the findings owned by
`TECH-075`..`TECH-091` (language tables are `TECH-079`, spec-section parsing `TECH-083`, model
calls `TECH-085`).

The scope is all 9 findings: the moves first, then the engine's own parts `[agreed 2026-11-02]`.

## The Defect (re-measured 2026-11-02)

| Finding | Re-measured |
|---|---|
| Fix first #10, FL-3 | `core/flow/engine/task_files.py` (227 lines), `engine/frameworks.py` (116), `handlers/contract_renderers.py` (533) are language and framework domain code in the engine |
| FL-5 | Validation's own CLI (`assurance/validation/interfaces/cli.py:139,290`) and the API (`interfaces/api/v1/validation.py:107`) import validation policy from `core/flow/handlers/validation_hydrator.py` and `archetype_pipelines.py`: the dependency points from validation into the engine |
| WV-7 | Only three handlers call a model themselves: `arbiter.py:396`, `lint_fix.py:346`, `drift.py:174`, each with a hand-written prompt |
| FL-17 | `ArbitrateVerdictHandler.execute` (`arbiter.py:300`) carries `# noqa: C901`; `ValidateTestsHandler.execute` (`validation.py:379-478`) and `LintFixHandler` (`lint_fix.py:88-361`) mix domain work and orchestration |
| FL-16 | 19 free functions take `runner: Any` and read or write its private fields (`step_execution.py:106-528`, `approval.py:68`, `session.py:28-166`, `fan_out.py:46`, `sandboxed_execution.py:57`); `_session_active` and `_session_kept` are never set in `PipelineRunner.__init__`, so `step_execution.py:204` reads one through `getattr(..., False)`. The engine reads handler output keys by literal: `"plan"` (`hydration.py:37`), `"plan_path"` (`:145`), `"results"` (`step_execution.py:482`), `"verdict"` (`gates.py:133`), `"files_touched"` (`handover.py:57`) |
| FL-9 | A step is described in four tables: `VALID_STEP_COMBINATIONS` (`models.py:106`, 21 pairs), the registry (`registry.py:97`, the same 21), `AGENTIC_STEPS` (`models.py:391`, 2), `ROLE_OF_STEP` (`_llm.py:25`, 13); 11 handlers hard-code their role again. The dual pipeline has no row: it is reached by `params.mode == "dual_pipeline"` at `decompose.py:373` and `_llm.py:72`, and any other `mode` value only logs a warning and runs plan orchestration (`decompose.py:379-384`) |
| FL-10 | `context.feedback` (`run_context.py:174`) is `dict[str, Any]` with six key kinds; two pop functions with reversed argument order (`generation.py:50`, `draft.py:29`); `arbiter.py:236,425` hard-codes the YAML step names `generate_code` and `generate_scenarios`, also listed in `dual_pipeline.py:55-56`; `scenario.py:222` writes `scenario_test_path`, which nothing reads |
| FL-21 | `handlers/mcp_assembler.py` and `handlers/context_assembler.py` are both titled "Context Assembler"; the private `handlers/_llm.py` is imported from `interfaces/run_setup/builder.py:79,156`; `generation.py:106,317` `FILENAME_PREFIX` has no reader |
| Carry-in | `_print_summary` (`assurance/validation/interfaces/cli.py:71-95`) counts only FAIL and WARN, so a run where every rule is SKIP prints `ALL PASSED` and exits 0; `/check` (`interfaces/api/v1/validation.py:123-136`) returns `overall: "PASS"` for the same run |

## Path List (`ADR-005`)

| # | Path | Span | Owner | Status |
|---|---|---|---|---|
| P-1 | `sw check <file>` → `execute_validation_flow` (new home) → rules → printed table and summary | validation CLI, validation orchestration, rules | TECH-082 (FR-1, FR-13) | ⬜ |
| P-2 | `POST /api/v1/check` → `execute_validation_flow` (new home) → response | API, validation orchestration, rules | TECH-082 (FR-1, FR-14) | ⬜ |
| P-3 | `sw run` / `sw implement` → `validate_code` / `validate_tests` handler → validation orchestration | flow handler, validation orchestration | TECH-082 (FR-1) | ⬜ |
| P-4 | `sw implement` → generation handler → `task_files_for`, `project_framework`, `render_contract_file` (new home) | flow handler, workflows/implementation | TECH-082 (FR-3) | ⬜ |
| P-5 | a pipeline's `lint_fix` step → `LintFixHandler` → lint-repair workflow → model | flow handler, workflows/implementation, LLM | TECH-082 (FR-4) | ⬜ |
| P-6 | `drift_check` step and `sw drift` → `DriftCheckHandler` → drift analysis → model | flow handler, validation orchestration, LLM | TECH-082 (FR-2) | ⬜ |
| P-7 | `sw run scenario_integration` → `orchestrate`+`dual_pipeline` → two sides → `arbitrate`+`verdict` → arbitration workflow → model | YAML loader, registry, dual handler, workflows/arbitration | TECH-082 (FR-5, FR-9, FR-10) | ⬜ |
| P-8 | a run builder asks which roles a pipeline needs (`roles_of`) | `interfaces/run_setup`, step table | TECH-082 (FR-8, FR-12) | ⬜ |

## Research Findings

### Codebase Patterns

- **The rules live in three places** (`docs/architecture/03_system_topology/hard_dependency_rules.md`):
  `tach.toml` module edges (`exact = true`, `root_module = "forbid"`, TYPE_CHECKING imports count,
  no cycles, no `deprecated` edge, TECH-081 FR-20), `tach.toml` `[[interfaces]] expose`, and each
  `context.yaml`. Guards: `test_architecture.py`, `test_manifests_match_tach.py`,
  `test_manifests_are_complete.py`, `test_pure_modules_do_no_io.py`, `test_tach_sees_every_module.py`.
- **`assurance/validation` is `pure-logic`** and forbids `sandbox/*` and `infrastructure/llm`
  (`assurance/validation/context.yaml`). `validation_hydrator` runs sandbox atoms (`:126,155,200-202`),
  `archetype_pipelines` imports sandbox (`:113,114,164`), `validation.io` (`:182`, a cycle) and
  `core.flow.engine.project_paths` (`:189`). Hence a new orchestrator sub-module (AD-1).
- **`workflows/implementation`** is an orchestrator that consumes `infrastructure/llm`,
  `core/config`, `assurance/validation`, and already holds `languages.py` and the language and
  framework texts (`workflows/languages/*.md`, `workflows/frameworks/*.md`).
- **The engine knows no handler** (`docs/dev_guides/layer_isolation_and_di.md`): `core/flow` is
  three tach modules, `engine`, `handlers`, `run_state`; the engine reaches handlers through the
  injected `HandlerLookup` port; a handler that needs a workflow gets it from the builder
  (`interfaces/run_setup`).
- **Anti-patterns** (`docs/architecture/06_lessons_and_future/anti_patterns.md`): domain modules
  must not import `sandbox/*` ("use `flow/` as the bridge"); "two modules naming one thing
  differently across a seam"; "a declared rule that nothing reads".
- **Mutants pin file + symbol + `symbol_sha`** (`docs/dev_guides/writing_mutation_campaigns.md`).
  Anchors in moved files: `task_files` 5, `frameworks` 4, `contract_renderers` 1,
  `validation_hydrator` 4, `archetype_pipelines` 7, `arbiter` 9, `lint_fix` 10, `drift` 2.
- **`mock.patch` strings that break silently on a move**: `validation_hydrator` 2
  (`test_validate_code_languages.py:41,78`), `arbiter` 3 module strings
  (`test_build_base_prompt_profiles.py:181,279,366`), `lint_fix` 4 (`test_cli_implement.py:115,227`,
  `e2e/conftest.py:93`, `test_drafter_loop_e2e.py:134`).
- **A past decision this reverses**: `INT-US-24` AD-1 chose `params.mode` over a new step pair,
  "engine-model change + YAML migration for zero behavioral gain". It was the agent's call, never
  marked agreed; the user chose the new step `[agreed 2026-11-02]`. The gain: an unknown `mode`
  silently runs plan orchestration today, and FL-9 wants every step in one table.
- **Summary strings in tests**: 9 assertions in 5 files (`test_cli.py:264,334`,
  `test_cli_check.py:85`, `test_dal_e2e_pipeline.py:94,106`,
  `test_validation_dal_enforcement.py:77,100`, `test_code_dal_strictness_e2e.py:131,146`).
  No user guide quotes a summary line; `1_installation_and_setup.md:336` describes the SKIP rows.

### External Tools

None new. `tach` (already pinned) enforces the boundaries.

### Blueprint References

The "functional core, imperative shell" split: the handler (shell) gathers inputs from the run and
writes results back; the moved function (core) takes plain values and returns plain values. The
engine's existing `HandlerLookup` port is the same idea one level up.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | `execute_validation_flow`, `hydrate_code_validation_context`, `spec_pipeline`, `code_pipeline`, `own_pipeline`, `add_payload` and the rest of `validation_hydrator.py` and `archetype_pipelines.py` SHALL live in the new module `assurance/validation/orchestration` `[agreed 2026-11-02]`; the validation CLI, the API and the flow handlers SHALL import them from there, and no module under `assurance/` or `interfaces/api/v1/validation.py` SHALL import `specweaver.core.flow.handlers` (seam: CLI, API and flow → validation orchestration) | the validation CLI, the API, `ValidateCodeHandler` | check a file | the same results as before, through the new home |
| FR-2 | The drift root-cause analysis (prompt, model call, `SpendLimitReachedError` → `None`) SHALL be a function in `assurance/validation/orchestration` that takes the model adapter, its config and plain values; `DriftCheckHandler` SHALL only gather inputs, call it and write the result `[agreed 2026-11-02]` | `DriftCheckHandler` | run a drift step | the same report |
| FR-3 | `task_files.py`, `frameworks.py` and `contract_renderers.py` SHALL live in `workflows/implementation` `[agreed 2026-11-02]`, and no module named `task_files`, `frameworks` or `contract_renderers` SHALL remain under `core/flow`; the moved code SHALL NOT import `sandbox/*` (the caller passes the detected language) | generation, `sw implement`, `POST /implement` | derive a task's files, framework and contract | the same files, framework and contract text |
| FR-4 | The lint repair (prompt, model call, fence strip, tag restore) SHALL be a function in `workflows/implementation` taking the adapter, config, code text and lint errors and returning the fixed text; `LintFixHandler` SHALL keep the loop, the file write and the lineage log `[agreed 2026-11-02]` | `LintFixHandler` | repair a lint failure | the same fixed file |
| FR-5 | `ArbitrateVerdict`, `ArbitrateResult`, `ARBITRATE_INSTRUCTIONS` and the evidence-to-verdict call (prompt in, model call, parse) SHALL live in the new module `workflows/arbitration` `[agreed 2026-11-02]`; `ArbitrateVerdictHandler` SHALL keep guards, the trace filter and verdict routing, without `# noqa: C901` | `ArbitrateVerdictHandler` | arbitrate a dual run | the same verdict and routing |
| FR-6 | No module under `core/flow/handlers` SHALL call a model adapter's `generate` or `generate_with_tools` itself (the engine's agentic `work_unit.py` loop is out of scope); `ValidateTestsHandler.execute` and `LintFixHandler` SHALL pass ruff's complexity limit (10) without a `noqa` | the flow handlers | — | only workflows talk to the model |
| FR-7 | Every engine function that takes the runner SHALL type it with one protocol naming the members it uses; no engine module SHALL read or write another object's `_`-prefixed attribute; `PipelineRunner.__init__` SHALL set every attribute those functions read | `core/flow/engine` | run a pipeline | no `runner: Any`, no `getattr(runner, "_…", default)` |
| FR-8 | Each handler output key the engine reads (`plan`, `plan_path`, `results`, `verdict`, `files_touched`) SHALL be named once, in one module both the engine and the writing handler import | the engine, the handlers | pass a step's output | one spelling per key |
| FR-9 | Every `(action, target)` step SHALL be declared once, with its handler, its model role (or none) and whether it is agentic; `VALID_STEP_COMBINATIONS`, the registry rows, `ROLE_OF_STEP` and `AGENTIC_STEPS` SHALL derive from that declaration, and no handler SHALL hard-code its own step's role (a call made for another task, such as `generation.py:343`'s plan call, keeps its explicit role) | the engine, the registry, the run builder | load and run a pipeline | one table; `test_handler_reachability.py` also checks roles |
| FR-10 | A step `action: orchestrate`, `target: dual_pipeline` SHALL run `ArbitrateDualPipelineHandler`, and `roles_of` SHALL include its two sides' roles through the table; `scenario_integration.yaml` SHALL use it `[agreed 2026-11-02]` | the YAML loader, the registry, `roles_of` | run `scenario_integration` | the same dual run |
| FR-11 | An `orchestrate` step that carries `params.mode` SHALL be refused when the pipeline loads, with a message that names `target: dual_pipeline` `[agreed 2026-11-02]` | the YAML loader | load an old pipeline | a load error, never a silent fallback |
| FR-12 | Each `context.feedback` key SHALL be declared once with its value type, read through one pop function; the arbiter SHALL take the side step names from the dual pipeline's side table, not literals; the unread `scenario_test_path` write and `FILENAME_PREFIX` SHALL be removed; `mcp_assembler` and `context_assembler` SHALL carry distinct names; `roles_of` SHALL be imported from a public module | the handlers, `interfaces/run_setup` | — | no grab-bag keys, no private import from outside `core/flow` |
| FR-13 | `sw check`'s summary SHALL count SKIP rows: each summary line SHALL add `N skipped` when N > 0, and when no rule judged (every result SKIP, or no result) it SHALL print `NOTHING CHECKED: N skipped` and exit 1 `[agreed 2026-11-02]` | `sw check` | check a file | e.g. `ALL PASSED (3 skipped)`; all-skip exits 1 |
| FR-14 | `POST /api/v1/check` SHALL return a `skipped` count, and `overall: "NOTHING_CHECKED"` when no rule judged `[agreed 2026-11-02]` | the API | check a file | the response says nothing was checked |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | run validation with hydrated context | `execute_validation_flow(...)` | read `core/flow/handlers/validation_hydrator.py:321`; callers `assurance/validation/interfaces/cli.py:290`, `interfaces/api/v1/validation.py:107`, `handlers/validation.py:310` |
| FR-1 | the project boundary used by `relative_to_root` | `project_file(project_root, relative)` over `sandbox.security.WorkspaceBoundary` | read `core/flow/engine/project_paths.py:13,20`; importers `archetype_pipelines.py:189`, `interfaces/api/v1/paths.py:14`; `interfaces/api/context.yaml` forbids `sandbox/*` |
| FR-2, FR-4, FR-5 | adapter and config | `handlers/_llm.py` · `llm_for(context: RunContext, task_type: TaskType) -> tuple[Any, GenerationConfig]` | read `_llm.py:46` |
| FR-5 | the base prompt | `prompting.py` · `async _build_base_prompt(context, instructions, *, profile=None, skeleton_files=None) -> PromptBuilder` | read `prompting.py:23` |
| FR-3 | the language when none is given | `sandbox.language.core.detect` | read `task_files.py:60` (lazy import) |
| FR-9, FR-10 | step pairs checked at load | `validate_flow` → `VALID_STEP_COMBINATIONS`; `_validate_params` | read `models.py:358,373,410` |
| FR-11 | where a param is refused | `_validate_params` (only `bash` requires `script` today) | read `models.py:385,410` |
| FR-13 | rule results | `RuleResult.status` (`Status.SKIP`) | read `cli.py:71-95`, `models.py` |
| FR-14 | the response model | `CheckResponse` (`overall`, `total`, `passed`, `failed`, `warned`) | read `interfaces/api/v1/schemas.py:89-97`, `validation.py:123-136` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Behaviour stays the same outside FR-10, FR-11, FR-13, FR-14 | The full suite passes; test edits outside those FRs change only import paths and `mock.patch` targets **[proof: meta — rule about the diff]** |
| NFR-2 | The boundaries hold | `tach check` passes with `exact = true`, no cycle, no `deprecated` edge; manifests match tach; the new modules declare `exposes` equal to tach's interfaces **[proof: arch — tach/lint gate, not pytest]** |
| NFR-3 | No compatibility shims | Importing each old module path (`specweaver.core.flow.engine.task_files`, `...frameworks`, `...handlers.contract_renderers`, `...handlers.validation_hydrator`, `...handlers.archetype_pipelines`) raises `ModuleNotFoundError` |
| NFR-4 | Mutants still find their code | Every mutant anchored in a moved symbol is re-pointed and its `symbol_sha` refreshed; `stale_mutants.py` reports none stale and each re-pointed campaign kills as before **[proof: meta — rule about tests]** |

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | New sub-module `assurance/validation/orchestration`, archetype `orchestrator`, own `context.yaml` and tach module; it may consume `sandbox`, `infrastructure/llm` and `assurance/validation/io` | `assurance/validation` stays pure-logic; the validation CLI and API depend on their own family | Yes — approved by the user on 2026-11-02 |
| AD-2 | New module `workflows/arbitration` (orchestrator, consumes `infrastructure/llm`) | The arbiter is a workflow of its own, beside `workflows/review` | Yes — approved by the user on 2026-11-02 |
| AD-3 | Moved functions take plain values (adapter, config, text, paths); the handler keeps `RunContext` | Moved code never imports `core/flow` (would be a wrong-way edge and a cycle) | No |
| AD-4 | `core/flow/engine/project_paths.py` moves with `archetype_pipelines` into `assurance/validation/orchestration` `[agreed 2026-11-02]` | Its only users are `archetype_pipelines` (`:189`) and `interfaces/api/v1/paths.py:14`; the engine never imports it. `sandbox/security` was rejected: `interfaces/api` forbids `sandbox/*`. The API already needs an edge to the orchestration module for FR-1 | No — inside AD-1's module |
| AD-5 | The language detection call stays with the callers (flow handler, CLI, API); `task_files_for` gets the language `[agreed 2026-11-02]` | Domain modules do not import `sandbox/*` (anti-patterns); `TECH-079` then unifies detection in one place | No |
| AD-6 | No shims at old paths; tests move with the code `[agreed 2026-11-02]` | A shim needs its own tach edge under `exact = true` and keeps the wrong-way import alive | No |
| AD-7 | The step table is one list of rows in `core/flow/engine`; the registry keeps the handler classes, keyed by the same rows | The engine knows no handler (`layer_isolation_and_di.md`) | No |
| AD-8 | `params.mode` on `orchestrate` is refused, not translated | A translation is a second way to say one thing `[agreed 2026-11-02]` | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Moves (SF-01..SF-03), about 2,900 lines and their tests | medium | low: mechanical, the suite guards it |
| Re-pointing 42 mutants | small | low |
| Engine internals (SF-04..SF-06) | medium | medium: the runner is the hot path |
| Summary (SF-07) | small | low |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| `TECH-079`, `TECH-083`, `TECH-084`, `TECH-085` | work on the files in their final homes, once | high |
| Validation users (CLI, API) | the check no longer reaches into the engine | medium |
| Anyone adding a step | one table, roles checked by the reachability test | medium |
| `sw check` and API users | an all-skip run is never "passed" | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| A `mock.patch` string keeps the old path and the test patches nothing | medium | a test proves nothing | NFR-3 makes the old path fail to import, so the patch errors |
| A user's own pipeline YAML has `mode: dual_pipeline` | low | the run refuses to load | FR-11's message names the replacement `[agreed 2026-11-02]` |
| A user script reads `ALL PASSED` or exit 0 for an all-skip file | low | it now sees exit 1 | the decision `[agreed 2026-11-02]`; the user guide says so |
| The runner protocol misses a member | low | mypy fails | mypy runs in the gate |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| `TECH-079` | language tables in `task_files`, `frameworks`, `archetype_pipelines` | one home each before the merge | none here |
| `TECH-083` | `extract_*` in `contract_renderers` | moved with the file; split later | none here |

## Non-Goals

- The findings owned by `TECH-075`..`TECH-091` and `TECH-070` `[agreed 2026-10-22]`.
- Merging the language tables (`TECH-079`) or the model-call shapes (`TECH-085`).
- Persisting `context.feedback` across a resume.
- New behaviour beyond FR-10, FR-11, FR-13 and FR-14.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `pipeline_engine_guide.md` | the one step table and the `dual_pipeline` target | ⬜ |
| `layer_isolation_and_di.md` | handler shells call workflows with plain values | ⬜ |
| `docs/user_guides/2_drafting_effective_specs.md` | `sw check` summary lines and exit codes, `NOTHING CHECKED` | ⬜ |
| `docs/architecture/03_system_topology/module_dependency_graph.md` | the two new modules | ⬜ |

## Sub-Feature Breakdown

### SF-01: Validation orchestration home
- **Scope**: validation policy and drift analysis leave `core/flow` for `assurance/validation/orchestration`.
- **FRs**: [FR-1, FR-2]
- **Inputs**: `validation_hydrator.py`, `archetype_pipelines.py`, `project_paths.py`, `drift.py`.
- **Outputs**: the new module; the CLI, API and handlers import from it.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf01_implementation_plan.md

### SF-02: Implementation home
- **Scope**: task files, frameworks, contract rendering and lint repair leave `core/flow` for `workflows/implementation`.
- **FRs**: [FR-3, FR-4]
- **Inputs**: `task_files.py`, `frameworks.py`, `contract_renderers.py`, `lint_fix.py`.
- **Outputs**: the moved modules and the lint-repair function.
- **Depends on**: SF-01 (`lint_fix` uses `archetype_pipelines`)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf02_implementation_plan.md

### SF-03: Arbitration home and thin handlers
- **Scope**: the arbiter's model work goes to `workflows/arbitration`; no handler calls a model itself.
- **FRs**: [FR-5, FR-6]
- **Inputs**: `arbiter.py`, `validation.py`, `lint_fix.py` (after SF-02).
- **Outputs**: `workflows/arbitration`; handlers within the complexity limit.
- **Depends on**: SF-02
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf03_implementation_plan.md

### SF-04: Runner seams
- **Scope**: the runner's helpers use a typed protocol; handler output keys are named once.
- **FRs**: [FR-7, FR-8]
- **Inputs**: `step_execution.py`, `approval.py`, `session.py`, `fan_out.py`, `sandboxed_execution.py`, `runner.py`, `hydration.py`, `gates.py`, `handover.py`.
- **Outputs**: the runner protocol and the output-key module.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf04_implementation_plan.md

### SF-05: One step table
- **Scope**: a step is declared once; the dual pipeline is a real step; `params.mode` is refused.
- **FRs**: [FR-9, FR-10, FR-11]
- **Inputs**: `models.py`, `registry.py`, `_llm.py`, `decompose.py`, the 11 handlers with roles, `scenario_integration.yaml`.
- **Outputs**: the step table; `orchestrate`+`dual_pipeline`.
- **Depends on**: SF-03
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf05_implementation_plan.md

### SF-06: Feedback keys and names
- **Scope**: `context.feedback` gets declared keys; dead code and duplicate names go.
- **FRs**: [FR-12]
- **Inputs**: `run_context.py`, `gates.py`, `arbiter.py`, `dual_pipeline.py`, `generation.py`, `draft.py`, `scenario.py`, `review.py`, the two assemblers, `interfaces/run_setup/builder.py`.
- **Outputs**: the feedback key module; renamed assemblers; public `roles_of`.
- **Depends on**: SF-05
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf06_implementation_plan.md

### SF-07: Skipped rules are counted
- **Scope**: `sw check` and `POST /check` count skipped rules and never call an all-skip run passed.
- **FRs**: [FR-13, FR-14]
- **Inputs**: rule results.
- **Outputs**: summary lines, exit code, `skipped` and `overall` in the response.
- **Depends on**: SF-01 (`execute_validation_flow` moves there)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf07_implementation_plan.md

## Execution Order

1. SF-01 and SF-04 (no deps; SF-04 may run in parallel)
2. SF-02, then SF-07 (both after SF-01)
3. SF-03 (after SF-02)
4. SF-05 (after SF-03), then SF-06

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Validation orchestration home | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-02 | Implementation home | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-03 | Arbitration home and thin handlers | SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-04 | Runner seams | — | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-05 | One step table | SF-03 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-06 | Feedback keys and names | SF-05 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-07 | Skipped rules are counted | SF-01 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

### Red/Blue (Phase 6), 2 cycles
- R1 (HIGH) AD-4 first put `project_paths.py` in `sandbox/security`; `interfaces/api/context.yaml`
  forbids `sandbox/*` and tach has no `api → sandbox` edge. Fixed: it moves into the orchestration
  module with its only other user.
- R2 (MEDIUM) FR-6 named only `generate`; `generate_with_tools` is the other model call. Fixed.
- R3 (MEDIUM) FR-9 "no handler hard-codes its role" would forbid a handler's call for another task
  (`generation.py:343`, plan). Fixed: only the step's own role comes from the table.
- R4 (MEDIUM) FR-13 shows `N skipped` only when N > 0, and treats "no result" as nothing checked.
  Both refine the agreed answer; approved by the user with the design 2026-11-02.
- R5 (MEDIUM) AD-5 makes up to 7 callers of `task_files_for` pass a language. Accepted: `TECH-079`
  merges detection next; the plan counts the callers that pass `None`.
- R6 (LOW) `pipeline_engine_guide.md:151-155` forbids changing `fan_out()` in
  `OrchestrateComponentsHandler`. The dual handler already branches off before it
  (`decompose.py:373`); FR-10 moves that branch into the table and leaves `fan_out` alone.
- Cycle 2: challenged R1's fix (does the API gain a wrong-way edge?) — no, `interfaces` may depend
  on `assurance`. Challenged AD-2 (fold the arbiter into `workflows/review`?) — no, the user chose a
  module of its own. No new finding above LOW.

**Current status**: Design APPROVED by the user 2026-11-02, with FR-11, FR-13 (R4), AD-4, AD-5,
AD-6, the `INT-US-24` AD-1 reversal and the 7 SFs.
**Next step**: implementation plan for SF-01.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate skill.
