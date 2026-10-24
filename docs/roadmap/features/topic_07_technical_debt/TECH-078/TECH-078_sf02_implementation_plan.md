# Implementation Plan: Review, Validation and the API Still Assume Python [SF-02: One way to find a step's files]
- **Feature ID**: TECH-078
- **Sub-Feature**: SF-02 — One way to find a step's files
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_sf02_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-1 (every step that works on the generated code finds it one way), FR-2 (`target` is the one
parameter name; `target_path` is still read) and FR-3 (C02, C03 and the C03 hydrator find a code
file's tests by its language's convention). NFR-1 (Python as before) and NFR-3 (a `target` outside
the project is refused in every step that reads one) apply. Kind `bugfix`. Depends on SF-01
(committed: `commons/languages.py`).

## Research Notes

Read 2026-10-24.

- **How each step finds its code file today:**
  - `review_code` (`core/flow/handlers/review.py:270`): `params["target_path"]`, used as given (no
    inside-the-project check), else the first `*.py` in `output_dir` (`:323`).
  - `validate_code` (`validation.py:300`): `params["target"]`, resolved inside the project (outside →
    None → "No code file found"), else the first `*.py` in `output_dir` (`:311`).
  - `lint_fix` (`lint_fix.py:71`, `:216`): `params["target"]` (default `"src/"`) is the linter's
    target; the file to fix is the target when it is a file inside the project, else the first
    `*.py` in `output_dir` (`:228`).
  - `drift` (`drift.py:50`): `params["target_path"]`, required, used as given, no inside check.
  - generation (`generation.py:135`) and the QA targets (`qa_targets.py:84`) use `task_files_for`;
    Python code alone keeps `output_dir/<stem>.py` (`generation.py:143`, `qa_targets.generated_code`).
- **Writers of `target_path`**: `sw review --spec` (`workflows/review/interfaces/cli.py:74`), `sw drift
  check` and the rot check (`assurance/validation/interfaces/cli_drift.py:67`, `:184`). No bundled
  pipeline YAML uses it.
- **How the tests of a code file are found today (three ways, all Python only):**
  - C02 (`rules/code/c02_tests_exist.py:32`): `test_<stem>.py` under every `tests/` from the file's
    folder up to the project root.
  - C03 (`c03_tests_pass.py:96`): the hydrator's `qa_test_file`, else `tests/**/test_<stem>.py` under
    the nearest `pyproject.toml`.
  - The hydrator (`validation_hydrator.py:231`): `<project>/tests/**/test_<stem>.py`, for C03 and C04.
- **C02/C03 never judge a non-Python file through `validate_code`** today: with no archetype,
  `_run_validation` returns None for any language but Python (`validation.py:346`), and no bundled
  archetype ships a `validation_code_<archetype>` pipeline. `sw check --level code <file>.kt` does run
  the default pipeline, so C02 there looks for `test_<stem>.py` and fails.
- **The convention**: `commons.languages.root_of_tests(language)` and `name_tests_for(code, language)`
  (SF-01): Python `tests` / `test_<stem>.py`; Java, Kotlin `src/test/<lang>` / `<Name>Test.<ext>`;
  TypeScript `tests` / `<stem>.test.ts`; Rust `tests` / `<m>.rs`. Go, C, C++, JavaScript have none.
- **JavaScript is handled with TypeScript** `[agreed 2026-10-24]`: a project with `package.json` is
  detected as `typescript` (`sandbox/language/core/_detect.py:47`) and runs on the TypeScript runner;
  the skeleton reads `.js` with the TypeScript parser. The convention gains JavaScript: root `tests`,
  test name `<stem>.test.js`.
- **`language_support_guide.md` misses steps** a new language needs: its generator text
  (`workflows/languages/<lang>.md` and `_LANGUAGES` in `workflows/implementation/languages.py`), its
  task files (`core/flow/engine/task_files.py`), `SUPPORTED_LANGUAGES` and `_SCENARIO_EXTENSIONS`
  (`_detect.py`), its rename and move resolver (`workspace/ast/refactor/<lang>.py`) and its standards
  analyzer (`assurance/standards/languages/<lang>/`). CB-2 adds them.
- **Layering**: `assurance/validation` is `pure-logic` and may not import `core/flow`; the engine
  imports validation. `walk_up` (`assurance/validation/project_root.py`) already bounds C02's search
  at the project root. C02's `rglob` is file reading inside a `pure-logic` module, and no row in
  `known_boundary_violations.md` names it.
- **Tests that pin today's lookups**: `test_validate_code_find_path.py`,
  `test_lint_fix_find_code_files.py`, `test_handlers_edge_cases.py`, `test_drift_handler.py`,
  `test_drift.py`, `test_c01_c02_c03.py`, `test_code_rules.py`, `test_c03_context.py`,
  `tests/integration/interfaces/cli/test_cli_drift.py`.

## Decisions (Phase 4, user answered "all A" 2026-10-24)

1. With no archetype, `validate_code` runs C02 and C03 of the default pipeline on every language
   with a test convention (Java, Kotlin, TypeScript, JavaScript, Rust); the other default rules stay
   Python's `[agreed 2026-10-24]`.
