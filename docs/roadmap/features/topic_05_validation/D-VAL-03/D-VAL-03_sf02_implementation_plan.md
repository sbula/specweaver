# D-VAL-03 SF-02 — JVM Handlers (Java & Kotlin)

**Status**: COMPLETED · **FRs owned**: FR-5, FR-6 (recorded 2026-08-17 under `specweaver-dev`
§3.2c, from `INT-US-03-SF01-MIG`) · **Depends on**: SF-01 · Design:
[D-VAL-03_design.md](D-VAL-03_design.md) §Sub-Feature Breakdown → SF-02 · Feature ID 3.19

## Goal

`JavaRunner` and `KotlinRunner`, inheriting `QARunnerInterface`, map the 5 polyglot intents
(run_tests, run_linter, run_complexity, run_compiler, run_debugger) onto Gradle and Maven CLI calls.

## Changes

1. **`specweaver.core.loom.atoms.qa_runner`** — `src/specweaver/loom/atoms/qa_runner/atom.py`
   [MODIFY]: `_resolve_runner` accepts `java` and `kotlin` contexts; `JavaRunner` and `KotlinRunner`
   are added to the `runners` dictionary.
2. **`specweaver.core.loom.commons.qa_runner.jvm`** (shared JVM primitives and parser wrappers)
   - `src/specweaver/loom/commons/qa_runner/java.py` [NEW], inherits `QARunnerInterface`:
     - Anchors on `pom.xml` or `build.gradle` up the directory graph. Both present → `build.gradle`
       wins; the build tool is cached for all sub-commands.
     - Test commands for `mvn` / `gradlew`. **Wipes old XML (rm -rf) before running tests**, then
       `junitparser` reads the report directories — no stale output.
     - PMD SARIF parsed with built-in `json.loads`, no third-party package.
   - `src/specweaver/loom/commons/qa_runner/kotlin.py` [NEW], inherits `QARunnerInterface`:
     - `detekt` lint calls under Maven and Gradle; same anchoring as Java.
     - Same `json.loads` SARIF parsing, SARIF 2.1 schema.
3. **Tests** — subprocess patched via `unittest.mock.patch`, no CLI overrides:
   - `tests/unit/loom/commons/qa_runner/test_java.py` [NEW] — patches `subprocess.run`; mock JVM
     SARIF payloads through the parsers.
   - `tests/unit/loom/commons/qa_runner/test_kotlin.py` [NEW] — `QARunnerInterface` conformance as
     for java.py; `detekt` payload maps to SARIF blocks.

## Tests

`pytest tests/unit/loom/commons/qa_runner/test_java.py tests/unit/loom/commons/qa_runner/test_kotlin.py`
— the parsers extract `LintError` paths from standard payloads with no real CLI. Manual
verification: N/A (fully mocked and deterministic).

Mutants: both conflate the compile intent with a full `build`, and both die.

## Decisions

- **SARIF parsing:** `detekt` emits standard `run -> results -> locations` JSON; walk it by hand with
  the standard `json` module (approved at the HITL gate).
- **JUnit:** `junitparser.JUnitXml.fromfile()` over `pathlib.Path.rglob("*.xml")` on `build/` and
  `target/` respectively, accumulating failures.

## As built

- [x] **Batch 1**: Atom Resolution Engine & Interface Stubs (Completed)
- [x] **Batch 2**: JavaRunner implementation (Maven/Gradle) (Completed)
- [x] **Batch 3**: KotlinRunner implementation (Gradle/detekt) (Completed)
