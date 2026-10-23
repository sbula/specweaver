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
- Gradle (Kotlin) is not installed here; its filters are proven by unit tests until CB-2's toolchain
  tier.
