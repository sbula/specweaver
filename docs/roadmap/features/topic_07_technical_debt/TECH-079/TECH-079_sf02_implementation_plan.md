# Implementation Plan: Language and Toolchain Are Decided in a Dozen Places That Disagree [SF-02: Every caller asks it]
- **Feature ID**: TECH-079
- **Sub-Feature**: SF-02 — Every caller asks it
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-079/TECH-079_sf02_implementation_plan.md
- **Status**: APPROVED (the user, 2026-11-06)

## Scope

Every whole-project caller takes the language and build tool from the one profile (SF-01,
`ee2da570`); the factories take the language as a required argument; the refusal reaches the CLI
and the API. FRs: **FR-7, FR-8, FR-14**. NFRs: NFR-1 (only guess-pinning tests change), NFR-2 (the
new edge `core.flow.engine → workspace.project`), NFR-3 (no shims), NFR-4 (a run decides once),
NFR-5 (mutants re-pointed). Paths: P-1, P-2, P-3, P-4. SF-03 adds the framework; SF-04 removes the
other ending tables. The second edge of AD-2 (`assurance.validation.orchestration →
workspace.project`) belongs to SF-03 (FR-9); SF-02 does not need it (F4).

Today (measured 2026-11-06):

- Language. `core/flow/engine/run_language.py:22` `run_language(project_root, language)` = the
  `[implement] language` pin, else `sandbox/language/core/detect.py:33` `detect_language(cwd)`.
  `RunContext.isolation.language: str | None` (`run_state/run_context.py:65`) carries the pin only;
  the run builder sets it (`interfaces/run_setup/builder.py:92,105,135`).
- Callers of `run_language`/`run_task_files`: `interfaces/api/v1/implement.py:91`,
  `workflows/implementation/interfaces/cli.py:178`, `core/flow/engine/isolation.py:59` (and `:58`
  hard-codes `python` when no project root), `core/flow/engine/sandboxed_execution.py:122`,
  handlers `qa_targets.py:79,87`, `lint_fix.py:310`, `generation.py:117,389,499` (the contract's
  language at `:500`).
- Factories that detect on their own: `runner_factory.resolve_runner(cwd, executor, language=None)`
  (`:44`, ladder `_runner_class:63`, unknown → Python); `create_scenario_converter(cwd)`
  (`scenario_converter_factory.py:33`); `create_stack_trace_filter(cwd)`
  (`stack_trace_filter_factory.py:21`); `LanguageAtom(cwd)` (`language/core/atom.py`, intents
  `detect_language` — no caller in `src` — and `convert_scenario`, used by
  `handlers/scenario.py:196`). Ladders with a Python default: `contract_renderers.render_contract:350`,
  `task_files.task_files_for:61`. `render_contract_file:485` too (check at dev).
- Build tool. `workspace/project/prepare_plan.py:132` `detect_toolchain(source_root)` (uv first,
  then cargo, maven, gradle; never npm). Users: `plan_for(source_root):180`,
  `sandbox/execution/sandbox_image._resolve_image(source_root):58`, `sandbox_ready(project_root):136`
  (via `qa_runner/core/atom.container_available`, called by `handlers/acceptance.py:74`,
  `dual_pipeline.py:189`, `coder_sandbox.py:29`), `container_executor.py:104,144,153,197,514,521`,
  `handlers/dual_pipeline.py:51`, `interfaces/cli/routers/sandbox_router.py:49` (`sw sandbox preflight`).
- QA atom. `runner_factory.qa_atom(cwd, language=None, sandbox_settings=None, scenarios_root=None)`;
  callers `handlers/lint_fix.py:275`, `handlers/validation.py:499,504`,
  `assurance/validation/orchestration/validation_hydrator.py:128` (language from the run, or None
  from `sw check` and `POST /api/v1/check`, which never pass `sandbox_settings`: always host).
- Doors that build a run: `run_doors.build_run_or_exit` (`sw run`/resume via
  `core/flow/interfaces/cli.py:249`, `sw implement`, `sw draft`, `sw review`, and `run_one_step` for
  `sw standards`, `sw drift`); `api/v1/run_doors.build_api_run` (`POST /pipelines/{name}/run`,
  `/runs/{id}/resume`, review, standards); `POST /api/v1/implement` builds its run in `_llm.run_steps`
  after computing the task files at `implement.py:52`.
