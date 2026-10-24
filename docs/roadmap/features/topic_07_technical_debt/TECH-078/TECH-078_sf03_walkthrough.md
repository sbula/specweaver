# Walkthrough: TECH-078 SF-03 — The API's implement and the planner

Plan: [TECH-078_sf03_implementation_plan.md](TECH-078_sf03_implementation_plan.md).

## CB-1 — the planner names the language (FR-5)

### What changed

- `Planner(..., language=)`: required, the language's display name; the system prompt says "for a
  `<language>` project". No silent Python default.
- `PlanSpecHandler` passes `language_guide(task_files_for(...).language, project).name`; a bad
  `Package` line fails the step naming the spec line.

### Red first

`test_planner_language.py` (unexpected keyword `language`), `test_plan_names_the_language.py` (P-4:
a Rust and a TypeScript project's plan step were told "Python project").

### Tests changed

The 16 older `Planner(...)` calls in tests pass `language="Python"`. Mutants: FR-5
`planner-always-python`, `plan-step-says-python`, both killed. Re-pinned after running (their code
moved in this ticket): D-INTL-03 `planner-can-write`, `guess-a-plan`; B-INTL-01 `absolute-path`;
D-INTL-08 `header-package-ignored`, `python-rules-on-java`; TECH-077 `review-not-read-only`,
`check-rot-opens-worktree`, `drift-check-wrong-folder`; TECH-078 `kotlin-test-loses-Test`.

### The rest of the corpus (done in CB-2, at the user's request)

31 more corpus mutants were `STALE` in files this ticket did not touch: each was run (all killed)
and re-pinned. Two pointed at renamed functions and now name them: C-FLOW-13
`show-broken-file-exits-zero` (`refuse_settings`), C-FLOW-01 `unwritten-never-told`
(`tell_missing_at_end`). Eight function mutants that had never been pinned (D-UI-01 five, C-VAL-05
two, TECH-078 `atom-skips-the-table`, whose symbol is `CodeStructureAtom._handle_read_symbol`) were
run and pinned. The nine left unpinned anchor on constants or a YAML file, which cannot be pinned;
all nine were run and killed.

## CB-2 — one implement pipeline behind both doors (FR-4, FR-1)

### What changed

- `workflows/pipelines/implement_spec.yaml` (bundled): the six steps and gates `sw implement` ran,
  with no file names. `sw implement` and `POST /implement` both load it by name; the Python step
  list (`_build_implement_pipeline`) is gone (decision 1).
- `POST /implement` reports the task's code and test files in the project's language, and `status`:
  `completed`, or `failed` (200) when the tests still fail after the loop, with the test counts, the
  lint errors left and the validation result (decision 2). A bad `[implement]` section answers 500
  naming it; a bad `Package` line 400 `SPEC_INVALID`; a generation error 500 `GENERATION_FAILED`.
- **Bug found and fixed**: a Python test step with no target looked in `src/test_<stem>.py` (every
  door's run has `output_dir = src`), while the tests are written to `tests/`. It now runs the task's
  tests file, given relative so a worktree run reads its own copy. `sw run new_feature` was hit.
- `lint_fix` with no target lints the task's code file, not `src/`.
- **Leak found and fixed**: a failed generation sent the step's traceback (server file paths) to
  the API client; the client now gets the message only, the log keeps the rest.

### Red first

`test_step_defaults.py` (3 red), `test_implement_pipeline.py` (no bundled `implement_spec`),
`test_api_implement_languages.py` (4 red: two steps, `.py` paths, 500 on failing tests, a traceback
in the error).

### Tests changed

- `test_api_llm_endpoints_e2e.py`: the doubled model now answers the test generator with a real
  test, since `POST /implement` runs the tests; the run still makes two model calls.
- `test_one_module_name.py`, `test_task_files_agree.py`: the pipeline names no file, so they assert
  the steps' own defaults agree with the session policy and the task's files.
- `test_acceptance_step.py` reads the bundled pipeline; `test_the_coder_runs_its_own_tests.py`
  expects the relative test target.
- Mutants: FR-4 `api-runs-two-steps`, `api-reports-python-paths`, `failing-tests-are-a-500`,
  `cli-runs-two-steps`, `api-error-leaks-traceback`; FR-1 `python-tests-looked-for-in-src`,
  `lint-default-is-all-of-src`. All killed. Re-pinned after running (their code moved): B-FLOW-01
  `coder-runs-scenario-tests`, B-FLOW-05 `implement-says-tests-failed`, C-FLOW-11
  `sw-implement-reads-another-file`, C-FLOW-13 `implement-drops-run-model`, D-INTL-08
  `sw-implement-names-no-language`, C-EXEC-08 `sw-implement-drops-the-policy`, TECH-077
  `implement-worktree-traceback`, `implement-selector-ignored`.
- Duplication baseline re-frozen: the API's `implement.py` and `review.py` now share six import
  lines.

### Accepted risks

- A project pipeline with `lint_fix` and no target now lints the task's file, not `src/`.
- `implement_spec` is also runnable by `sw run` and `/pipelines/implement_spec/run`, with their
  generic report.
- A client that reads only the HTTP code sees 200 for failing tests; `status` says `failed`.
