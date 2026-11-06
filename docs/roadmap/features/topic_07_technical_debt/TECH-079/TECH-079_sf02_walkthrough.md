# Walkthrough: TECH-079 SF-02 — Every caller asks it

## CB-1: the run carries the profile; the refusal reaches the doors (FR-7 run part, FR-8)

**What changed**
- `IsolationPolicy.language` (the pin only) is gone. The run carries `profile: ProjectProfile | None`
  and `undecided: str | None`; the run builder sets one of them with both `[implement]` pins.
- `core/flow/engine/run_language.py` → `run_profile.py`: `run_profile(context)` returns the profile,
  raises `ProjectUndecidedError` with the stored message, or, for a context nobody decided for (one
  a test built), decides from the root with no pins and keeps it. `run_task_files` uses it. The new
  edge `core.flow.engine → workspace.project` is in tach and `context.yaml` (AD-2).
- `derive_allowed_paths(spec, root, language)`: all required; the `python` branch is gone.
- Doors: `RunRequest.needs_profile`; `sw run` and resume, `POST /pipelines/{name}/run` and resume
  pass it (Q2 `[agreed 2026-11-06]`). `build_run_or_exit` prints a refusal and exits 1;
  `build_api_run` answers 400 `PROJECT_UNDECIDED`, from any door.
- Q1 `[agreed 2026-11-06]`: `apply_session_policy` raises the refusal past its best-effort guard
  when session isolation is on (set, or by DAL) and no allow-list is configured.
- Not in the plan, taken at dev: `sw implement` builds the run first and takes its task files from
  `run_task_files`, so it decides once and needs no `workspace.project` import; the plan's door-side
  `read_project_profile` was not needed. `cli_kit._core.project_sections_at` lost its last caller
  and was deleted with its two tests. `POST /implement` decides at the door (plan F3).
- Found by red/blue: a registered folder removed since registration crashed the builder with an OS
  traceback; the builder now keeps a refusal naming the folder.

**What a user sees.** A fresh `sw init` project has no build file, so `sw run` and `sw implement`
refuse with "the project root has no build file and no code file; set [implement] language in
specweaver.toml" until it has one or the setting. This follows FR-3/FR-5 as agreed; §6c says it.

**Tests**
- Red first: `tests/unit/core/flow/engine/test_run_profile.py` (replaces `test_run_language.py`),
  `tests/integration/interfaces/run_setup/test_run_carries_the_profile.py`,
  `tests/integration/interfaces/cli/test_cli_refuses_an_undecided_project.py`,
  `tests/integration/interfaces/api/test_api_refuses_an_undecided_project.py` (red: no module, or
  the run started).
- NFR-1: 118 test files built project folders with no build file and leaned on the Python default;
  each now writes the build file its test means (mostly `pyproject.toml`, `tsconfig.json` beside
  `package.json`) or a pinned profile. No assertion was loosened; the removed `assert` lines are the
  ones rewritten for the profile. Seven QA-atom expectations of `language=None` now expect the run's
  `"python"`. The scenario e2e pins `[implement] language` instead of a pyproject, because a
  pyproject makes the sandbox build the toy project.
- Mutants, each OBJECTED: `run-profile-ignores-undecided`, `needs-profile-ignored`,
  `session-policy-swallows-undecided`, `isolation-python-default`, `cli-door-shows-a-traceback`,
  `api-resume-runs-undecided`, `api-door-answers-500`.
- NFR-5: 58 mutants in 19 corpora pointed at changed functions; 20 anchors were rewritten to the new
  code with the same claim (`TECH-081` FR-14 now probes a private import in `run_profile`), all
  re-pinned; `stale_mutants.py` reports none.

**Gap analysis (Phase 2)**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `run_profile`, `run_task_files` | ✅ | ✅ | — |
| `derive_allowed_paths`, `apply_session_policy` (Q1) | ✅ | ✅ | — |
| strip-merge allow-list language | — | ✅ (one test; probe objected) | — |
| `builder._profile` (pins, undecided, needs, unreadable root) | — | ✅ | — |
| `build_run_or_exit` refusal, any door | — | ✅ (added) | — |
| `build_api_run` refusal, any door | — | ✅ (added) | — |
| API resume refusal | — | ✅ (added) | — |
| `implement._task_files` refusal | — | ✅ | — |