- tach: `core.flow.engine` depends on `run_state, core.config, infrastructure.llm, sandbox,
  workflows.implementation, workspace, workspace.memory`; the sandbox module exposes
  `language.core.detect.detect_language`; workspace.project exposes `prepare_plan.detect_toolchain`.
- `RunContext(` is built in `src` only by the run builder; tests build it in 166 files (383 places).

## Findings (Phase 4)

| # | Sev | Question | Options | Proposal |
|---|---|---|---|---|
| Q1 | HIGH | Session isolation is on (`enforce_session_isolation` or DAL escalation), and the profile is undecided, on a door that does not refuse (`sw draft`, `sw review`). Today `apply_session_policy` swallows the failure and runs **without** session isolation (`isolation.py:108`) | A: refuse the run, naming `[implement] language`; B: keep today's fallback (no session isolation) | **Refuse the run, naming `[implement] language` `[agreed 2026-11-06]`** |
| Q2 | MEDIUM | `POST /pipelines/{name}/run` and `/runs/{id}/resume` are the API twins of `sw run`; FR-8 names only `POST /api/v1/implement` | A: refuse with 400 `PROJECT_UNDECIDED`, like `sw run`; B: start the run; the first step that needs the language fails naming the setting | **Refuse with 400 `PROJECT_UNDECIDED` `[agreed 2026-11-06]`** |
| F1 | MEDIUM | The design names `sw sandbox prepare`; the command is `sw sandbox preflight` (`sandbox_router.py:39`) | the plan uses `preflight`; the design line was corrected at approval | a typo, not a scope change |
| F2 | MEDIUM | How a run carries the profile | `IsolationPolicy.language` → `profile: ProjectProfile \| None` and `undecided: str \| None`; the builder sets one of them; `run_profile(context)` returns the profile, raises `ProjectUndecidedError(undecided)`, or — when neither is set (a context a test built) — decides from `project_path` with no pins and stores it | AD-3: decided once at the start; no hidden Python default (FR-5); 383 test constructions need no change unless they reach a language |
| F3 | MEDIUM | Where `sw run` and the API run doors refuse | `RunRequest.needs_profile: bool = False`; `build_run` raises `ProjectUndecidedError` when it is True and the profile is undecided; `build_run_or_exit` prints it and exits 1; `build_api_run` maps it to 400 `PROJECT_UNDECIDED`. `sw implement` and `POST /api/v1/implement` keep computing the task files before the run, now from `read_project_profile` with the pins, and refuse there | FR-8: refused before any run starts; the other doors carry the refusal and only a step that needs the language fails |
| F4 | MEDIUM | `sw check` and `POST /api/v1/check` on one code file (no run) | the QA atom's language is the file's (`commons.language_of`), on the host; a language SpecWeaver does not generate (a `.go` file) gets no QA atom and C03/C04 report SKIP naming the language | FR-8 "keeps using that file's ending"; FR-5 "no part falls back to Python" (today a `.go` file gets pytest) |
| F5 | MEDIUM | TypeScript in the sandbox | `plan_for(root, "npm")` returns route `none` with an npm warning (today it falls to the Gradle text, `prepare_plan.py:349`); the image stays the Python one (non-goal) | SF-01 F10 agreed "no prepare for npm, as today" |
| F6 | MEDIUM | The dual run on a TypeScript project | `build_tool` `npm` is not `uv`/`""`, so the dual run refuses ("proven for Python projects only"); today a TS root without `pyproject.toml` passes the check | the check's own message; a behaviour change FR-7 brings, named in the walkthrough |
| F7 | MEDIUM | Factory signatures (FR-14) | `resolve_runner(cwd, executor, language)`, `create_scenario_converter(language)`, `create_stack_trace_filter(language)`, `LanguageAtom(cwd, language)`, `render_contract`/`render_contract_file`/`task_files_for` with the language as today; each chooses from one dict and raises `ValueError("no <thing> for language 'go'")` for an unknown one; matching is exact (the profile only yields lower-case names) | one table per factory; `_runner_class` disappears |
| F8 | MEDIUM | The build tool's path into the sandbox | `plan_for(root, build_tool)`, `_resolve_image(root, build_tool)`, `sandbox_ready(root, build_tool)`, `container_available(root, build_tool)`, `ContainerSubprocessExecutor(..., build_tool=)`; `qa_atom(cwd, profile, ...)`; handlers pass `run_profile(context)` | no module reads the root for the build tool again |
| F9 | LOW | `detect.py` | deleted whole: `SUPPORTED_LANGUAGES` and `_SCENARIO_EXTENSIONS` have no other user; the converter already names its output file (`output_path`) | NFR-3; SF-04 removes the other copies of the language set |
| F10 | LOW | `LanguageAtom`'s `detect_language` intent | removed (no caller in `src`) | YAGNI |
| F11 | LOW | `infrastructure/llm/prompt/constants.detect_language(path)` | stays: a per-file code-fence name, not project detection; SF-04 (FR-12) moves it onto `commons` | out of SF-02's scope; NFR-3 names the sandbox one |
| F12 | LOW | The error type at the doors | `ProjectUndecidedError` (SF-01 F1), never caught as `ValueError` (`implement.py:91` maps `ValueError` to `SPEC_INVALID`) | the right error code |
| F13 | LOW | Docs | `1_installation_and_setup.md` §6c (the pins, `build_tool`, the refusals, no detection order); `language_support_guide.md` (detection lives in `commons`); the API doc for `PROJECT_UNDECIDED` | SF-01 F8 deferred §6c to here |
| F14 | LOW | `tests/integration/commons/test_profile_agrees.py` | its second half (agreement with the two detectors) is deleted with them in CB-2/CB-3 | said in SF-01 |

