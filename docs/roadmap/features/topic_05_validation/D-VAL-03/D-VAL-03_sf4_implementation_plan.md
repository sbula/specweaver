# Implementation Plan: Polyglot Submodule Architecture Refactor [SF-4: Polyglot Submodule Architecture Refactor]
- **Feature ID**: 3.19
- **Sub-Feature**: SF-4 — Polyglot Submodule Architecture Refactor
- **Design Document**: docs/roadmap/features/topic_05_validation/D-VAL-03/D-VAL-03_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-4
- **Implementation Plan**: docs/roadmap/features/topic_05_validation/D-VAL-03/D-VAL-03_sf4_implementation_plan.md
- **Status**: APPROVED

## Research Notes
- **SARIF Complexity Extraction**: All PMD, Detekt, and clippy-sarif tools embed custom attributes under the `properties` or `rank` fields dynamically. We will natively scan for `properties.complexity` and `properties.CyclomaticComplexity` within the JSON result object. **NO REGEX ALLOWED.** If these properties are missing, we explicitly **HARD FAIL** the complexity check rather than silently falling back. This ensures toolchain drift raises immediate visibility.
- **Directory Layout Limitations**: Test files MUST EXACTLY MIRROR the source structure and class names. E.g., `src/.../java/runner.py` gets tested by `tests/unit/.../java/qa_runner.py`. Not `test_java_runner.py`.
- **Atom & Tool Test Parity**: **CRITICAL ARCHITECTURE DISCOVERY**: Agents explicitly only call **Tools**. Engines explicitly call **Atoms**. NO ONE calls **Commons** directly! Therefore, `commons` must strictly only contain MOCKED UNIT TESTS. All live Integration / E2E test files mapping to Cargo/Gradle fixtures MUST be physically relocated to test the actual API bounds.
  - Integration target: `tests/integration/loom/atoms/qa_runner/java/test_atom.py` and `tests/integration/loom/tools/qa_runner/java/test_tool.py`

## Goal Description
Refactor the sprawling "god-class" handler files (`java.py`, `kotlin.py`, `rust.py`, `python.py`, `typescript.py`) into dedicated native submodules (`java/runner.py`, `kotlin/runner.py`, `rust/runner.py`, `python/runner.py`, `typescript/runner.py`) to prevent core-module bloat. Extract and migrate complexity logic directly into `parsers.py` without Regex fallbacks. Scale top-down Atom and Tool level validation tests alongside each language step to ensure full parity with agent endpoints.

## Proposed Changes

### 1. Java Refactoring & Testing Realignment
- Moving `java.py` to `java/runner.py` and extracting `_parse_pmd_complexity` to `parsers.py` without regex.
- `tests/unit/loom/commons/qa_runner/test_java.py` strictly moves to `tests/unit/loom/commons/qa_runner/java/qa_runner.py`.
- Converting Live Integrations: We **DELETE** `test_java_integration.py` from `commons/` completely. We spin up `tests/integration/loom/atoms/qa_runner/java/test_atom.py` and `tests/integration/loom/tools/qa_runner/java/test_tool.py` bounding the OS payload explicitly at the highest level!

### 2. Kotlin Refactoring & Testing Realignment
- Moving `kotlin.py` to `kotlin/runner.py` and moving detekt complexity to `parsers.py`.
- `tests/unit/loom/commons/qa_runner/test_kotlin.py` moves to `tests/unit/loom/commons/qa_runner/kotlin/qa_runner.py`.
- Converting Live Integrations: `test_kotlin_integration.py` moves out of `commons/` entirely into `tests/integration/loom/atoms/qa_runner/kotlin/test_atom.py` and exactly mirrors up to `tools/`.

### 3. Rust Refactoring & Testing Realignment
- Moving `rust.py` to `rust/runner.py`.
- `tests/unit/loom/commons/qa_runner/test_rust.py` moves to `tests/unit/loom/commons/qa_runner/rust/qa_runner.py`.
- Converting Live Integrations: `test_rust_integration.py` moves natively into `tests/integration/loom/atoms/qa_runner/rust/test_atom.py` and identically for `tools/` boundaries.

### 4. Python Refactoring & Testing Realignment
- Refactor `python.py` into `python/__init__.py` and `python/runner.py`.
- Refactor Unit Test bounding inside `tests/unit/loom/commons/qa_runner/python/qa_runner.py`.
- Implement `test_atom.py` and `test_tool.py` integration bindings under `tests/integration/.../python/`.

### 5. TypeScript Refactoring & Testing Realignment
- Refactor `typescript.py` to `typescript/runner.py`.
- Refactor Unit Tests inside `tests/unit/.../typescript/qa_runner.py`.
- Implement `test_atom.py` and `test_tool.py` natively bridging integration checks!

## Open Questions & Review Decisions (Phase 4 HITL Pending)
*See generated artifact for Phase 5 final verification.*

## Verification Plan
1. **Commons Layer (Unit)**: All mocked internal isolation validations operate completely disconnected from external processes.
2. **Atom & Tool Layer (Integration)**: Fully instantiated processes explicitly run `Atom Result` payloads parsing correctly across real Tool endpoints. `QARunnerInterface` methods are NOT called directly in these layers.

## Status Tracking
- `[ ]` Task 1: Refactor Java (`runner.py`, `parsers.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 2: Refactor Kotlin (`runner.py`, `parsers.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 3: Refactor Rust (`runner.py`, `parsers.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 4: Refactor Python (`runner.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 5: Refactor TypeScript (`runner.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` **Execute `@[/pre-commit]` workflow** for SF-4.
