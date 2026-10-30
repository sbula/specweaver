# Walkthrough: TECH-087 SF-04 — Runners beside their factory, one JVM base

Plan: [TECH-087_sf04_implementation_plan.md](TECH-087_sf04_implementation_plan.md).

## CB-1 — the factory moves; the atom takes a runner (FR-12)

### What changed

- `sandbox/qa_runner/core/factory.py` → `sandbox/language/core/runner_factory.py`. `resolve_runner`
  is unchanged. New `qa_atom(cwd, language, sandbox_settings, scenarios_root)` picks the executor
  (host, container, or container with the scenario store), resolves the runner and returns the atom.
  The container-executor choice moved here from the atom unchanged.
- `QARunnerAtom(cwd, runner, *, scenarios_mounted=False)`: it no longer builds anything.
- `create_qa_runner_interface(role, atom)` takes the atom (it had no `src` caller).
- The lint-fix, validate-tests and code-validation handlers call `qa_atom`. `tach.toml` exposes it.
- `docs/dev_guides/language_support_guide.md` § Selection names the new home and the guard.
- Kind changed from the planned `refactor` to `bugfix`: the new constructor made 14 test files
  change, which the refactor gate refuses; the commit fixes SB-1's two-way imports.

### Red first

- `tests/unit/sandbox/qa_runner/test_qa_runner_imports_no_language.py`: red on the factory's six
  imports; its own cases show a function-level, a `TYPE_CHECKING` and a `from … import language`
  import all count, and a string mention does not.
- `tests/unit/sandbox/language/core/test_runner_factory.py` (moved from `qa_runner/core/qa_runner/`)
  `TestQaAtom`: the named language reaches the runner; a scenario store wins over host settings; the
  scenario scratch goes with the atom, and goes when no runner can be built (red before the fix
  below).
- Tests that built `QARunnerAtom(cwd=…)` or patched `…atom.QARunnerAtom`, `…atom._resolve_runner`
  or `…qa_runner.core.factory.resolve_runner` now use `qa_atom` and its module. The facade tests
  pass their mock atom directly.

### Proof

- Moved and re-pinned: `D-INTL-08` `named-language-ignored`, `container-runs-silently`,
  `atom-drops-the-language`, `lint-ignores-the-language`; `B-FLOW-01` `scenario-mount-on-coder`,
  `c03-c04-on-host`, `lint-on-host`. Corpora `D-INTL-08` 55/55, `B-FLOW-01` 69/69, `TECH-075` 30/30.
- Found by that run, already surviving on `d55f2fa0`: `D-INTL-08` FR-7 `note-not-shown` (since
  `TECH-078` gave every language its test rules, no journey prints the code-validation note). Fixed:
  `test_implementation_cli.py::TestCodeValidationLine` kills it; the campaign scope names it.
- Probes: scratch cleanup removed → `test_the_scenario_scratch_goes_with_the_atom` red; the
  failure cleanup removed → `test_the_scenario_scratch_goes_when_no_runner_is_built` red.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the scratch folder leaked when `resolve_runner` raised: the cleanup was registered
  only once the atom existed. Fixed: `qa_atom` removes it on any failure, test first.
- R2 (LOW) `QARunnerAtom`'s constructor changed; an outside caller would break. Accepted: no
  entry point or guide names it; `qa_atom` is the documented way.
- R3 (LOW) `create_qa_runner_interface` changed its parameters. Accepted: no `src` caller.
- Cycle 2: no new finding (the guard runs on every file, so a new lazy import fails at once).

## CB-2 — one JVM base; Kotlin compile errors located (FR-13)

### What changed

- New `sandbox/language/core/jvm/runner.py` `JvmRunner`: `run_tests`, `run_linter`,
  `run_complexity`, `run_compiler`, with abstract hooks for the build tool, the test, analysis and
  compile commands, and the complexity reader. `JavaRunner` and `KotlinRunner` keep only those
  hooks, their debugger and their architecture check. Kotlin keeps its own default build tool
  (Gradle) and report-dir table; Java keeps Maven and its cached choice.
- `maven_output.py` → `jvm/build_output.py` `[agreed 2026-10-30]`: `compile_errors` also reads the
  Kotlin plugin's `[ERROR] file:///…:L:C` and Gradle's `e: file:///…:L:C` lines; the URI becomes a
  path (`%20` decoded). `MavenDiagnostic` is `BuildDiagnostic`.
- Kotlin's `run_compiler` is Java's: located errors from stdout and stderr (Gradle writes Kotlin's
  to stderr), else one `BuildFailed` naming the exit code and the output tail. Java now reads stderr
  too, which only adds diagnostics.
- Duplication baseline re-frozen: 6 Java↔Kotlin and runner clones gone; the constructor and
  `run_tests` signature clones every runner shares are re-keyed onto `jvm/runner.py` (SF-05's FR-9
  removes the constructor default).

