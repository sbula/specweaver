# Design: Domain Logic Lives in the Flow Engine

- **Feature ID**: TECH-082
- **Phase**: Topic 07 (Technical Debt)
- **Status**: COMPLETE (signed off by the user 2026-11-05)
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

It also makes one boundary rule true for the whole project and every language `[agreed 2026-11-03]`:
going down the folder tree, a module gets stricter; a child is wider than its parent only where its
own `context.yaml` declares it in `widens`, with a reason. SpecWeaver checks this rule the same way in
all 9 code languages, on user projects and on its own tree. It found the question in SF-01's plan:
the new orchestration module sits under a pure-logic parent and must use the sandbox and the LLM.

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
| Boundary rule | `context_yaml_spec.md:230-231` says a child only narrows `consumes` and `forbids` add up going down; nothing enforces it. The product checkers read only the nearest `context.yaml` (`python/forbids_checker.py:27`, `java/runner.py:37`, `typescript/runner.py:289`), so one child manifest drops the parent's `forbids` without a word. Kotlin and Rust report "not implemented"; Go, C, C++ and JavaScript have no check. In our tree 15 of 50 nested manifests are wider than their parent (10 are `interfaces`), and 2 use what their parent forbids (`validation/interfaces` → `sandbox/execution`, `graph/interfaces` → `core/config`) |

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
| P-9 | `sw check <code file>` in any of the 9 languages → C05 → shared boundary check → parser imports → effective rules from the folder tree | validation, sandbox language, workspace parsers, topology rules | TECH-082 (FR-15, FR-16, FR-17, FR-19) | ⬜ |
| P-10 | `sw scan` → topology → `tach.toml` with the declared widenings | workspace project, topology rules | TECH-082 (FR-20) | ⬜ |
| P-11 | a project that configures a stricter tool (tach, dependency-cruiser, go-arch-lint) → C05 runs it as an extra | sandbox language, the tool | TECH-082 (FR-20) | ⬜ |
| P-12 | SpecWeaver's own tree → the guard test → the same rule resolver | tests, topology rules | TECH-082 (FR-21) | ⬜ |

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
| FR-5 | `ArbitrateVerdict`, `ArbitrateResult`, `ARBITRATE_INSTRUCTIONS` and the evidence-to-verdict call (prompt in, model call, parse) SHALL live in the new module `workflows/arbitration` `[agreed 2026-11-02]`, and so SHALL the text rules that keep scenario words from the coder and code from the scenario side (`SCENARIO_VOCABULARY`, the coder guard, `scenario_safe`, `code_trace`) `[agreed 2026-11-03]`; `ArbitrateVerdictHandler` SHALL keep the evidence checks, building the trace filter and verdict routing, without `# noqa: C901` | `ArbitrateVerdictHandler` | arbitrate a dual run | the same verdict and routing |
| FR-6 | No module under `core/flow/handlers` SHALL call a model adapter's `generate` or `generate_with_tools` itself (the engine's agentic `work_unit.py` loop is out of scope); `ValidateTestsHandler.execute` and `LintFixHandler` SHALL pass ruff's complexity limit (10) without a `noqa` | the flow handlers | — | only workflows talk to the model |
| FR-7 | Every engine function that takes the runner SHALL type it with one protocol naming the members it uses; no engine module SHALL read or write another object's `_`-prefixed attribute; `PipelineRunner.__init__` SHALL set every attribute those functions read | `core/flow/engine` | run a pipeline | no `runner: Any`, no `getattr(runner, "_…", default)` |
| FR-8 | Each handler output key the engine reads (`plan`, `plan_path`, `results`, `verdict`, `files_touched`) SHALL be named once, in one module both the engine and the writing handler import | the engine, the handlers | pass a step's output | one spelling per key |
| FR-9 | Every `(action, target)` step SHALL be declared once, with its handler, its model role (or none) and whether it is agentic; `VALID_STEP_COMBINATIONS`, the registry rows, `ROLE_OF_STEP` and `AGENTIC_STEPS` SHALL derive from that declaration, and no handler SHALL hard-code its own step's role (a call made for another task, such as `dual_pipeline.py:70`'s check of the two sides' models, keeps its explicit role; corrected 2026-11-04, SF-05 plan F-2) | the engine, the registry, the run builder | load and run a pipeline | one table; `test_handler_reachability.py` also checks roles |
| FR-10 | A step `action: orchestrate`, `target: dual_pipeline` SHALL run `ArbitrateDualPipelineHandler`, and `roles_of` SHALL include its two sides' roles through the table; `scenario_integration.yaml` SHALL use it `[agreed 2026-11-02]` | the YAML loader, the registry, `roles_of` | run `scenario_integration` | the same dual run |
| FR-11 | An `orchestrate` step that carries `params.mode` SHALL be refused when the pipeline loads, with a message that names `target: dual_pipeline` `[agreed 2026-11-02]` | the YAML loader | load an old pipeline | a load error, never a silent fallback |
| FR-12 | Each `context.feedback` key SHALL be declared once with its value type, read through one pop function; the arbiter SHALL take the side step names from the dual pipeline's side table, not literals; the unread `scenario_test_path` write and `FILENAME_PREFIX` SHALL be removed; `mcp_assembler` and `context_assembler` SHALL carry distinct names; `roles_of` SHALL be imported from a public module | the handlers, `interfaces/run_setup` | — | no grab-bag keys, no private import from outside `core/flow` |
| FR-13 | `sw check`'s summary SHALL count SKIP rows: each summary line SHALL add `N skipped` when N > 0, and when no rule judged (every result SKIP, or no result) it SHALL print `NOTHING CHECKED: N skipped` and exit 1 `[agreed 2026-11-02]` | `sw check` | check a file | e.g. `ALL PASSED (3 skipped)`; all-skip exits 1 |
| FR-14 | `POST /api/v1/check` SHALL return a `skipped` count, and `overall: "NOTHING_CHECKED"` when no rule judged `[agreed 2026-11-02]` | the API | check a file | the response says nothing was checked |
| FR-15 | Going down the folder tree a module SHALL get stricter: its effective `forbids` SHALL be its own plus its parent's effective `forbids`, and each of its `consumes` SHALL lie inside its parent's effective `consumes`. A child SHALL be wider only through its own `widens` map, `path: reason` `[agreed 2026-11-03]`, covering both halves `[agreed 2026-11-03]`; an entry with an empty reason, or one that widens nothing, SHALL be refused. A `consumes` entry inside the parent's own folder (a sibling) is not a widening `[agreed 2026-11-03]`. A folder with no `context.yaml` SHALL get its nearest ancestor's effective rules. `context_yaml_spec.md` SHALL say this | the rule resolver | read a folder tree | one effective rule per folder |
| FR-16 | One shared boundary check SHALL judge a code file in each of the 9 languages (`commons.languages.LANGUAGE_SUFFIXES`) by FR-15's effective rules, from the imports its language parser lists; each language SHALL contribute only how an import names a project folder. The Python forbids checker, Java's generated program and the TypeScript ESLint rule SHALL be removed `[agreed 2026-11-03]`. Manifest paths are relative to the project root `[agreed 2026-11-05]`; Python imports under `if TYPE_CHECKING:` count `[agreed 2026-11-05]`; a file no `context.yaml` covers is a C05 SKIP `[agreed 2026-11-05]`; `sw init` writes `tests/context.yaml` with `consumes: [src]` `[agreed 2026-11-05]` (seam: validation → sandbox → parsers) | C05 | check a code file | the same verdict for the same tree in every language |
| FR-17 | An import that names no project folder SHALL not be judged against `consumes`; the result SHALL count such imports `[agreed 2026-11-03]`. An inherited `forbids` entry SHALL still judge it by its written name, `.` and `::` parting it (`sqlalchemy.orm` meets `*.orm`) `[agreed 2026-11-05]` | the shared check | check a file with third-party imports | "N imports not mapped to a project folder" |
| FR-18 | A JavaScript code parser SHALL list the imports of `.js`, `.jsx`, `.mjs`, `.cjs` files `[agreed 2026-11-03]` | the parser factory | parse a JavaScript file | its imports |
| FR-19 | A file whose imports go beyond its folder's effective rules SHALL fail C05; the message SHALL name the file, the import, the folder whose rule it breaks and the `widens` field that would allow it `[agreed 2026-11-03]` | C05 on a user project | check an undeclared widening | a failure that names the fix |
| FR-20 | Where a project configures a stricter boundary tool for its language, the check SHALL run it in addition and report each extra and whether it ran; a tool that is configured but not installed SHALL be reported as not run, never as clean `[agreed 2026-11-03]`: tach (Python, `tach.toml`), dependency-cruiser (TypeScript and JavaScript, `.dependency-cruiser.*`), go-arch-lint (Go, `.go-arch-lint.yml`); `sw scan` SHALL write declared widenings into `tach.toml`. A configured extra that cannot run makes C05 WARN and names it `[agreed 2026-11-05]`; with no `tach.toml` tach is not configured, which retires `D-VAL-05` FR-5's "run `sw scan`" failure `[agreed 2026-11-05]` | C05, `sw scan` | check a project with a tool configured | the shared verdict plus each extra |
| FR-21 | SpecWeaver's own manifests SHALL follow FR-15: every wider child declares `widens` with a reason, and a guard test SHALL check the whole tree with the same resolver the product uses `[agreed 2026-11-03]` | the guard test | — | our tree obeys the rule it ships |

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
| FR-15, FR-21 | every manifest's `consumes`, `forbids` | `TopologyNode` (`consumes`, `forbids`) loaded by `assurance/graph/topology.py:226-228` | read `topology.py:51-66,226-231` |
| FR-16 | a file's imports | `CodeStructureInterface.extract_imports(code) -> list[str]`, 8 parsers today | read `workspace/ast/parsers/interfaces.py:254`, `factory.py:28-47` (no JavaScript entry) |
| FR-16 | where C05 gets its result | `_hydrate_architecture` → atom intent `run_architecture` → each runner's `run_architecture_check` | read `validation_hydrator.py:291`, `kotlin/runner.py`, `rust/runner.py` ("not implemented") |
| FR-18 | the JavaScript grammar | `tree-sitter-javascript>=0.25.0` | read `pyproject.toml:26` (already a dependency) |
| FR-20 | `tach.toml` writing | `sync_tach_toml(graph, target_path)` | read `workspace/project/tach_sync.py:71` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Behaviour stays the same outside FR-10, FR-11, FR-13..FR-20 and FR-8's `files_touched` writers `[agreed 2026-11-05]` | The full suite passes; test edits outside those FRs change only import paths and `mock.patch` targets; one exception: FR-9 changes the routing helpers' arguments and replaces the hand list of model-free steps (`test_llm_for.py:81`) `[agreed 2026-11-04]`; FR-12 merges the two pop functions and removes the `scenario_test_path` write, so their tests (`test_draft_feature_handler.py:400-430`, `test_scenario_handlers.py:351-369`) move to what replaces them `[agreed 2026-11-04]`; the same holds for the third pop function, `DraftSpecHandler._pop_feedback`, and its tests (`test_draft_handler.py:195-222`); FR-7 makes the runner's members public, so test lines that read `runner._x` read `runner.x` `[agreed 2026-11-05]`; SF-09 retires three proven behaviours and their tests move to what replaces them: `C-VAL-03` FR-5's per-file `forbids` merge, `TECH-087` FR-5's Kotlin and Rust SKIP, `D-VAL-05` FR-5's no-`tach.toml` failure `[agreed 2026-11-05]` **[proof: meta — rule about the diff]** |
| NFR-2 | The boundaries hold | `tach check` passes with `exact = true`, no cycle, no `deprecated` edge; manifests match tach; the new modules declare `exposes` equal to tach's interfaces **[proof: arch — tach/lint gate, not pytest]** |
| NFR-3 | No compatibility shims | Importing each old module path (`specweaver.core.flow.engine.task_files`, `...frameworks`, `...handlers.contract_renderers`, `...handlers.validation_hydrator`, `...handlers.archetype_pipelines`) raises `ModuleNotFoundError` |
| NFR-4 | Mutants still find their code | Every mutant anchored in a moved symbol is re-pointed and its `symbol_sha` refreshed; `stale_mutants.py` reports none stale and each re-pointed campaign kills as before **[proof: meta — rule about tests]** |
| NFR-5 | One rule, every language | One fixture tree, written once in each of the 9 languages, gives the same violations and the same unmapped count in each **[proof: integration, parametrized over the 9 languages]** |