## Proposed Changes

### `core/flow` (run state, engine, handlers)

#### [MODIFY] `core/flow/run_state/run_context.py`
`IsolationPolicy`: `language` → `profile: ProjectProfile | None = None` and
`undecided: str | None = None` (F2).

#### [RENAME+MODIFY] `core/flow/engine/run_language.py` → `run_profile.py`
- `run_profile(context) -> ProjectProfile`: the stored profile; `undecided` → raise; neither → read
  the root (`workspace.project.read_project_profile`, lazy import) and replace `context.isolation`
  with a copy holding it, so later calls do not read again.
- `run_task_files(context)` uses `run_profile(context).language`. `run_language` is gone.

#### [MODIFY] `core/flow/engine/isolation.py`, `sandboxed_execution.py`
`derive_allowed_paths(spec_path, project_root, language)`: all required; the `python` branch goes.
`_task_paths` and the strip-merge call pass `run_profile(context).language`.
`apply_session_policy`: an undecided profile with session isolation on raises past the
best-effort guard (Q1 A), so the run does not start.

#### [MODIFY] handlers
`qa_targets.py`, `arbiter.py`, `scenario.py`, `lint_fix.py`, `validation.py`, `generation.py`,
`dual_pipeline.py`, `acceptance.py`, `coder_sandbox.py`: pass `run_profile(context)` (or its
`.language` / `.build_tool`) to the factories and sandbox functions.

#### [MODIFY] `core/flow/engine/context.yaml`, `tach.toml`
`core.flow.engine` consumes / depends on `workspace.project` (AD-2, edge 1).

### `interfaces`

#### [MODIFY] `interfaces/run_setup/builder.py`
`_sections` returns the whole `ImplementPolicy`; `build_run` calls `read_project_profile(root,
language=, build_tool=)` once; a refusal sets `undecided`, and raises when
`request.needs_profile` (F3).

#### [MODIFY] `interfaces/run_doors/run_doors.py`, `core/flow/interfaces/cli.py`
`build_run_or_exit(..., needs_profile=False)` catches `ProjectUndecidedError` whatever `needs_profile`
says (Q1 raises it from any door), prints it and exits 1; `sw run` and resume pass True.

#### [MODIFY] `interfaces/api/v1/run_doors.py`, `pipelines.py`, `implement.py`
`build_api_run(..., needs_profile=False)` maps the refusal, from any door, to `SpecWeaverAPIError(detail=msg,
error_code="PROJECT_UNDECIDED", status_code=400)`; run and resume pass True (Q2 A).
`implement._task_files` uses `read_project_profile` with both pins; a refusal is that 400.

#### [MODIFY] `workflows/implementation/interfaces/cli.py`, `interfaces/cli_kit/_core.py`
`sw implement` takes the task files from `read_project_profile` with both pins; a refusal prints
and exits 1. `project_sections_at` returns the whole `ImplementPolicy`.

#### [MODIFY] `interfaces/cli/routers/sandbox_router.py`
`sw sandbox preflight` reads `[implement]` (`load_section_at`), decides the profile, prints a
refusal and exits 1; else `plan_for(root, profile.build_tool)`.

### `sandbox`

