# D-VAL-03 SF-03 — Rust Handler

**Status**: COMPLETED · **FRs owned**: FR-4 (recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-03-SF01-MIG`) · **Depends on**: SF-01 · Design: [D-VAL-03_design.md](D-VAL-03_design.md)
§Sub-Feature Breakdown → SF-03 · Feature ID 3.19

## Goal

`RustRunner`, inheriting `QARunnerInterface`, maps the 5 polyglot intents (`run_tests`,
`run_linter`, `run_complexity`, `run_compiler`, `run_debugger`) onto `cargo`, with `cargo2junit` so
it follows the JVM handlers' path: stable `junit.xml`, no ad-hoc JSON parsing.

## Changes

1. **`specweaver.core.loom.atoms.qa_runner`** — `src/specweaver/loom/atoms/qa_runner/atom.py`
   [MODIFY]: `_resolve_runner` accepts the `rust` context; `RustRunner` registered beside the JVM
   runners.
2. **`specweaver.core.loom.commons.qa_runner.rust`** — `src/specweaver/loom/commons/qa_runner/rust.py`
   [NEW], inherits `QARunnerInterface`:
   - Anchors on `Cargo.toml` up the directory graph.
   - Tests: `cargo test -- -Z unstable-options --format=json`, fed to a separate `cargo2junit`
     subprocess (no pipes) → `junit.xml`, parsed like JVM.
   - Lint: `cargo clippy --message-format=json` into a `clippy-sarif` subprocess → SARIF shaped like
     Detekt and PMD.
   - Complexity: `-W clippy::cognitive_complexity` injected into `cargo clippy` to enforce
     `max_complexity` through `clippy-sarif`.
3. **Tests**
   - `tests/unit/loom/commons/qa_runner/test_rust.py` [NEW] — `QARunnerInterface` conformance for
     `rust.py`.
   - `tests/integration/loom/commons/qa_runner/test_rust_integration.py` [NEW] — end-to-end against
     `tests/fixtures/rust_cargo_project`, real compilation.

## Tests

Full `pytest` run with the same `@pytest.mark.live` strategy against a real Rust fixture.

Mutant: `cargo build` downgraded to `cargo check` — a type check that passes is not a build that
succeeded.

## Decisions

- **No pipes.** `cargo test -- --format=json | cargo2junit` breaks the sandbox's "NO PIPES" and "NO
  SHELL COMPOUNDING" rule, so `cargo2junit` runs as its own subprocess. Alternatives considered:
  `cargo test --format=json` (may need nightly), `cargo test --message-format=json` on stdout, or
  a regex over the final `test result: ok. 10 passed; 0 failed` line to avoid unstable options.
- **Clippy** returns JSON via `cargo clippy --message-format=json`; `json.loads` maps it to
  `LintError` paths.
- **Complexity:** Cargo has no McCabe metric; the `clippy::cognitive_complexity` rule plays the role
  of PMD's `too complex`, read from clippy's output.
- **Same path as JVM:** JVM produces `junit.xml` and `sarif` natively. `cargo2junit` bridges Rust to
  the same stable formats, which protects against compiler JSON changes.
- **Location:** `src/specweaver/loom/commons/qa_runner/rust.py` for now; SF-04 moves it into an
  `__init__` package.

## As built

- `[x]` Task 1: Update `atom.py` routing bounds for rust.
- `[x]` Task 2: Implement full mock boundaries logic inside `tests/unit/loom/commons/qa_runner/test_rust.py`.
- `[x]` Task 3: Develop core generic logic for `src/specweaver/loom/commons/qa_runner/rust.py`.
- `[x]` Task 4: Develop `tests/fixtures/rust_cargo_project` and `tests/integration/loom/commons/qa_runner/test_rust_integration.py`.
- `[x]` **Execute `@[/pre-commit]` workflow** for SF-03