Composition: builder → `run_profile` → task files and allow-list in one test
(`test_a_pinned_mixed_root_carries_the_pin_everywhere`). Agreement: the task files and the QA runner
name one language (`test_run_profile_agrees_with_qa.py`). The journey e2e for P-1/P-3 lands with
CB-2, when every part takes the run's language.

**Red/blue**
- Fixed: the unreadable-root traceback above.
- Accepted: `sw implement` and `POST /implement` read the root at the door and again in the builder
  (two listings); NFR-4's "a run decides once" holds.
- Accepted: `run_profile`'s fallback stores its answer with `model_copy`; inside a step copy it does
  not reach the original. Only test-built contexts take it.
- Accepted: a context nobody decided for whose folder does not exist raises the OS error; the
  builder, the only `RunContext` in `src`, never leaves one undecided.

## CB-2: the factories take the language (FR-14, FR-7 language part)

**What changed**
- `resolve_runner(cwd, executor, language)`, `create_scenario_converter(language)`,
  `create_stack_trace_filter(language)`: the language is required; each chooses from one table
  (`_RUNNERS`, `_CONVERTERS`, `_FILTERS`) through one lookup, `language_table.language_class`, which
  raises `ValueError` naming a language with no row. `_runner_class` and both ladders are gone.
- `render_contract`, `contract_extension` and `task_files_for` refuse an unknown language the same
  way; none falls back to Python.
- `LanguageAtom(cwd, language)`; its `detect_language` intent is gone (no caller, plan F10).
- `sandbox/language/core/detect.py` is deleted (NFR-3): `detect_language`,
  `detect_scenario_extension`, `SUPPORTED_LANGUAGES` and `_SCENARIO_EXTENSIONS` with it.
- Handlers pass `run_profile(context)`: the scenario file (`qa_targets`), the scenario converter
  (`scenario.py`), the stack trace filter (new `arbiter.trace_filter`), code validation (`profile`).
- `sw check` and `POST /api/v1/check` (no run): the QA language is the file's ending (plan F4).
- Found at dev, not in the plan: a Go file lost C05. The boundary check is the one QA part every
  language shares, and it rode on the QA atom, which now has no runner for Go. `QARunnerAtom` takes
  `runner=None` and then refuses every intent but `run_architecture`; `architecture_atom(cwd)` builds
  that atom on the host. A language SpecWeaver does not generate keeps C05 and runs no tests.

**Tests**
- Red first: the factory tests (one table, unknown refused), `test_every_part_takes_the_run_language.py`
  (a mixed root pinned to Python gets Python's runners, scenario file and filter; pinned to
  TypeScript, TypeScript's; undecided, every part refuses), the hydrator's language tests,
  `test_the_detector_is_gone.py` (NFR-3).
- Old tests that pinned detection now name the language; contexts the handlers read carry a profile.
- Mutants, each OBJECTED: `unknown-language-is-python`, `contract-unknown-is-python`,
  `contract-extension-unknown-is-py`, `task-files-unknown-is-python`, `check-ignores-the-file-ending`,
  `go-loses-the-boundary-check`, `scenario-file-is-python`, `trace-filter-is-python`.
- NFR-5: 16 mutants pointed at changed functions; 7 re-anchored (`D-INTL-08`'s two Kotlin mutants now
  live in `commons.project_profile`, scope + `test_project_profile.py`), all re-pinned. The 20
  re-anchored in CB-1 were re-run against their scopes: 19 objected; `TECH-081` FR-14 was SILENT
  (a private import from `commons`, a utility module, is allowed) and now imports a private name
  from `workspace.project`, which objects.

**Gap analysis (Phase 2)**

| Function | Unit | Integration | E2E |
|---|---|---|---|
| `language_class` and the three factory tables | ✅ | ✅ | — |
| contract renderer, extension, task files | ✅ | — | — |
| `QARunnerAtom(runner=None)`, `architecture_atom` | ✅ | — | ✅ (Go boundary e2e) |
| hydrator: run profile, file ending, Go | ✅ | ✅ (boundary extras) | ✅ |
| handlers: scenario file, converter, filter | ✅ | ✅ (seam) | — |

Composition: the seam test drives profile → handlers → factories. Agreement: lint, unit, scenario
runners, the scenario file and the filter name one language in one test.

**Red/blue**
- Accepted: `task_files_for` raises `ValueError` for an unknown language, which `POST /implement`
  would map to `SPEC_INVALID`; the language there comes from the profile, which only yields the five.
- Accepted: `architecture_atom` runs on the host only; it is reached only without a run (`sw check`),
  which never asks for a container.
