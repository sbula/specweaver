# Design: Review, Validation and the API Still Assume Python

- **Feature ID**: TECH-078
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED (by the user, 2026-10-23)
- **Kind**: `bugfix`
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 9 below.

## Feature Overview

TECH-078 makes every step find its files the way generation writes them, so Java, Kotlin, TypeScript
and Rust projects get the same review, validation, test runs and API answers as Python. It solves
steps that glob `*.py`, test rules that look for `test_<stem>.py` only, a `POST /implement` that is a
different and smaller feature than `sw implement`, a planner told it plans "for a Python project",
Kotlin fenced as "text", no way to run one test method outside Python, and a Rust debugger that ignores
its entrypoint. It touches the flow handlers that find files, the code rules C02/C03, the API
`/implement`, the planner, the language-suffix tables and the language runners. It adds no language.
These are gaps in delivered work; `finished-stories-immutable` bars editing the closed stories, so this
ticket owns them.

## Findings this ticket owns

Re-measured 2026-10-23: all hold.

| Finding | What is wrong (today) | Fixed by |
|---|---|---|
| Fix first #5 | `review_code` takes the first `*.py` in `output_dir` (`core/flow/handlers/review.py:323`); C02/C03 want `test_<stem>.py`; `POST /implement` runs 2 steps and reports `src/<stem>.py` (`interfaces/api/v1/implement.py:75`); the C03 hydrator wants `test_<stem>.py` (`validation_hydrator.py:236`) | FR-1, FR-3, FR-4 |
| FL-1 | the generated file is found several ways: `review.py:323`, `validation.py:311` and `lint_fix.py:228` glob `*.py`; `generation.py:135` and `qa_targets.py:88` use `task_files_for`; `review.py:270` reads `target_path`, `validation.py:300` reads `target` | FR-1, FR-2 |
| X-4 | the test file is derived Python-only, from the code file's stem (`c02_tests_exist.py:32`, `c03_tests_pass.py:110`) | FR-3 |
| EP-2 | `sw implement` (6 steps, QA loop, `workflows/implementation/interfaces/cli.py:35`) and `POST /implement` (2 steps, Python paths) share one name | FR-4 |
| WV-18, Real defect 9 | the planner's system prompt says "for a Python project" (`workflows/planning/planner.py:28`) | FR-5 |
| WV-12 | Kotlin is fenced as "text" (`infrastructure/llm/prompt/constants.py:17`, no `.kt`); six suffix tables disagree (`prompt/constants.py`, `sandbox/code_structure/core/atom.py:328`, `core/flow/handlers/archetype_pipelines.py:28`, `workspace/ast/parsers/factory.py:30`, `infrastructure/llm/_skeleton.py:30`, `workspace/ast/refactor/rename.py:49`) | FR-6 |
| TECH-075 planning, 2026-10-22 | one test method cannot run in Java, Kotlin or Rust: only a class or file reaches the build tool, and a folder runs every test (`sandbox/language/core/run_targets.py:17`, `java/runner.py:168`, `kotlin/runner.py:84`, `rust/runner.py:116`) | FR-7 |
| TECH-075 planning, 2026-10-22 | the Rust debugger always runs `cargo run`, ignoring its entrypoint (`rust/runner.py:279`) | FR-8 |

## Path List (`ADR-005`)

| Path | Span | Proof |
|---|---|---|
| P-1 a Java project: `review_code` / `validate_code` / `lint_fix` after generation → the task's `.java` file | `core/flow/handlers` → `core/flow/engine/task_files` | integration (FR-1) |
| P-2 C02 and C03 on a Kotlin, TypeScript or Rust code file → that language's test file found and run | `assurance/validation` → `commons` (convention) → QA runner | integration (FR-3) |
| P-3 `POST /implement` on a TypeScript project → the 6-step pipeline, the task's `.ts` paths | API → `workflows/implementation` → `core/flow` | integration (FR-4) |
| P-4 a Rust project's plan step → the planner told "Rust" | `core/flow/handlers` → `workflows/planning` | integration (FR-5) |
| P-5 a run_tests target of one test, one file, one folder (subfolders included), or none, on Java, Kotlin, Rust, TypeScript, Python → exactly those tests run | QA atom → language runner → build tool | integration with the real tools, `toolchain` tier (FR-7) |
| P-6 the Rust debugger with `src/bin/<x>.rs` → `cargo run --bin <x>` | QA atom → Rust runner | integration (FR-8) |

## Research Findings

### Codebase Patterns