2. One test-file finder, `tests_of`, lives in `assurance/validation/project_root.py` beside
   `walk_up`; C02, C03 and the hydrator call it. Its file reading in a `pure-logic` module gets a row
   in `known_boundary_violations.md` `[agreed 2026-10-24]`.
3. One search: from the code file's folder up to the project root, the first
   `<folder>/<root_of_tests>` that holds `name_tests_for(code)`; any depth below it, except Rust,
   whose test is only `tests/<m>.rs` `[agreed 2026-10-24]`.
4. The drift step reads `target` (`target_path` still read), refuses a file outside the project, and
   still needs an explicit target; the CLI writers send `target` `[agreed 2026-10-24]`.
5. C02 and C03 skip a language with no test convention (Go, C, C++) and say so `[agreed 2026-10-24]`.
6. JavaScript is handled with TypeScript: tests under `tests/`, named `<stem>.test.js`
   `[agreed 2026-10-24]`.

Settled by the design: an explicit `target` wins and must be a file inside the project; without
one, the task's code file from `task_files_for`, Python keeping `output_dir/<stem>.py` (FR-1); never
the first `*.py`. An explicit target that is not a file is an error that names it. `lint_fix`'s
`target` stays the linter's target; a folder target falls back to the task's file for the fix.
Generation already finds its files one way (`generation.py:135`); it does not change.

> [!WARNING]
> C03's test run keeps the hydrator's 60-second limit (`validation_hydrator.py:254`). A first Maven or
> cargo build can take longer; C03 then fails as "timed out" and says so. Accepted risk: changing the
> number is not this ticket's decision.
>
> **When it is decided** `[agreed 2026-10-24]`: at the CB-2 stop (the one that closes SF-02). P-2
> measures how long C03's run takes on the Rust crate and the Kotlin-on-Maven project, cold and
> warm, and the CB-2 report gives the user those numbers with two options: keep 60 seconds, or let
> C03 take the step's own `timeout`. The user decides there; nothing in CB-1 or CB-2 changes the
> number before that.

## Approach (pseudocode, ordered)

**CB-1 — one code file lookup (FR-1, FR-2, NFR-3)**
1. `qa_targets.task_code_file(context) -> Path`: `task_file(context, "code")`, else Python's
   `output_dir/<stem>.py` (else `<project>/src/<stem>.py`). `generated_code` uses it (one copy).
2. `qa_targets.step_file(step, context) -> Path | None`, in this order:
   a. `params["target"]`, else `params["target_path"]` (FR-2);
   b. given: resolve against `project_path` (an absolute path stays absolute); outside →
      `ValueError` naming the target (NFR-3); not a file → `ValueError` naming it;
   c. not given: `task_code_file`; None when that file does not exist.
   `task_files_for`'s own `ValueError` (a bad `Package` line) passes through.
3. Callers; each turns a `ValueError` into the step's error result:
   - `review_code`: `step_file`; None → "No code file found for review". `_find_code_path` goes.
   - `validate_code`: `step_file`; `_find_code_path` goes.
   - `lint_fix`: the fix file is `step_file` when `target` names a file, else `task_code_file`; the
     linter still gets `target` (default `src/`). `_find_code_files` goes.
   - `drift`: no `target`/`target_path` → "Missing 'target' in step params."; else `step_file`.
4. The CLI writers (`workflows/review/interfaces/cli.py:74`, `cli_drift.py:67`, `:184`) send `target`.

**CB-2 — one test file lookup (FR-3)** — closes SF-02
5. `commons.languages`: JavaScript joins the convention (`tests`, `<stem>.test.js`).
6. `project_root.tests_of(code_path, stop) -> Path | str`: the test file, or why there is none
   ("no test convention for go", "no test file 'OrdersTest.kt' found"): language from
   `language_of`; walk up with `walk_up`; at each folder `<folder>/<root>`; Rust looks only at
   `<root>/<name>`, the others search any depth (first in sorted order).
7. C02, C03 (`_test_file`) and the hydrator (`_test_file_for`, for C03 and C04) call it. C02 and C03
   skip on "no test convention"; otherwise their messages name the expected file. `_test_file_for`
   stays the hydrator's name for the call.
8. `_run_validation`: with no archetype and a language other than Python that has a test convention,
   keep only the C02 and C03 steps of the default pipeline (decision 1); a language with none still
   returns None (no rule judges it).
