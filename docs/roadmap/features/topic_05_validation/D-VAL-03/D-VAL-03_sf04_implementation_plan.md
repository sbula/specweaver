# D-VAL-03 SF-04 — Polyglot Submodule Architecture Refactor

**Status**: APPROVED · **FRs owned**: none — deliberate; SF-04 is the submodule refactor that moved
the runners into `sandbox/language/core/<lang>/` (recorded 2026-08-17 under `specweaver-dev` §3.2c,
from `INT-US-03-SF01-MIG`) · **Depends on**: SF-02, SF-03 · Design:
[D-VAL-03_design.md](D-VAL-03_design.md) §Sub-Feature Breakdown → SF-04 · Feature ID 3.19

## Goal

- Split the "god-class" handlers (`java.py`, `kotlin.py`, `rust.py`, `python.py`, `typescript.py`)
  into submodules (`java/runner.py`, `kotlin/runner.py`, `rust/runner.py`, `python/runner.py`,
  `typescript/runner.py`).
- Move complexity logic into `parsers.py`, with no regex fallback.
- Add Atom- and Tool-level tests per language, for parity with agent endpoints.

## Rules

- **Complexity from SARIF properties.** PMD, Detekt and clippy-sarif put custom attributes under
  `properties` or `rank`. Read `properties.complexity` and `properties.CyclomaticComplexity` from the
  JSON result. **NO REGEX ALLOWED.** Missing properties → **HARD FAIL** the complexity check, never a
  silent fallback, so toolchain drift shows at once.
- **Tests mirror the source** structure and class names: `src/.../java/runner.py` is tested by
  `tests/unit/.../java/qa_runner.py`, not `test_java_runner.py`.
- **Test at the layer that is called.** Agents call only **Tools**; engines call only **Atoms**;
  nobody calls **Commons** directly. So `commons` holds only MOCKED UNIT TESTS, and every live
  Integration / E2E test on Cargo/Gradle fixtures moves up to the Atom and Tool APIs, e.g.
  `tests/integration/loom/atoms/qa_runner/java/test_atom.py` and
  `tests/integration/loom/tools/qa_runner/java/test_tool.py`.

## Changes

1. **Java** — `java.py` → `java/runner.py`; `_parse_pmd_complexity` → `parsers.py`, no regex.
   `tests/unit/loom/commons/qa_runner/test_java.py` → `tests/unit/loom/commons/qa_runner/java/qa_runner.py`.
   **DELETE** `test_java_integration.py` from `commons/`; add
   `tests/integration/loom/atoms/qa_runner/java/test_atom.py` and
   `tests/integration/loom/tools/qa_runner/java/test_tool.py`, which bound the OS payload at the top
   level.
2. **Kotlin** — `kotlin.py` → `kotlin/runner.py`; detekt complexity → `parsers.py`.
   `tests/unit/loom/commons/qa_runner/test_kotlin.py` → `tests/unit/loom/commons/qa_runner/kotlin/qa_runner.py`.
   `test_kotlin_integration.py` leaves `commons/` for
   `tests/integration/loom/atoms/qa_runner/kotlin/test_atom.py`, mirrored under `tools/`.
3. **Rust** — `rust.py` → `rust/runner.py`.
   `tests/unit/loom/commons/qa_runner/test_rust.py` → `tests/unit/loom/commons/qa_runner/rust/qa_runner.py`.
   `test_rust_integration.py` → `tests/integration/loom/atoms/qa_runner/rust/test_atom.py`, and the
   same for `tools/`.
4. **Python** — `python.py` → `python/__init__.py` + `python/runner.py`. Unit tests in
   `tests/unit/loom/commons/qa_runner/python/qa_runner.py`; `test_atom.py` and `test_tool.py`
   under `tests/integration/.../python/`.
5. **TypeScript** — `typescript.py` → `typescript/runner.py`. Unit tests in
   `tests/unit/.../typescript/qa_runner.py`; `test_atom.py` and `test_tool.py` integration checks.

## Tests

1. **Commons layer (unit):** fully mocked, no external processes.
2. **Atom & Tool layer (integration):** real processes; `Atom Result` payloads parse correctly
   across real Tool endpoints. `QARunnerInterface` methods are NOT called directly here.

## Decisions (audit)

Open: the HITL review of this plan is still pending.

## As built

- `[ ]` Task 1: Refactor Java (`runner.py`, `parsers.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 2: Refactor Kotlin (`runner.py`, `parsers.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 3: Refactor Rust (`runner.py`, `parsers.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 4: Refactor Python (`runner.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` Task 5: Refactor TypeScript (`runner.py`). Integrate top-down Atom/Tool tests natively.
- `[ ]` **Execute `@[/pre-commit]` workflow** for SF-04.