#### [DELETE] `sandbox/language/core/detect.py` (F9)
#### [MODIFY] `runner_factory.py`, `scenario_converter_factory.py`, `stack_trace_filter_factory.py`, `atom.py` (F7, F8, F10)
#### [MODIFY] `sandbox/execution/sandbox_image.py`, `container_executor.py`, `sandbox/qa_runner/core/atom.py` (F8)
#### [MODIFY] `tach.toml` sandbox `expose`: `language.core.detect.detect_language` removed.

### `workspace/project`

#### [MODIFY] `prepare_plan.py`
`plan_for(source_root, build_tool)`; `detect_toolchain` and `_TOOLCHAIN_MANIFESTS` gone; an `npm`
branch in `_plan_for_other` (F5). `context.yaml` and tach `expose` drop `detect_toolchain`.

### `workflows/implementation`

#### [MODIFY] `contract_renderers.py`, `task_files.py`
One dict per ladder; an unknown language raises `ValueError` naming it (F7). `contract_extension`
(`:46`, falls back to `py`) raises too; SF-04 moves its table onto `commons`.

### `assurance/validation/orchestration`

#### [MODIFY] `validation_hydrator.py`
`hydrate_code_validation_context(..., profile: ProjectProfile | None)`: None (no run) → the code
file's language, host executor; a language not in `GENERATED_LANGUAGES` → no QA atom, so the QA
rules SKIP (F4). No new import of `workspace.project`. `execute_validation_flow`'s `language` parameter becomes
`profile` too; `handlers/validation.py:264` passes `run_profile(context)`.

## Commit Boundaries

### CB-1: the run carries the profile; the refusal reaches the doors (FR-7 run part, FR-8)
`IsolationPolicy.language` goes in this boundary, so every reader of it changes here too:
`lint_fix.py:277`, `validation.py:264,501,505` pass `run_profile(context).language` to the
signatures as they are today; CB-2 and CB-3 change those signatures.
Tests first, red because `profile`, `needs_profile` and `run_profile` do not exist:

| Bucket | Case |
|---|---|
| Happy | `build_run` on a Python root stores `ProjectProfile("python","uv")`; a pinned mixed root stores the pin; task files and the allow-list follow it |
| Boundary | a context with neither field set decides once from the root (a second call reads nothing: count `iterdir` with a spy on the reader seam) |
| Degradation | an undecided root on `sw draft` builds the run; the first step that asks fails with the message |
| Hostile | `sw run` and `sw implement` on pyproject+package.json+tsconfig print the refusal and exit 1, no step runs; `POST /api/v1/implement` and `POST /pipelines/{name}/run` answer 400 `PROJECT_UNDECIDED`; session isolation on + undecided → no run (Q1) |

Files: `tests/integration/interfaces/run_setup/test_run_carries_the_profile.py` (seam builder →
reader → context), `tests/integration/interfaces/cli/test_undecided_project_is_refused.py`
(CliRunner over `sw run`, `sw implement`), `tests/integration/interfaces/api/test_undecided_project_is_refused.py`,
`tests/unit/core/flow/engine/test_run_profile.py` (replaces `test_run_language.py`). Tests that
pin the guess change (NFR-1): `test_run_language*.py`, `test_build_run.py`, `test_qa_follows_the_run_language.py`,
the doc-policy door tests that pass `language=`.

Mutants: `run-profile-ignores-undecided` (returns a Python profile instead of raising),
`needs-profile-ignored` (`build_run` never raises), `isolation-python-default` (restores the
`python` branch), `session-policy-swallows-undecided`.

### CB-2: the factories take the language (FR-14, FR-7 language part)
Tests first, red because the factories still detect: a root with `pyproject.toml`, `package.json`
and `tsconfig.json` pinned to `python` gets `PythonQARunner`, the Python converter and filter, and a
Python contract (today `detect_language` says typescript).

| Bucket | Case |
|---|---|
| Happy | each of the five languages gets its runner, converter, filter, contract renderer and task files from one table |
| Boundary | `sw check` on a `.kt` file in a Python project runs the Kotlin runner on the host (F4) |
| Degradation | `sw check` on a `.go` file: C03 SKIP naming go, no pytest (F4) |
| Hostile | `"go"`, `"Python"`, `""` → `ValueError` naming the value, from each factory |

