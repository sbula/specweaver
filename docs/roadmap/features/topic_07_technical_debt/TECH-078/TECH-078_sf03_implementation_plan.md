# Implementation Plan: Review, Validation and the API Still Assume Python [SF-03: The API's implement and the planner]
- **Feature ID**: TECH-078
- **Sub-Feature**: SF-03 — The API's implement and the planner
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-4 (`POST /implement` runs the same implement pipeline as `sw implement` and reports the task's
files) and FR-5 (the planner is told the project's language by its language guide's name). NFR-1
(Python as before) applies. Kind `bugfix`. Depends on SF-02 (committed: every step finds the task's
files without a per-task parameter).

## Research Notes

Read 2026-10-24.

- **`POST /implement`** (`interfaces/api/v1/implement.py`): a 2-step pipeline (`generate_code`,
  `generate_tests`) through `run_steps` (`interfaces/api/v1/_llm.py`, the run builder the CLI uses);
  a run that does not complete answers 500 `GENERATION_FAILED` with the first step error; a spend
  stop answers 402 `SPEND_LIMIT`; it answers `ImplementResponse(code_path, test_path,
  unwritten_calls)` with **Python paths** (`src/<stem>.py`, `tests/test_<stem>.py`) whatever the
  language.
- **`sw implement`** (`workflows/implementation/interfaces/cli.py:35`):
  `_build_implement_pipeline(files: TaskFiles | str)` builds 6 steps — `generate_code`,
  `generate_tests`, `lint_fix` (target the task's code, 3 reflections, report-only), `run_tests`
  (target the task's tests, `kind: unit`, coverage, loops back to `generate_code` at most 2 times),
  `validate_code` (target the task's code, report-only), `acceptance` (report-only). The task files
  come from `task_files_for(project, spec, language)` with the project's `[implement]` language
  (`_core.project_sections_at`). Exit 1 when `run_tests` still fails, or on a spend stop.
- **Users of the builder**: the CLI, `test_implement_pipeline.py` (11), `test_one_module_name.py`,
  `test_task_files_agree.py`, `test_acceptance_step.py`.
- **Layering**: `workflows/implementation` may import only `infrastructure.llm` (`tach.toml`), and
  `core/flow` imports `workflows.*`; the builder needs `core.flow.engine.models`, so it **cannot**
  live in `workflows/implementation` (design AD-2 assumed it could). `core/flow` is importable by
  both doors (`workflows.implementation.interfaces` and `interfaces.api`).
- **The run builder** sets `isolation.language` from `[implement]`
  (`interfaces/run_setup/builder.py:91`), so the API's run already knows the language; the task
  files for the response need the same value before the run.
- **Planner** (`workflows/planning/planner.py:28`): `_SYSTEM_PROMPT` says "for a Python project".
  The only constructor call is `PlanSpecHandler` (`core/flow/handlers/generation.py:402`).
  `lint_fix` already names the language this way: `language_guide(task_files_for(...).language,
  root).name` (`lint_fix.py`). `language_guide` raises `ValueError` outside the five languages.

- **Bundled pipelines are data**: `workflows/pipelines/*.yaml`, loaded by
  `core/flow/engine/parser.load_bundled_pipeline(name)`. `new_feature.yaml` already holds
  `generate_code`, `generate_tests`, `run_tests` (`kind: unit`, coverage, loop to `generate_code`,
  2 retries), `validate_code` and `acceptance` with no file names.
- **A live defect found here**: with no `target`, `default_test_target` gives a Python run
  `<output_dir>/test_<stem>.py`, and a door's run sets `output_dir = <project>/src`
  (`run_setup/builder.py:102`), so `run_tests` looks in `src/test_<stem>.py` while `generate_tests`
  writes `tests/test_<stem>.py` (`generation.py:141`). `sw run new_feature` on Python is hit today.
- **`lint_fix` with no `target`** lints `src/` (`lint_fix.py:71`); no bundled pipeline has a
  `lint_fix` step yet.

## Decisions (Phase 4, user 2026-10-24)

1. The implement steps become a bundled pipeline, `workflows/pipelines/implement_spec.yaml`, loaded
   by name by both doors; no Python step list remains. Design AD-2 ("the builder moves to
   `workflows/implementation`") is replaced: that module may not import the flow engine, and the
   engine already runs every other built-in pipeline from YAML `[agreed 2026-10-24]`.
2. When the tests still fail after the loop, `POST /implement` answers 200 with `status: "failed"`
   and what `sw implement` prints: tests passed/failed and coverage, lint errors left, validation
   passed/total and its failed rules. A generation error stays 500 `GENERATION_FAILED`, a spend stop
   402 `SPEND_LIMIT` `[agreed 2026-10-24]`.

Settled by the design, not asked: the API runs the same 6 steps with the same gates
`[agreed 2026-10-23]`; it reports the task's files; the planner names the language by
`language_guide(...).name`; a request takes minutes (the user guide says so). FR-1 settles the two
defaults below: a step with no target works on the task's file, so `run_tests` runs the task's
tests file in Python too, and `lint_fix` lints the task's code file.

## Approach (pseudocode, ordered)

**CB-1 — the planner names the language (FR-5)**
1. `Planner(..., language: str)` (the display name, keyword, required): the system prompt says "for
   a `<language>` project".
2. `PlanSpecHandler` passes `language_guide(task_files_for(project, spec, run language).language,
   project).name`; a `ValueError` (unknown language, bad `Package` line) is the step's error.

**CB-2 — one implement pipeline behind both doors (FR-4, and FR-1's two defaults)** — closes SF-03
3. `default_test_target` (non-scenario kinds): the task's tests file for every language,
   `<project>/<task_files_for(...).tests>`, where `generate_tests` writes it.
4. `lint_fix` with no `target` lints the task's code file (`task_code_file`, relative to the
   project); an explicit `target` is used as today.
5. `workflows/pipelines/implement_spec.yaml`: the 6 steps and gates of today's builder, with no file
   names (`lint_fix` `max_reflections: 3`, report-only; `run_tests` `kind: unit`, coverage, loop to
   `generate_code`, 2 retries; `validate_code` and `acceptance` report-only).
6. `sw implement` loads it with `load_bundled_pipeline("implement_spec")`; its output does not
   change. `_build_implement_pipeline` goes; its tests move to the YAML.
7. `POST /implement`: `task_files_for(project_root, spec_path, [implement] language)` (a `ValueError`
   answers 400 naming the spec line); load the pipeline; `run_steps` as today. A run that completed
   → 200 `status: "completed"`; a run stopped by a failed `run_tests` → 200 `status: "failed"`; any
   other stop → 500 as today. The response: `code_path`, `test_path` (the task's files), `status`,
   `tests` (`passed`, `failed`, `coverage_pct`), `lint_errors_remaining`, `validation` (`passed`,
   `total`, `failed_rules`), `unwritten_calls`.
8. Docs: the user guide (`POST /implement` takes minutes and what it answers);
   `pipeline_engine_guide.md` (`implement_spec`; `lint_fix` and `run_tests` defaults); design AD-2.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/workflows/planning/planner.py` | [MODIFY] `language` argument |
| `src/specweaver/core/flow/handlers/generation.py` | [MODIFY] `PlanSpecHandler` passes the language |
| `src/specweaver/core/flow/handlers/qa_targets.py` | [MODIFY] `default_test_target` |
| `src/specweaver/core/flow/handlers/lint_fix.py` | [MODIFY] default linter target |
| `src/specweaver/workflows/pipelines/implement_spec.yaml` | [NEW] |
| `src/specweaver/workflows/implementation/interfaces/cli.py` | [MODIFY] loads the pipeline |
| `src/specweaver/interfaces/api/v1/implement.py`, `schemas.py` | [MODIFY] pipeline, paths, outcome |
| `tests/unit/workflows/planning/test_planner_language.py` | [NEW] |
| `tests/integration/core/flow/handlers/test_plan_names_the_language.py` | [NEW] P-4 |
| `tests/unit/workflows/implementation/test_implement_pipeline.py` | [MODIFY] reads the YAML |
| `tests/integration/interfaces/api/test_api_implement_languages.py` | [NEW] P-3 |
| `tests/unit/core/flow/handlers/test_step_defaults.py` | [NEW] the two defaults |
| `test_one_module_name.py`, `test_task_files_agree.py`, `test_acceptance_step.py`, `test_implement.py` | [MODIFY] |

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | `Planner` system prompt names the language given | FR-5 | the prompt says Python |
| integration | P-4: a Rust project's `plan` step (doubled LLM, recording) → the system message says "Rust project" | FR-5 (seam: handler → planner) | the planner is told Python |
| unit | `run_tests` with no target runs `tests/test_<stem>.py` on Python with `output_dir = src`; `lint_fix` with no target lints the task's file | FR-1 | `src/test_<stem>.py`; `src/` |
| unit | `implement_spec.yaml` loads; its 6 steps, gates and params equal today's builder's | FR-4 | no such pipeline |
| integration | P-3: `POST /implement` on a TypeScript project (doubled LLM, tool double as in `test_implement_in_every_language_e2e.py`) → the 6 steps run; the response names `src/<stem>.ts`, `tests/<stem>.test.ts`; failing tests → 200 `status: "failed"` with the counts | FR-4 (seam: API → bundled pipeline → flow) | 2 steps, `.py` paths, 500 |
| integration | `sw implement` and `POST /implement` run the same step names on one project | FR-4 (one pipeline) | the API has its own steps |

Mutants: the language in the planner prompt; the handler's language argument; the Python tests
default (`output_dir` back); the `lint_fix` default (`src/` back); the API's pipeline (2 steps back);
the API's reported paths (Python layout back); the failed-tests answer (500 back).

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–2, their tests, P-4 | full suite green; the FR-5 mutants killed |
| CB-2 | steps 3–8, their tests, P-3, docs | full suite green; the FR-4 and FR-1 mutants killed; stage and stop (closes SF-03) |

## Documentation

User guide (`1_installation_and_setup.md`): `POST /implement`. `pipeline_engine_guide.md`:
`implement_spec`, the `lint_fix` and `run_tests` defaults. Design AD-2 replaced (decision 1).

## Architecture Verification (Phase 3)

- The design's AD-2 location breaks `tach` (cycle `core.flow` → `workflows.implementation` →
  `core.flow`); decision 1 adds no import: the engine reads one more bundled YAML file.
- `PlanSpecHandler` (`core/flow`) already imports `workflows.implementation.languages` through
  `lint_fix`'s pattern and `task_files_for`; no new edge. `workflows/planning` gains no import.
- Both doors call `core.flow.engine.parser.load_bundled_pipeline`; both already depend on `core.flow`.

## Consistency Check and Red/Blue (Phase 5)

- Every FR of SF-03 has a step and a test: FR-4 (steps 5–7, P-3, the two-door test), FR-5 (steps
  1–2, P-4). The FR-1 defect found here (steps 3–4) has its own tests and mutants. NFR-1: the full
  suite before each commit. No open question.
- Red/Blue, 2 cycles:
  - R1 (MEDIUM) a project pipeline with `lint_fix` and no target now lints the task's file, not
    `src/`. Blue: FR-1's rule; the pipeline guide says so; an explicit target keeps the old reach.
  - R2 (MEDIUM) `implement_spec` becomes runnable by `sw run` and `/pipelines/implement_spec/run`.
    Blue: the same steps; those doors print their generic report. Accepted.
  - R3 (MEDIUM) a client reading only the HTTP code sees 200 for failing tests. Blue: decision 2;
    `status` is in the response and the guide.
  - R4 (LOW) the YAML's description cannot name the task's file. Blue: `sw implement` prints the
    paths itself.
  - Cycle 2: no new finding.
