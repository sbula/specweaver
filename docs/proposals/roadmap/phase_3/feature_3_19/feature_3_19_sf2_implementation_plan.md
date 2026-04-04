# Implementation Plan: JVM Handlers [SF-2: Java & Kotlin]
- **Feature ID**: 3.19
- **Sub-Feature**: SF-2 — JVM Handlers (Java & Kotlin)
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3_19/feature_3_19_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_19/feature_3_19_sf2_implementation_plan.md
- **Status**: COMPLETED

## Goal Description
Implement the `JavaRunner` and `KotlinRunner` classes inheriting from `QARunnerInterface`. These runners will map the 5 polyglot intents (run_tests, run_linter, run_complexity, run_compiler, run_debugger) directly into Gradle and Maven CLI executions.

## Proposed Changes

### `specweaver.loom.atoms.qa_runner`
Contains the orchestrator resolving logic to instantiate appropriate language engines.

#### [MODIFY] `src/specweaver/loom/atoms/qa_runner/atom.py`
- Modify `_resolve_runner` to accept `java` and `kotlin` contexts natively.
- Import `JavaRunner` and `KotlinRunner` conditionally or directly mapping them efficiently into the `runners` dictionary graph without error.

---

### `specweaver.loom.commons.qa_runner.jvm`
Contains the shared JVM execution primitives, parser wrappers, and specific Kotlin/Java interfaces.

#### [NEW] `src/specweaver/loom/commons/qa_runner/java.py`
- Inherits `QARunnerInterface`.
- Implements structural target anchoring (scans for `pom.xml` or `build.gradle` up the directory graph). If both exist, prioritizes `build.gradle`, caching the determined build tool wrapper for all sub-commands.
- Formats test commands mapping to `mvn` / `gradlew`. Uses `junitparser` natively on target directories **after executing a forced XML wipe/rm -rf prior to invoking tests** to skip stale output parsing reliably.
- Extends standard `pmd` SARIF parsing using built-in `json.loads` rather than 3rd party package references, resolving NFR requirements directly to Python primitives.
- Restricts subprocess tests entirely via `unittest.mock.patch` without CLI overrides.

#### [NEW] `src/specweaver/loom/commons/qa_runner/kotlin.py`
- Inherits `QARunnerInterface`.
- Implements `detekt` specific CLI calls mapped under Maven and Gradle scopes for linting.
- Mirrors structural anchoring behavior cleanly.
- Implements exactly identical `json.loads` based SARIF outputs matching standard SARIF 2.1 schemas perfectly without bloat.

### `tests`
Contains isolated unittest pipelines strictly enforcing isolation boundaries.

#### [NEW] `tests/unit/loom/commons/qa_runner/test_java.py`
- Implements isolated validation wrappers enforcing test paths natively. Patches `subprocess.run` to guarantee external execution bypass for JVM environments locally. Provides mock generic JVM SARIF payloads to be evaluated via the parsing abstractions perfectly.

#### [NEW] `tests/unit/loom/commons/qa_runner/test_kotlin.py`
- Implements isolated validation logic ensuring `QARunnerInterface` conformance exactly equivalent to java.py while validating its Kotlin `detekt` payload maps appropriately to SARIF blocks cleanly.

## Verification Plan

### Automated Tests
- Run `pytest tests/unit/loom/commons/qa_runner/test_java.py tests/unit/loom/commons/qa_runner/test_kotlin.py` natively to validate parser extraction correctly isolates `LintError` paths from standard payloads cleanly without a valid CLI trigger cleanly.

### Manual Verification
- N/A. Handled via fully abstracted and deterministic testing.

## Status Tracking
- [x] **Batch 1**: Atom Resolution Engine & Interface Stubs (Completed)
- [x] **Batch 2**: JavaRunner implementation (Maven/Gradle) (Completed)
- [x] **Batch 3**: KotlinRunner implementation (Gradle/detekt) (Completed)

## Research Notes
- **SARIF Parsing**: `detekt` outputs strictly standard `run -> results -> locations` json bindings. We enforce manual tree traversal using standard python JSON natively as approved via HITL gate findings.
- **JUnitParser Details**: `junitparser.JUnitXml.fromfile()` will loop via `pathlib.Path.rglob("*.xml")` on `build/` and `target/` respectively to accumulate failure matrices directly.
