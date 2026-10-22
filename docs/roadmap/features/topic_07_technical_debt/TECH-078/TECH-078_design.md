# Design: Review, Validation and the API Still Assume Python

- **Feature ID**: TECH-078
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Kind**: `bugfix`
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 7 below.

## Problem Statement

Polyglot gaps `D-INTL-08` did not reach: `review_code` finds `*.py` only, C02/C03 look for Python
test files only, `POST /implement` reports Python paths, and the planner is told it plans "for a
Python project".

These are gaps in delivered work. `finished-stories-immutable` bars editing the closed stories, so
they are owned here.

### Findings

Filing-day evidence from the audit. Line numbers drift; re-measure each one before planning.

- **Fix first #5** — `review_code` finds code as `*.py` only; C02/C03 look for `test_<stem>.py`
  only; `POST /implement` runs 2 steps and reports Python paths; the C03 hydrator looks for Python
  tests. Where: `core/flow/handlers/review.py:321`, `rules/code/c02,c03`,
  `interfaces/api/v1/implement.py:75`.
- **FL-1** — "Find the generated file" six ways; review, validate and lint-fix glob `*.py` and
  ignore `task_files_for`; params `target` and `target_path` mean the same. Where:
  `generation.py:137`, `qa_targets.py:61`, `review.py:321`, `validation.py:293`, `lint_fix.py:208`,
  `validation_hydrator.py:224`.
- **X-4** — Test location derived Python-only, and from `spec_path.stem`. Where:
  `c02_tests_exist.py:32`, `c03_tests_pass.py:94`.
- **EP-2** — `sw implement` (6 steps, QA loop) and `POST /implement` (2 steps, Python paths) are
  different features with one name. Where: `implementation/interfaces/cli.py:35` vs
  `api/v1/implement.py:49,75`.
- **WV-18** — Planner hard-coded for Python. Where: `planner.py:28`.
- **Real defect 9** — The planner role is hard-coded "for a Python project"; Java, TypeScript and
  Rust get Python-flavoured plans. Where: `workflows/planning/planner.py:28`.
- **WV-12** — Kotlin files are fenced as "text" in prompts. Where: 6 suffix tables in this area.

- **Found 2026-10-22 during `TECH-075` planning** `[agreed 2026-10-22]` — a single test method cannot
  be run or debugged in Java, Kotlin or Rust: `run_tests` passes only the test class or file to the
  build tool (Gradle `--tests <Class>`, Maven `-Dtest=<Class>`, `cargo test --test <file>`), never
  `Class.method` / `Class#method` / a test-name filter, which IDEs such as IntelliJ offer. Where:
  `sandbox/language/core/run_targets.py:17` (`jvm_test_class`), `java/runner.py:168`,
  `kotlin/runner.py:84-87`, `rust/runner.py:116-119`.
- **Found 2026-10-22 during `TECH-075` planning** `[agreed 2026-10-22]` — the Rust debugger ignores
  its `entrypoint` and always runs `cargo run` (the default binary), so no `--bin` or test can be
  chosen; Python and TypeScript take a file. Where: `sandbox/language/core/rust/runner.py:279-298`.

## Goal

Every step finds its files through `task_files_for`, so Java, Kotlin, TypeScript and Rust projects
get the same review, validation and API results as Python.

## Open Decisions (for the grilling, not answered here)

- None found at minting. The grilling in `specweaver-design` asks again.

## Non-Goals (proposed, pending design)

- Findings owned by the other tickets minted from the same audit (`TECH-075` to `TECH-091`, and
  `TECH-070` for the project walk).
- New behaviour beyond what the findings name.

## Next Step

Re-measure every finding above, then run `specweaver-design` for `TECH-078`. Write each fix's test
red
first.