- `task_files_for(project_root, spec_path, language)` (`core/flow/engine/task_files.py:57`) is the one
  convention for a task's code and test files per language (Python `src/<stem>.py`,
  `tests/test_<stem>.py`; Java/Kotlin `src/main|test/<lang>/<pkg>/<Name>[Test].<ext>`; TypeScript
  `src/<stem>.ts`, `tests/<stem>.test.ts`; Rust `src/<m>.rs`, `tests/<m>.rs`). `qa_targets.task_file`
  (`:84`) wraps it and keeps Python's `output_dir`.
- C02/C03 run in `assurance/validation`, which may not import `core/flow` (the engine depends on
  validation). A code file's test convention therefore has to live where both reach it: `commons`.
- `PipelineStep.params` is free-form; no bundled pipeline uses `target_path`; the CLI sets it for
  `sw review --spec` and the drift commands (`workflows/review/interfaces/cli.py:74`,
  `assurance/validation/interfaces/cli_drift.py:67`).
- `_build_implement_pipeline(task)` lives in the CLI module (`workflows/implementation/interfaces/cli.py:35`);
  the API cannot import a CLI module, so it moves into `workflows/implementation`.
- The language guide gives a language's display name (`workflows/implementation/languages.language_guide(language, root).name`).
- Runners: pytest takes `<file>::<name>` natively; Gradle `--tests <Class>.<method>`; Maven
  `-Dtest=<Class>#<method>`; `cargo test --test <file> <name>`; the TypeScript runner's test command
  takes a name filter (`-t`).

### External Tools

None new. Gradle `--tests` and Maven Surefire `-Dtest=Class#method` take a method filter; `cargo test
<filter>` filters by test name; `cargo run --bin <name>` / `--example <name>` choose a target.

### Blueprint References

`qa_targets.task_file` / `default_test_target` are the one place that already does FR-1 right; the fix
generalises it.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Every step that works on the generated code (`review_code`, `validate_code`, `lint_fix`, the C03 hydrator, generation, the QA targets) SHALL find it one way: an explicit `target` resolved inside the project, else the task's file from `task_files_for` (Python keeps the run's `output_dir`); never the first `*.py` | flow handlers | find the code file | the file generation wrote, in every language |
| FR-2 | `target` SHALL be the one parameter name for a step's file; `target_path` is still read as the old spelling `[agreed 2026-10-23]` | pipeline steps | name a file | one name, no pipeline file breaks |
| FR-3 | C02, C03 and the C03 hydrator SHALL find a code file's tests by its language's convention (`tests/**/test_<stem>.py`, `src/test/<lang>/**/<Name>Test.<ext>`, `tests/**/<stem>.test.ts`, `tests/<stem>.rs`), the one convention generation writes by | validation rules | find tests | Kotlin, Java, TypeScript and Rust code is judged on its own tests |
| FR-4 | `POST /implement` SHALL run the same implement pipeline as `sw implement` (code, tests, test run, validation, the bounded loop; one pipeline builder outside both doors) and report the task's files `[agreed 2026-10-23]` | API | implements | one feature behind one name |
| FR-5 | The planner SHALL tell the model the project's language, by its language guide's name | planner | plans | Java, Kotlin, TypeScript and Rust get plans for their language |
| FR-6 | One table in `commons` SHALL map file endings to languages; prompt fences, the code-structure atom, the archetype pipelines, the parser registry, the skeleton reader and rename SHALL read it `[agreed 2026-10-23]` | prompts, AST, flow | name a file's language | Kotlin is fenced as `kotlin`; a new language is added once |
| FR-7 | A test target SHALL run exactly what it names, at every size, in every language: one test (`<file>::<test name>` `[agreed 2026-10-23]`), one file, one folder with all its subfolders, or the whole project (no target) `[agreed 2026-10-23]`. A name means exactly that test, and a run that ran no test fails, naming the target `[agreed 2026-10-23]`. Each runner turns it into its tool's filter: pytest takes the path as is; Gradle `--tests <Class>.<name>` / `<Class>` / `<pkg>.*` (its `*` spans subpackages); Maven `-Dtest=<Class>#<name>` / `<Class>` / `<pkg path>/**`; cargo `--test <file> <name>` / `--test <file>` / a folder of `src/` as its module path filter, `tests/` as `--tests`; the TypeScript runner takes the file or folder and a name filter | QA runner | runs tests | a single test, a file, a folder or all of them run and can be debugged outside Python |
| FR-8 | The Rust debugger SHALL run the entrypoint it is given: `src/bin/<x>.rs` → `cargo run --bin <x>`, `examples/<x>.rs` → `--example <x>`, else the default binary | QA runner | debugs | a chosen Rust binary or example runs |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | the task's files | `task_files_for`, `qa_targets.task_file` | read 2026-10-23 |
| FR-3 | a code file's language and test convention | new `commons` table (FR-6) + convention | designed here; `task_files_for` reads the same convention |
| FR-4 | the implement pipeline | `_build_implement_pipeline` (moves to `workflows/implementation`) | read 2026-10-23 |
| FR-5 | the language's name | `language_guide(language, root).name` | read 2026-10-23 |
| FR-7 | each tool's filter | runners' `_test_command` / `run_tests` | read 2026-10-23 |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Python projects behave as before **[proof: meta — the full suite, which `scripts/commit_gated.py` runs green before every commit]** | existing tests green |
| NFR-2 | `commons` gains no dependency on any SpecWeaver module **[proof: arch — `tach check`]** | `tach check` clean |
| NFR-3 | A `target` outside the project is refused in every step that reads one | one test per step |

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The language table and the code-to-test convention live in `commons` | validation and the engine both need them, and validation may not import the engine | No |
| AD-2 | The implement pipeline builder moves from the CLI module to `workflows/implementation` | the API may not import a CLI module | No |
| AD-3 | A test target's `::<name>` is translated by each runner | the tool syntax stays inside the runner that owns it | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| 4 sub-features, 8 FRs | 3–4 sessions | medium: file lookup changes in five handlers; NFR-1 guards Python |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| Java, Kotlin, TypeScript, Rust projects | review, validation, tests and the API work on their files | high |
| API users | `/implement` is the real implement | high |
| Maintainers | one table and one lookup instead of six and five | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| `POST /implement` now runs tests, so a request takes minutes | high | clients time out | the user's choice 2026-10-23; the user guide says so |
| A Python run that relied on the first `*.py` in `output_dir` now gets the task's file | low | another file reviewed | the task's file is the one generation wrote; NFR-1 |