## External Dependencies

| Tool | Status | Used for |
|---|---|---|
| `tree-sitter-javascript` | already pinned, `>=0.25.0` (`pyproject.toml:26`), no parser uses it yet | FR-18 |
| tach, dependency-cruiser, go-arch-lint | the project's own tools; SpecWeaver never installs them; run only when the project configures them | FR-20 |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | New sub-module `assurance/validation/orchestration`, archetype `orchestrator`, own `context.yaml` and tach module; it may consume `sandbox`, `infrastructure/llm` and `assurance/validation/io`, declared in its `widens` with reasons, since its parent forbids the first two (FR-15) | `assurance/validation` stays pure-logic; the validation CLI and API depend on their own family | Yes — approved by the user on 2026-11-02 |
| AD-2 | New module `workflows/arbitration` (orchestrator, consumes `infrastructure/llm`) | The arbiter is a workflow of its own, beside `workflows/review` | Yes — approved by the user on 2026-11-02 |
| AD-3 | Moved functions take plain values (adapter, config, text, paths); the handler keeps `RunContext` | Moved code never imports `core/flow` (would be a wrong-way edge and a cycle) | No |
| AD-4 | `core/flow/engine/project_paths.py` moves with `archetype_pipelines` into `assurance/validation/orchestration` `[agreed 2026-11-02]` | Its users are `archetype_pipelines` (`:189`), `interfaces/api/v1/paths.py:14` and `core/flow/handlers/review.py:382` (found in SF-01's plan; the handlers get the edge to the new module anyway); the engine never imports it. `sandbox/security` was rejected: `interfaces/api` forbids `sandbox/*`. The API already needs an edge to the orchestration module for FR-1 | No — inside AD-1's module |
| AD-5 | The language detection call stays with the callers (flow handler, CLI, API); `task_files_for` gets the language `[agreed 2026-11-02]` | Domain modules do not import `sandbox/*` (anti-patterns); `TECH-079` then unifies detection in one place | No |
| AD-6 | No shims at old paths; tests move with the code `[agreed 2026-11-02]` | A shim needs its own tach edge under `exact = true` and keeps the wrong-way import alive | No |
| AD-7 | The step table is one list of rows in `core/flow/engine`; the registry keeps the handler classes, keyed by the same rows | The engine knows no handler (`layer_isolation_and_di.md`) | No |
| AD-8 | `params.mode` on `orchestrate` is refused, not translated | A translation is a second way to say one thing `[agreed 2026-11-02]` | No |
| AD-9 | The rule resolver (effective rules per folder, `widens`) is pure and lives beside the topology model in `assurance/graph`; the product checker, `sw scan` and our guard test all use it `[agreed 2026-11-03]` | One rule, one implementation; `topology.py` already loads `consumes` and `forbids` | No |
| AD-10 | The shared check needs no language runner: it parses and judges `[agreed 2026-11-03]`. Amended: the shared check and one table of FR-20 extras live in `sandbox/language/core`, behind the QA atom's `run_architecture` intent; the runners lose `run_architecture_check` `[agreed 2026-11-05]` | Go, C, C++ and JavaScript have no runner; the rule and the extras must not wait for one | No |
| AD-11 | The list of extra tools in FR-20 covers tools with a CLI and a project config file. ArchUnit (Java) and Konsist (Kotlin) run inside the project's own tests, which C03 already runs; Rust, C and C++ have no common tool `[agreed 2026-11-03]` | Only tools a project already chose are run | No |
| AD-12 | `widens` keys use the same path form as `consumes` (`specweaver/sandbox` or `specweaver/sandbox/*`) `[agreed 2026-11-03]` | One path language in the manifest | No |

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
- New behaviour beyond FR-10, FR-11 and FR-13..FR-21.
- Installing or configuring any extra tool of FR-20 in a user project.
- tach's further checks (interfaces, cycles) for other languages.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `pipeline_engine_guide.md` | the one step table and the `dual_pipeline` target | ✅ (SF-05) |
| `layer_isolation_and_di.md` | handler shells call workflows with plain values | ✅ (SF-03) |
| `docs/user_guides/2_drafting_effective_specs.md` | `sw check` summary lines and exit codes, `NOTHING CHECKED` | ✅ (SF-07) |
| `docs/architecture/03_system_topology/module_dependency_graph.md` | the two new modules | ✅ orchestration (SF-01), implementation (SF-02), arbitration (SF-03) |
| `docs/architecture/03_system_topology/context_yaml_spec.md` | the stricter-going-down rule and `widens` | ⬜ |
| `docs/user_guides/` (the `context.yaml` and `sw check` pages) | `widens`, the C05 message, the unmapped count, the extras | ⬜ |

## Sub-Feature Breakdown

### SF-01: Validation orchestration home
- **Scope**: validation policy and drift analysis leave `core/flow` for `assurance/validation/orchestration`.
- **FRs**: [FR-1, FR-2]
- **Inputs**: `validation_hydrator.py`, `archetype_pipelines.py`, `project_paths.py`, `drift.py`.
- **Outputs**: the new module; the CLI, API and handlers import from it.
- **Depends on**: SF-08 (its new manifest declares `widens`)
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

### SF-08: One boundary rule
- **Scope**: the rule of FR-15 exists once (the resolver), the spec says it, and SpecWeaver's own tree obeys it.
- **FRs**: [FR-15, FR-21]
- **Inputs**: `context_yaml_spec.md`, `assurance/graph/topology.py`, the 74 manifests, `test_manifests_match_tach.py`.
- **Outputs**: the resolver; `widens` on the wider manifests; the guard test.
- **Depends on**: none (runs first `[agreed 2026-11-03]`)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf08_implementation_plan.md

### SF-09: The rule in every language
- **Scope**: one shared check judges all 9 languages; JavaScript gets a parser; user projects fail on undeclared widening; stricter tools run as extras.
- **FRs**: [FR-16, FR-17, FR-18, FR-19, FR-20]
- **Inputs**: the resolver (SF-08), the 8 parsers, the 5 language runners, `validation_hydrator.py` (after SF-01), `tach_sync.py`.
- **Outputs**: the shared check; the JavaScript parser; the old checkers removed.
- **Depends on**: SF-08, SF-01 (C05's hydration moves there)
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-082/TECH-082_sf09_implementation_plan.md

## Execution Order

1. SF-08 (first `[agreed 2026-11-03]`)
2. SF-01 and SF-04 (SF-04 may run in parallel)
3. SF-02, SF-07 and SF-09 (all after SF-01)
4. SF-03 (after SF-02)
5. SF-05 (after SF-03), then SF-06

## Live Demo

Run 2026-11-05 on a fresh project (`sw init`, `SPECWEAVER_DATA_DIR` in a temp folder):

```bash
# src/domain/context.yaml: forbids: [src/infra, "*.orm"]
# src/domain/svc.py:       from src.infra import db / from sqlalchemy.orm import Session
sw check src/domain/svc.py --level code   # C05 FAIL: 2 violations (a project folder, a library by name)
# .dependency-cruiser.cjs present, depcruise not installed
sw check web/app/main.ts --level code     # C05 WARN: "dependency-cruiser is configured but did not run"
```

No model is called, so the nightly real-model run has nothing to add; the same journeys run in
`tests/e2e/capabilities/workspace/test_scan_writes_widenings_e2e.py` and
`tests/integration/sandbox/language/test_boundary_extras_run.py`.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | Validation orchestration home | SF-08 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Implementation home | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Arbitration home and thin handlers | SF-02 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-04 | Runner seams | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-05 | One step table | SF-03 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-06 | Feedback keys and names | SF-05 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-07 | Skipped rules are counted | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-08 | One boundary rule | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-09 | The rule in every language | SF-08, SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

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

**Amendment 2026-11-03**: SF-01's plan found that the spec's inheritance rule (`context_yaml_spec.md:230-231`)
blocks AD-1 and that nothing enforces it. The user chose "stricter going down, wider only when
declared", for the whole project and all 9 languages, inside this ticket (Q1-Q8 and the Q6 addition,
all A). Measured and rejected: rule L "each manifest stands alone" (one file silently drops a parent's
`forbids`) and rule S "only stricter" (forces 10 `interfaces` folders out of their domains).

### Red/Blue on the amendment, 2 cycles
- R7 (HIGH) FR-15 as first written made every top-level module "wider" than the root manifest, since
  siblings are not in a parent's `consumes`. Fixed: a sibling inside the parent's folder is not a widening.
- R8 (MEDIUM) FR-20 did not say what a configured but missing tool reports. Fixed: "not run", never clean.
- R9 (MEDIUM) FR-16's import → folder mapping differs per language (Java packages under source roots,
  C includes, Rust `crate::`). Accepted: each language's mapping is its one contribution; NFR-5's
  shared fixture proves the verdicts agree.