9. Expose `project_root.tests_of` in validation's `context.yaml` and `tach.toml` (both, pinned by
   `test_validation_context_exposes.py`).

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/core/flow/handlers/qa_targets.py` | [MODIFY] `task_code_file`, `step_file` |
| `src/specweaver/core/flow/handlers/review.py` | [MODIFY] uses `step_file` |
| `src/specweaver/core/flow/handlers/validation.py` | [MODIFY] uses `step_file`; C02/C03 for other languages |
| `src/specweaver/core/flow/handlers/lint_fix.py` | [MODIFY] uses `step_file` / `task_code_file` |
| `src/specweaver/core/flow/handlers/drift.py` | [MODIFY] reads `target`, uses `step_file` |
| `src/specweaver/core/flow/handlers/validation_hydrator.py` | [MODIFY] `_test_file_for` calls `tests_of` |
| `src/specweaver/workflows/review/interfaces/cli.py` | [MODIFY] sends `target` |
| `src/specweaver/assurance/validation/interfaces/cli_drift.py` | [MODIFY] sends `target` |
| `src/specweaver/commons/languages.py` | [MODIFY] JavaScript convention |
| `src/specweaver/assurance/validation/project_root.py` | [MODIFY] `tests_of` |
| `src/specweaver/assurance/validation/rules/code/c02_tests_exist.py`, `c03_tests_pass.py` | [MODIFY] call `tests_of` |
| `src/specweaver/assurance/validation/context.yaml`, `tach.toml` | [MODIFY] expose `project_root.tests_of` |
| `tests/unit/core/flow/handlers/test_step_file.py` | [NEW] |
| `tests/integration/core/flow/test_step_files_java_live.py` | [NEW] P-1 |
| `tests/unit/assurance/validation/test_tests_of.py` | [NEW] |
| `tests/integration/assurance/validation/test_c02_c03_languages_live.py` | [NEW] P-2 |
| the nine test files under Research Notes | [MODIFY] as the lookups change |

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | `step_file`: target, old spelling, outside, not a file, none → task file per language, Python `output_dir` | FR-1, FR-2, NFR-3 | `step_file` does not exist |
| unit | each handler: outside target refused; no target → the task's `.java`, not a stray `.py` in `output_dir` | FR-1, NFR-3 | the handlers glob `*.py` |
| integration | P-1: a Java project; `generate_code` (doubled LLM) writes the `.java`; `review_code`, `validate_code`, `lint_fix` find that file | FR-1 (seam: handlers → `task_files_for`) | review finds no code file |
| unit | `tests_of` per language, nested Python, a Rust test in a subfolder is not one, no convention, outside the root | FR-3 | `tests_of` does not exist |
| integration | P-2: C02 and C03 through `validate_code` on a Rust crate and a Kotlin-on-Maven project with the real tools; their tests found and run (skipped where the tool is missing) | FR-3 (seam: validation → convention → QA runner) | `validate_code` skips Kotlin and Rust; C02 looks for `test_<stem>.py` |
| unit | C02/C03 skip Go; the TypeScript and JavaScript names; Python nested as before | FR-3, NFR-1 | the rules know only `test_<stem>.py` |

Mutants, written into `TECH-078_mutants.json` as each claim is proven: the target read, the old
spelling, the inside check, the task-file fallback, each language's test name and root in
`tests_of`, the Rust no-depth rule, the C02/C03 call sites.

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–4, their tests, P-1, `pipeline_engine_guide.md` | full suite green; the FR-1/FR-2/NFR-3 mutants killed |
| CB-2 | steps 5–9, their tests, P-2, the other docs | full suite green; the FR-3 mutants killed; stage and stop (closes SF-02), with the C03 timing numbers and the timeout decision |

## Documentation

`pipeline_engine_guide.md`: a step's `target`. `language_support_guide.md`: a new language's test
convention reaches C02/C03, and the missing steps above (one checklist for a new language). `known_boundary_violations.md`: the `tests_of` row. User guide: `sw review --spec` and `sw drift` refuse a file outside the project.

## Architecture Verification (Phase 3)

- `qa_targets` (`core/flow/handlers`) already imports `task_files_for`; no new edge.
- `project_root.tests_of` reads `commons.languages` (allowed: `commons` is importable by all). The
  hydrator (`core/flow`) importing `assurance.validation.project_root` needs it in the validation
  `exposes` list and `tach.toml` interfaces.
- File reading in `pure-logic` validation: decision 2 (ledger row).
- No cycle: `commons` ← validation ← `core/flow`.

## Consistency Check and Red/Blue (Phase 5)

- Every FR of SF-02 has a step and a test: FR-1 (steps 1–3, P-1), FR-2 (steps 2a, 4), FR-3 (steps
  5–8, P-2). NFR-1: the full suite before each commit; NFR-3: one refusal test per step (review,
  validate, lint_fix, drift). AD-1 is SF-01's table, read here. No open question.
- Red/Blue, 2 cycles:
  - R1 (HIGH) C03 on a JVM or Rust project can pass 60 s on a cold build. Blue: accepted risk,
    stated above; C03 says "timed out".
  - R2 (MEDIUM) drift with no target would silently check the task's file. Blue: drift keeps
    needing an explicit target (step 3).
  - R3 (MEDIUM) `sw review --spec` on a file outside the project now fails. Blue: NFR-3 asks for
    it; the error names the file; the user guide says so.
  - R4 (MEDIUM) Python tests that put a differently named `.py` in `output_dir` relied on the glob.
    Blue: they change to the task's file (design risk table, NFR-1).
  - R5 (LOW) a `.tsx` file's test is looked up as `<stem>.test.ts`. Blue: generation writes `.ts`;
    accepted.
  - Cycle 2: no new finding.