### Red/Blue (Phase 6), 2 cycles
- R1 (HIGH) `POST /implement` becomes a minutes-long request. Blue: the user's choice; the guide says
  so; the run setup and isolation are already the builder's (TECH-077).
- R2 (MEDIUM) `<file>::<name>` and Windows paths. Blue: a drive letter has one colon; the separator
  is the first `::`.
- R3 (MEDIUM) a code file outside the task layout (`src/a/b.py`). Blue: Python keeps its any-depth
  `tests/**` search; JVM finds `<Name>Test.<ext>` anywhere under `src/test/<lang>/`.
- R4 (LOW) rename's endings list holds `.pyi` and `.js`; the table gives them their language, so the
  archetype match gains `.pyi` for Python. Harmless: a stub file is Python.
- Cycle 2: no new finding.

### Refactoring Opportunities
Covered by FR-1 and FR-6.

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `language_support_guide.md` | add a language: one row in the `commons` table, its test convention | ✅ SF-02 |
| `pipeline_engine_guide.md` | a step's `target` | ✅ SF-02 |

## Works For Real

On a Kotlin project, `sw run` with a pipeline of `generate_code`, `generate_tests`, `validate_code` and
`review_code` reviews and validates the generated `.kt` file and C02 finds its `…Test.kt`; and
`run_tests` runs one test (`<OrdersTest.kt>::placesOrder`), its file, its package folder and the whole
project through Gradle, each running exactly those tests (the `toolchain` tier). Shown in the design's demo once built.

## Sub-Feature Breakdown

### SF-01: One table of languages
- **Scope**: the `commons` table and test convention; the six tables read it.
- **FRs**: [FR-6, FR-3 (the convention)]
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_sf01_implementation_plan.md

### SF-02: One way to find a step's files
- **Scope**: `target`, the task's file, the test file; five handlers, C02, C03, the hydrator.
- **FRs**: [FR-1, FR-2, FR-3]
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_sf02_implementation_plan.md

### SF-03: The API's implement and the planner
- **Scope**: the shared implement pipeline, `POST /implement`, the planner prompt.
- **FRs**: [FR-4, FR-5]
- **Depends on**: SF-02

### SF-04: Test and debug targets
- **Scope**: every target size (one test, file, folder, project) in every runner; the Rust debugger's entrypoint.
- **FRs**: [FR-7, FR-8]
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_sf04_implementation_plan.md

## Execution Order

1. SF-01 and SF-04, in either order
2. SF-02
3. SF-03

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | One table of languages | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | One way to find a step's files | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | The API's implement and the planner | SF-02 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-04 | Test and debug targets | — | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

**Current status**: Design APPROVED 2026-10-23; SF-01 committed 2026-10-23
([walkthrough](TECH-078_sf01_walkthrough.md)); SF-04 committed 2026-10-23
([walkthrough](TECH-078_sf04_walkthrough.md)); SF-02 committed 2026-10-24
([walkthrough](TECH-078_sf02_walkthrough.md)).
**Next step**: Trigger the implementation-plan skill for SF-03.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume
from there using the appropriate skill.