- R10 (LOW) Python users whose `tach.toml` allowed an undeclared widening now fail C05. Intended
  (Q3 A); the message names `widens`.
- Cycle 2: challenged R7 (does a sibling rule let a child reach a forbidden sibling?) — no, inherited
  `forbids` still apply to siblings. No new finding above LOW.

**Current status**: amendment approved by the user 2026-11-03, with AD-9..AD-12, the sibling rule (R7)
and the extra-tool list. Design APPROVED by the user 2026-11-02, with FR-11, FR-13 (R4), AD-4, AD-5,
AD-6, the `INT-US-24` AD-1 reversal and the 7 SFs.
**SF-08 done 2026-11-03** (accepted by the user): resolver, spec, our 18 manifests, guard
(`TECH-082_sf08_walkthrough.md`).
**SF-01 done 2026-11-03** (accepted by the user): validation policy and the drift model call live in
`assurance/validation/orchestration` (`TECH-082_sf01_walkthrough.md`).
**SF-02 done 2026-11-03** (accepted by the user): task files, framework choice, contract rendering
and the lint repair live in `workflows/implementation`; callers get the run language from
`core/flow/engine/run_language.py` (`TECH-082_sf02_walkthrough.md`).
**SF-03 done 2026-11-04** (accepted by the user): the arbiter's verdict, prompt, model call and text
guards live in `workflows/arbitration`; no flow handler calls a model (FR-6 guard)
(`TECH-082_sf03_walkthrough.md`).
**SF-05 done 2026-11-04** (accepted by the user): a step is one row in `STEPS`; handlers get their
role from the step; the dual run is `orchestrate`+`dual_pipeline` and `params.mode` is refused at
load (`TECH-082_sf05_walkthrough.md`).
**SF-06 done 2026-11-05** (accepted by the user): each `context.feedback` key is declared once in
`run_state/feedback.py` and read through one `pop_findings`; the arbiter takes the side steps from
the side table; `FILENAME_PREFIX` is gone; `skeleton_assembler` and `mcp_assembler` have distinct
titles; `roles_of` is public in `handlers/roles.py` (`TECH-082_sf06_walkthrough.md`).
**SF-04 done 2026-11-05** (accepted by the user): the runner's helpers take it as a `RunnerPort`
and read only its public members; the step output keys are named once in `engine/step_outputs.py`;
the code, test and contract steps write `files_touched`, the scenario steps do not
(`TECH-082_sf04_walkthrough.md`).
**SF-07 done 2026-11-05** (accepted by the user, `2367216c`): `sw check` and `POST /check` share one
`summarize`; each line adds `(N skipped)`; no rule judged is `NOTHING CHECKED` and exits 1; the
executor's run log counts a skip as skipped (`TECH-082_sf07_walkthrough.md`).
**SF-09 plan approved 2026-11-05** (the user): Q1..Q6 all A (project-root paths, `TYPE_CHECKING`
counts, shared check and extras in the sandbox, no-manifest SKIP, no `tach.toml` is no tach, a
missing extra is WARN); three commit boundaries.
**SF-09 done 2026-11-05** (accepted by the user, `2f07437e`, `0d6649bf`, `d576044b`): one shared
check in `sandbox/language/core/boundary_check.py` judges C05 in all 9 languages from the
`context.yaml` tree; a library meets only `forbids`, by its written name (Q8); tach,
dependency-cruiser and go-arch-lint run as configured extras, and one that did not run is WARN
(`TECH-082_sf09_walkthrough.md`).
**Closed 2026-11-05**: closure gate passed (21 of 21 FRs proven); signed off by the user.
**Next step**: none. TECH-079 is next in the backlog.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate skill.