Files: `tests/integration/core/flow/handlers/test_every_part_takes_the_run_language.py` (seam
handlers → factories, the pinned mixed root above), unit tests beside each factory
(`test_runner_factory.py`, `test_scenario_converters.py`, `test_stack_trace_filters.py`,
`test_contract_renderers.py`, `test_task_files.py`, `test_language_atom.py`), and
`test_detect_is_gone.py` (NFR-3: `ImportError` for `detect_language`, `detect_scenario_extension`).
Delete `test_detect.py` and the detector half of `test_profile_agrees.py`.

Mutants: `runner-unknown-is-python`, `converter-unknown-is-python`, `filter-unknown-is-python`,
`contract-unknown-is-python`, `contract-extension-unknown-is-py`, `task-files-unknown-is-python`, `check-go-runs-pytest`.

### CB-3: the build tool from the profile (FR-7 sandbox part) — closes SF-02
Tests first, red because `plan_for` still detects: a root with `pyproject.toml` and `Cargo.toml`
pinned to `rust` gets the cargo plan, the rust image, no `PATH` rewrite, and the dual run refuses
(today: uv, the Python image).

| Bucket | Case |
|---|---|
| Happy | each build tool → its plan and image; `sw sandbox preflight` shows the pinned tool |
| Boundary | python with only `requirements.txt` → build tool `""`, the plan as today; npm → route `none` with the npm warning (F5) |
| Degradation | Gradle stays "cannot be prepared yet" |
| Hostile | `sw sandbox preflight` on a mixed root prints the refusal, exit 1; a TypeScript dual run refuses (F6) |

Files: `tests/integration/sandbox/execution/test_sandbox_takes_the_build_tool.py` (seam handlers →
`container_available`/`qa_atom` → executor → plan and image; the container itself is not started —
the engine probe and `ensure` are the existing injected seams), `test_prepare_plan_languages.py`
(changes per NFR-1), `tests/integration/interfaces/cli/test_sandbox_preflight_profile.py`,
`test_detect_toolchain_is_gone.py` (NFR-3). Delete the rest of `test_profile_agrees.py`'s detector half.

Mutants: `plan-ignores-build-tool`, `image-ignores-build-tool`, `npm-plan-is-gradle`,
`dual-run-allows-npm`, `preflight-ignores-pins`.

Each boundary: `scripts/tests.py cb TECH-079 --kind bugfix`, `quality.py cb`, `tach check`, `mypy`,
then the pre-commit skill. NFR-5 at each: `stale_mutants.py` reports no stale mutant.

## Verification
- `python scripts/tests.py sf TECH-079 --kind bugfix` at the end of CB-3.
- `check_fr_coverage.py TECH-079` cites FR-7, FR-8, FR-14.
- Live: `sw implement` on a temp root with `pyproject.toml` and `package.json` prints the refusal;
  with `[implement] language = "python"` it writes `.py` files.

## Research Notes
- `IsolationPolicy` is `frozen=True, extra="forbid"`; a stdlib frozen dataclass is a valid pydantic
  v2 field type, so `ProjectProfile` needs no model of its own.
- `apply_session_policy` (`isolation.py:84`) wraps everything in `except Exception`; Q1 A needs the
  undecided case raised outside that guard (decide before `try`).
- `sandboxed_execution.py:122` derives the allow-list again when `allowed_paths` is empty; it gets
  the run's language from `run_profile`, so the merge and the grant stay one list.
- `prepare_plan._plan_for_other` ends in an unconditional Gradle `PreparePlan`
  (`prepare_plan.py:349`); an `npm` value would fall into it without F5's branch.
- `sw check` (`assurance/validation/interfaces/cli.py:297`) and `POST /api/v1/check`
  (`interfaces/api/v1/validation.py:113`) pass no `sandbox_settings`, so their QA atom always runs
  on the host and needs no build tool.
- The run builder is the only `RunContext(` in `src` (`builder.py:99`).
- `run_profile`'s fallback stores the decision with `model_copy`; the engine isolates a step with
  `copy.copy(context)`, so a decision made inside a step copy does not reach the original. Only
  test-built contexts take the fallback; the builder always sets `profile` or `undecided`.
- `sw implement` and `POST /api/v1/implement` decide at the door (to refuse before the run) and the
  run builder decides again: two root listings per command; NFR-4's "a run decides once" holds.
- `handlers/dual_pipeline.py:189` calls `self.container_available`, an injected seam its tests
  double; its new `build_tool` argument changes those doubles (NFR-1: signature, not assertion).