### Red first

- `tests/unit/sandbox/language/core/jvm/test_build_output.py` (moved from `test_maven_output.py`):
  the measured Kotlin lines, a Gradle `e:` line, a `%20` path and Kotlin warnings; red (no module).
- `test_kotlin_runner.py`: located errors from Maven's doubled lines, a Gradle error on stderr, and
  `BuildFailed` with the tail; all three red against the raw-stderr error.
- Toolchain tier: `TestKotlinMavenCompile` compiles a broken file with the real compiler and expects
  `Broken.kt` lines 2 and 3. It downloads packages, so it runs nightly; not run here (no network
  from this session). Its expected form was measured offline on the same `pom.xml`.

### Proof

- New FR-13 campaign: `kotlin-compile-raw-stderr` (only javac's form read) and
  `gradle-stderr-unread` (stderr dropped), both killed.
- Moved and re-pinned: `TECH-031` FR-20 (2, now on `build_output.py`; scope the moved test);
  `TECH-078` FR-7 `java-empty-run-passes` and `kotlin-empty-run-passes` are one line now, so one
  mutant, `jvm-empty-run-passes`. Corpora: `TECH-087` 23/23, `TECH-031` 22/22, `TECH-078` 53/53;
  0 stale.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a hook left unimplemented in a new JVM runner would fail only when called. Fixed: the
  hooks are `@abstractmethod`, so such a class cannot be built.
- R2 (MEDIUM) Kotlin 1.x prints `/path/A.kt: (3, 5)`. Accepted (plan): not measured; it falls to
  `BuildFailed`, which shows the output.
- R3 (LOW) a program line shaped like `e: file:///x.kt:1:1 …` during compile would count. Accepted:
  `run_compiler` runs no program.
- R4 (MEDIUM) found by the gated commit: CB-1's scratch test called `gc.collect()`, which can
  finalize another test's leftovers in the same worker and fail on their warnings. Fixed: `del`
  alone frees the atom (no cycle holds it); the finalizer mutant is still killed.
- Cycle 2: no new finding.

## CB-3 — one copy of each; parsers beside the runners (FR-14)

### What changed

- `jvm/stack_trace_filter.py` `JvmStackTraceFilter` (was Java's); the Kotlin copy is gone; the
  filter factory returns it for Java and Kotlin. Both scenario converters write
  `package scenarios.generated`, which is what it matches (checked).
- `parse_sarif_complexity` (with `_complexity_of`, `_first_location`) moved into
  `language/core/sarif.py` and uses its one `_findings`; `workspace/ast/parsers/_sarif_complexity.py`
  is gone. The PMD and detekt wrappers are gone: each runner passes its rule markers and drift hint.
- `extract_tsc_errors` → `typescript/tsc_output.py`; `workspace/ast/parsers/{java,kotlin,typescript}/
  parsers.py` are gone, with their three `tach.toml` exposes.
- `evaluator.py` → `sandbox/code_structure/core/evaluator.py`, beside its one user.
- `language_support_guide.md`: output parsers live beside the runner; the shared SARIF, JVM base,
  build-output and stack-trace pieces are named.
- Kind changed from the planned `refactor` to `bugfix`, as in CB-1: removing the copies removes their
  names, so 5 test files change.
- Duplication baseline re-frozen: the filter and the SARIF-walker clones are gone; the 7-line import
  block the two JVM runners both need is frozen (imports cannot be shared).

### Red first

- `test_dead_qa_code_is_gone.py` (now also `Proves: TECH-087 FR-14`): 8 removed modules; red while
  they existed.
- `test_stack_trace_filters.py`: Java and Kotlin cases and both factory cases expect
  `JvmStackTraceFilter`; red (no module).
- Moved to mirror `src`: `test_tsc_output.py`, `test_schema_evaluator.py`; the PMD and detekt tests
  became `test_{java,kotlin}_sarif_complexity.py` and call the runner's reader.
- `test_logging_rollout.py` drops the three deleted parser modules.

### Proof

- `TECH-078` FR-6 `atom-skips-the-table` re-pinned (its symbol moved by the import change). Corpora:
  `TECH-087` 23/23, `TECH-031` 22/22, `TECH-078` 53/53; 0 stale in 51.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) one filter for two languages is wrong if Kotlin scenarios used another package.
  Checked: both converters write `scenarios.generated`; the Kotlin cases stay in the test file.
- R2 (LOW) `workspace.ast.parsers` no longer offers the PMD, detekt and tsc helpers. Accepted: no
  other user (grep); `workspace` was not their place.
- R3 (LOW) `sarif.py` grows to 196 lines. Within the file-size gate; one subject (SARIF reading).
- Cycle 2: no new finding.
