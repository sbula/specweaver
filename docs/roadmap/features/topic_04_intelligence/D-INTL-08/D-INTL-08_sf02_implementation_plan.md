# Implementation Plan: Polyglot Implementation Loop [SF-02: The runners do what they say]
- **Feature ID**: D-INTL-08
- **Sub-Feature**: SF-02 — The runners do what they say
- **Design Document**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_sf02_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-21

**FRs owned**: FR-5, FR-6 (the runner half) · **Depends on**: SF-01 (committed 3c2cf22c). The
duplicate detector moved into SF-01 (committed 6c1b6e0d).

## Shape

| Piece | Where | Tag |
|---|---|---|
| A test target that is one test file runs only it: Java and Kotlin derive the class from the path (`src/test/java/com/example/GreetServiceTest.java` → `com.example.GreetServiceTest`; a file outside `src/test/<lang>/` → its simple class name) and pass Maven `-Dtest=<class>` or Gradle `--tests <class>` — a filter that matches nothing fails the run, it is never an empty pass; Rust passes `cargo test --test <stem>` for `tests/<stem>.rs`. A folder or the project (`.`, `src/`, `tests/`) still runs everything | `sandbox/language/core/{java,kotlin,rust}/runner.py` (a shared helper for the class name) | MODIFY |
| TypeScript `run_tests`: the project's `npm test`, with `-- <target>` for one file; the counts from Jest's or Vitest's summary line, colour codes stripped first (Q1); any other tool → one result for the whole run, passed or failed by the exit code (Q1); a `package.json` with no `test` script fails, naming it | `sandbox/language/core/typescript/runner.py` | MODIFY (stub → real) |
| TypeScript `run_linter`: `npx eslint <target> --format json` (`--fix` when asked), errors and fixable counts from the JSON; ESLint that did not run is a failed lint, named, never "0 errors" | same | MODIFY (stub → real) |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | one test file per JVM and Rust run | FR-5 (JVM, Rust) | a target test file runs the whole project |
| CB-2 | the real TypeScript test and lint runner | FR-5 (TypeScript), FR-6 | the stub reports 0 tests and 0 lint errors for anything |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit | the commands built (doubled executor): Maven, Gradle, `gradlew`, cargo; a file target filters, a folder target does not; the class from a Java and a Kotlin path, with and without a package |
| CB-1 | integration (real toolchain, skipped where missing — like `test_polyglot_runners_live.py`) | a Maven project with a passing and a failing test class: the passing one's file passes alone; a crate with two test files: one runs alone |
| CB-2 | unit | `npm test -- <file>` built; the counts read from Jest's and Vitest's summary lines, with and without colour codes (Q1); an unknown tool's exit code 0 and 1 (Q1); no `test` script → a named failure; `eslint --format json` read (errors, fixable); ESLint missing or crashing → a named failure |
| CB-2 | integration | the factory gives a `package.json` project the real runner, and a run with a doubled executor reports what the tool printed. The real `npm` run belongs to SF-05's `toolchain` tier: it needs packages from the network |

## Mutants (into `D-INTL-08_mutants.json`)

| CB | Neutralise | Killed by |
|---|---|---|
| CB-1 | the Maven filter dropped; the Gradle filter dropped; the cargo filter dropped; a folder target filtered | CB-1 tests |
| CB-2 | the stub's zeros back; the failed-count parse dropped; a missing `test` script read as a pass; ESLint's error count ignored | CB-2 tests |

## Research Notes

- `JavaRunner.run_tests` (`java/runner.py:128-184`): `gradlew|gradle test` or `mvnw|mvn test`, the
  whole project; JUnit XML harvested from `build/test-results` / `target/surefire-reports`, stale
  reports deleted first. Kotlin's `_test_command` is the same shape (`kotlin/runner.py:73-95`).
- `RustRunner.run_tests` (`rust/runner.py:97-120`): `cargo test`, text output parsed.
- `TypeScriptRunner.run_tests` / `run_linter` (`typescript/runner.py:76-106`) return zeros; only
  `run_compiler` (`tsc --noEmit`) and the ESLint architecture check are real.
- `did_not_run`, `failed_tests`, `build_failed_without_results` are the shared helpers for "the tool
  never ran" vs "it ran and failed".
- The task's test file comes from SF-01's `TaskFiles.tests`, which `sw implement`'s `run_tests`
  step already passes as its target.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How are TypeScript test counts read? | from the summary lines Jest and Vitest print; with any other tool, from the exit code alone `[agreed 2026-10-21]` |

## Backlog

none
