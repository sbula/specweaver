# Implementation Plan: Rust Handler [SF-3: Rust Handler]

- **Feature ID**: 3.19
- **Sub-Feature**: SF-3 — Rust Handler
- **Design Document**: docs/proposals/design/phase_3/feature_3_19_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-3
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_19_sf3_implementation_plan.md
- **Status**: COMPLETED

## Research Notes
- **Cargo Test Formatting**: Running `cargo test -- --format=json | cargo2junit` violates the strict "NO PIPES" and "NO SHELL COMPOUNDING" rule of the sandbox. Therefore, we must run `cargo test -- -Z unstable-options --format=json` (or strictly parse `cargo test --format=json` depending on whether nightly is required) or better yet, run `cargo test --message-format=json` and capture stdout dynamically. Wait, standard `cargo test` text output is easily parsable or we can just parse the final `test result: ok. 10 passed; 0 failed` directly using regex to avoid unstable options.
- **Cargo Clippy**: Returns standard JSON via `cargo clippy --message-format=json`. We can ingest this seamlessly into python's `json.loads` to map `LintError` paths accurately.
- **Complexity**: Rust doesn't have a direct McCabe complexity built into Cargo, but `clippy::cognitive_complexity` rule acts identically to PMD's `too complex`. We can parse it seamlessly from clippy's JSON output!
- **JVM vs Rust Standard Abstractions**: JVM organically produces `junit.xml` and `sarif`. To ensure Rust "*follows the same path*" and protects us against compiler JSON updates, we strictly employ `cargo2junit`. By bridging stable formats, we minimize upgrade maintenance efforts!
- **Component Submodules**: The Rust handler will be placed natively under `src/specweaver/loom/commons/qa_runner/rust.py` for now, pending the execution of SF-4 (which refactors these into `__init__` packages later).

## Goal Description
Implement the `RustRunner` class inheriting from `QARunnerInterface`. This runner will map the 5 polyglot intents (`run_tests`, `run_linter`, `run_complexity`, `run_compiler`, `run_debugger`) using `cargo` paired with `cargo2junit` to perfectly mimic the architecture established by JVM handlers—strictly relying on stable `junit.xml` validation without arbitrary JSON parsing!

## Proposed Changes

### `specweaver.loom.atoms.qa_runner`

#### [MODIFY] `src/specweaver/loom/atoms/qa_runner/atom.py`
- Modify `_resolve_runner` to accept `rust` context natively.
- Import `RustRunner` mapping it efficiently into the architectural structure parallel to JVM runners.

---

### `specweaver.loom.commons.qa_runner.rust`

#### [NEW] `src/specweaver/loom/commons/qa_runner/rust.py`
- Inherits `QARunnerInterface`.
- Implements structural target anchoring (scans for `Cargo.toml` up the directory graph).
- Resolves tests by executing `cargo test -- -Z unstable-options --format=json` natively fed into `cargo2junit` subprocess (avoiding pipes) ensuring a generated `junit.xml` file which natively parses exactly like JVM!
- Evaluates `cargo clippy --message-format=json` passed securely into a `clippy-sarif` subprocess wrapper. This guarantees a stable `sarif` output mapping structurally identical to Detekt and PMD.
- Injects complexity macros dynamically (`-W clippy::cognitive_complexity`) mapped straight into the `cargo clippy` execution layer to enforce `max_complexity` securely natively through the `clippy-sarif` boundary!

### `tests`

#### [NEW] `tests/unit/loom/commons/qa_runner/test_rust.py`
- Implements isolated validation logic ensuring `QARunnerInterface` conformance for `rust.py`.

#### [NEW] `tests/integration/loom/commons/qa_runner/test_rust_integration.py`
- End-to-End dynamic isolated testing bounding to `tests/fixtures/rust_cargo_project` ensuring native API compilation capabilities.

## Verification Plan

### Automated Tests
- Full `pytest` verification using identical `@pytest.mark.live` boundary strategies checking against a real rust fixture.

## Status Tracking
- `[x]` Task 1: Update `atom.py` routing bounds for rust.
- `[x]` Task 2: Implement full mock boundaries logic inside `tests/unit/loom/commons/qa_runner/test_rust.py`.
- `[x]` Task 3: Develop core generic logic for `src/specweaver/loom/commons/qa_runner/rust.py`.
- `[x]` Task 4: Develop `tests/fixtures/rust_cargo_project` and `tests/integration/loom/commons/qa_runner/test_rust_integration.py`.
- `[x]` **Execute `@[/pre-commit]` workflow** for SF-3
