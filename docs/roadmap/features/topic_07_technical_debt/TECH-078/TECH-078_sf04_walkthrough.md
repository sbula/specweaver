# Walkthrough: TECH-078 SF-04 — Test and debug targets

Plan: [TECH-078_sf04_implementation_plan.md](TECH-078_sf04_implementation_plan.md).

## CB-1 — every size in Python, Java, Kotlin and Rust (FR-7)

### What changed

- `run_targets.py`: `parse_target(target) -> RunTarget(path, name, kind)` reads `<path>::<name>`
  (first `::` splits; a drive letter has one colon) into `test`, `file`, `folder` or `project`.
  `jvm_test_args` gives Gradle `--tests Class.method | Class | pkg.*` and Maven
  `-Dtest=Class#method | Class | pkg/**/*`; `cargo_test_args` gives `--test x -- name --exact`,
  `--test *` for `tests/`, `--lib <module>::` for a file or folder under `src/`, `--bins` for
  `main.rs`. `no_test_ran(target, detail)` is the one message for an empty run. `cargo_test_file`
  is gone (replaced).
- Runners: Python drops the `kind` marker for a named test; Java, Kotlin and Rust use the filters; a
  target the tool has no filter for (`TargetError`) fails before any build. A run that ran no test
  fails in all four, naming the target (decision 2); the JVM message keeps what the build said.
- Rust runs with `--no-fail-fast`: without it the project size stopped at the first failing test
  binary and ran half the tests (found by the live test).

### Red first

`test_test_targets.py`: collection error (no `TargetError`). The live file was written with the code;
its proof is the FR-7 mutants (all killed). The Kotlin empty-run mutant was first SILENT: its case used
a Java folder and was refused before the build. The case now uses `src/test/kotlin/`.

### Tests changed

- `test_python_runner.py`: an empty suite (exit 5) and a missing `tests/` (exit 4) now fail as "no
  tests", still not as a missing pytest. Both pipelines write the tests before they run them.
- `test_one_test_file.py` (D-INTL-08): `tests/` is no longer "the whole crate"; cargo carries
  `--no-fail-fast`.
- `test_incremental_semantics_e2e.py`: the project's test had no `unit` marker, so the `tests/` run
  collected nothing and passed. It carries the marker now.
- Re-pointed and re-killed: D-INTL-08 `maven-runs-everything`, `gradle-runs-everything`,
  `cargo-runs-everything`; TECH-031 `cargo-is-asked-for-json-it-cannot-emit`.

### Accepted risks

- A Rust file or folder under `src/` filters by `<module>::`, which libtest matches as a substring:
  `shop::` also runs `x::shop::` tests. A name is exact.
- A Rust test in a `src/` file is reached by name only as `<module>::tests::<name>` (plan R2).
- `src/bin/x.rs` is read as a library module and runs no test; that fails, naming the target.
- A JVM file that is not a test file still runs every test (D-INTL-08 FR-5). A JVM folder outside
  `src/test/<lang>/` and `src/main/<lang>/` is refused.
- Gradle (Kotlin) is not installed here; see CB-2.

## CB-2 — TypeScript, the toolchain tier, the Rust debugger (FR-7, FR-8)

### What changed

- `run_targets.npm_test_args`: `npm test -- <path>`; a folder ends in `/` so `tests/shop` leaves
  `tests/shopping` out; a name becomes `-t "(^| )<name>$"`, escaped, so it matches only that test
  under any `describe` (decision 1). The TypeScript runner fails a run that ran no test: all tests
  skipped by the name, or "No tests found" / "No test files found" (decision 2).
- Jest writes its summary to stderr, Vitest to stdout; the runner now reads both. Before, a Jest
  run's counts were never read and fell back to the exit code (found by the gap analysis).
- `run_targets.cargo_run_args`: the Rust debugger runs `--bin <x>` for `src/bin/<x>.rs` or
  `src/bin/<x>/main.rs`, `--example <x>` for `examples/<x>.rs`, the default binary otherwise; a path
  with `..` names nothing (FR-8).
- `test_test_target_sizes_toolchain.py` (`toolchain` tier): the four sizes with Kotlin on Maven and
  on Gradle, and Vitest. `scripts/toolchain.py` now runs the tier in `tests/integration` as well as
  `tests/e2e`.

### Red first

TypeScript sizes and the debugger cases: 12 red before the code. The stderr summary and the
two-sided anchor: red, then green. The live debugger case (real cargo, two binaries and an example)
and the Kotlin-on-Maven sizes ran green here with the real tools.

### Not run here

- Gradle is not installed: its sizes skip here and on the nightly machine, so Gradle's filters are
  proven by unit tests only.
- Vitest needs `npm install` from the registry; it runs in the nightly toolchain run, not in this
  session.

### Accepted risks

- Jest and Vitest read the path as a pattern: `tests/a.test.ts` also matches a path that ends with
  it (`xtests/a.test.ts`). On Windows Jest sees `\` in paths, and a `/` folder pattern may not match.
