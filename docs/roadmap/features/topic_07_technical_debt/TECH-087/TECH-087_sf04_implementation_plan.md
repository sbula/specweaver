# Implementation Plan: QA Runners Are Split, Copied, and Can Report a Skipped Tool as Clean [SF-04: Runners beside their factory, one JVM base]
- **Feature ID**: TECH-087
- **Sub-Feature**: SF-04 — Runners beside their factory, one JVM base
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf04_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-12 (the runner factory lives in `sandbox/language`; `sandbox/qa_runner` imports nothing from
it at any depth), FR-13 (Java and Kotlin share one JVM base; a failed Kotlin build reports file and
line), FR-14 (one stack-trace filter for the JVM, one SARIF walker; the PMD, detekt and tsc parsers
move to `sandbox/language`; `evaluator.py` beside `code_structure`, `maven_output.py` into the JVM
base package as `build_output.py` `[agreed 2026-10-30]`). Moves are kind `refactor`; FR-13's Kotlin diagnostics are kind `bugfix`. No command,
option or output changes beyond FR-13's Kotlin compile result (NFR-1).

## Research Notes

Read 2026-10-30 against `31f18d3b`. Paths under `src/specweaver/`.

**FR-12 — who builds a runner.**

| Place | Today | Line |
|---|---|---|
| `sandbox/qa_runner/core/factory.py` | `resolve_runner(cwd, executor=None, language=None)`; lazy-imports `detect_language` and the 5 runner classes from `sandbox/language` | `:38-77` |
| `sandbox/qa_runner/core/atom.py` | `QARunnerAtom(cwd, language=None, sandbox_settings=None, scenarios_root=None)` picks the executor (container when `scenarios_root` or `execution_mode == "container"`), then `_resolve_runner` → the factory | `:44-53, 107-124` |
| `sandbox/qa_runner/interfaces/facades.py` | `create_qa_runner_interface(role, cwd, language)` builds `QARunnerAtom(cwd, language)`; no `src` caller | `:156-184` |
| atom builders in `src` | `core/flow/handlers/lint_fix.py:270`, `validation_hydrator.py:128`, `validation.py:492, 497` | — |
| atom builders in `tests` | 22 files call `QARunnerAtom(`; 4 patch `…qa_runner.core.factory.resolve_runner` by string (`test_api_implement_languages.py:90,165`, two e2e) and 2 patch `…atom._resolve_runner` | — |

The only `sandbox/language` imports inside `sandbox/qa_runner` are the factory's six. `tach` sees one
module, `specweaver.sandbox`, so it cannot check FR-12; a guard test must (step 1).

**FR-13 — the two JVM runners** (`language/core/java/runner.py` 380 lines, `kotlin/runner.py` 245):

| Part | Java | Kotlin | Same? |
|---|---|---|---|
| build tool | Gradle file → gradle, else maven (cached) | Gradle file → gradle, `pom.xml` → maven, else **gradle** | no: the default differs; kept (NFR-1) |
| `run_tests` | `jvm_test_args`, clear stale reports, run, `did_not_run`, `harvest_junit`, `build_failed_without_results` | the same steps, report dirs from a table | yes, but for names |
| lint, complexity | `run_sarif_analysis` with PMD; skip `complexity` rules | the same with detekt; skip `complex` | yes, but for the analyzer and its command |
| `run_compiler` | `maven_output.compile_errors(stdout)` → file/line errors; no location → one `BuildFailed` naming the exit code and the output tail | one `CompileError(file="", line=0, message=stderr)` on any non-zero exit | FR-13 makes Kotlin do Java's |
| `run_debugger` | gradle `build` / maven `compile exec:java`; `program_output(stdout)` | gradle `run --debug-jvm` / maven `exec:java`; a banner and `stderr[:200]` | no; kept (NFR-1) |
| `run_architecture_check` | the ArchUnit-style check | `note` (not built) | no; kept |

**Kotlin compile output, measured 2026-10-30** (Maven 3, `kotlin-maven-plugin` 2.0.21, offline, the
`tests/fixtures/toolchain/kotlin/pom.xml` project, two errors in one file). Each line is printed twice,
as javac's are:

```
[ERROR] file:///…/src/main/kotlin/shop/A.kt:2:16 Return type mismatch: expected 'Int', actual 'String'.
[ERROR] file:///…/src/main/kotlin/shop/A.kt:3:11 Unresolved reference 'nope'.
```

Gradle prints `e: file:///…/A.kt:3:11 <message>` (Kotlin 1.8 and later; not measured here, and
Gradle may write it to stderr, so both streams are read;
[GNU Emacs compilation.txt](https://code.fizz.buzz/mirror/emacs/src/branch/master/etc/compilation.txt),
[flutter#178492](https://github.com/flutter/flutter/issues/178492)). javac under Maven prints
`[ERROR] /path/App.java:[3,34] <message>` (`maven_output._DIAGNOSTIC`). Maven writes both Maven forms
to stdout. Kotlin's `file` is a `file://` URI; the reader strips the scheme so `file` is a path, as
for Java.

**FR-14 — the copies and the parsers:**

| Item | Today | Users |
|---|---|---|
| JVM stack-trace filter | `java/stack_trace_filter.py`, `kotlin/stack_trace_filter.py`: same code, names and docstrings differ | `stack_trace_filter_factory.py:31-43`; `test_stack_trace_filters.py` |
| SARIF walker `_findings` | `language/core/sarif.py:39` and `workspace/ast/parsers/_sarif_complexity.py:35`, identical | — |
| `parse_sarif_complexity` (+ `_complexity_of`, `_first_location`) | `workspace/ast/parsers/_sarif_complexity.py` | the two parser files below only |
| `parse_pmd_complexity`, `parse_detekt_complexity` | `workspace/ast/parsers/{java,kotlin}/parsers.py` (23 lines each) | the two runners; `tests/unit/workspace/ast/parsers/{java,kotlin}/test_*_parsers.py`; `tach.toml:198` exposes |
| `extract_tsc_errors` | `workspace/ast/parsers/typescript/parsers.py` | the TS runner; `test_typescript_parsers.py`; `tach.toml:198` |
| `evaluator.py` (`SchemaEvaluator`) | `sandbox/language/core/` | `sandbox/code_structure/core/atom.py:322` (lazy); 2 tests |
| `maven_output.py` | `sandbox/language/core/` | Java runner; `test_maven_output.py` |

After the parser moves nothing in `workspace` uses them (checked by grep). Moving them into
`sandbox` adds no edge: `sandbox` already depends on `workspace.ast.parsers`, and these files need
only `commons.qa`.

**Mutants on moved or merged code** (re-pinned in the commit that moves them, `TECH-081` practice):
`qa_runner/core/factory.py` 2, `java/runner.py` 2, `kotlin/runner.py` 1, `maven_output.py` 2,
`sarif.py` 3, across the `TECH-031`, `TECH-078`, `D-INTL-08` and `TECH-087` corpora.

**Docs that name a moved path:** `docs/dev_guides/language_support_guide.md` (the factory and the
filter factory).

## Audit (Phase 2) and Architecture (Phase 3)

### Decided at the Phase 4 gate

- **Q1 — how the QA atom gets its runner.** The atom takes a ready runner; a builder beside the
  factory in `sandbox/language` picks the executor, resolves the runner and returns the atom. The
  user chose this over keeping one lazy import (which would have weakened FR-12)
  `[agreed 2026-10-30]`.
- **Q2 — where `maven_output.py` goes.** Into the JVM base package as `build_output.py`, reading
  javac's, the Kotlin plugin's and Gradle's lines; not beside the Java runner `[agreed 2026-10-30]`.

### Settled by the design or the code

1. FR-12 proof: a unit test reads every file under `sandbox/qa_runner` with `ast` and fails on any
   import of `specweaver.sandbox.language`, top-level or in a function. Red today: the factory's six.
2. The JVM base keeps each runner's differences as overrides (default build tool, report dirs,
   analyzer and its command, complexity rule markers, debugger, architecture). Only `run_compiler`
   changes (FR-13).
3. A Kotlin build that fails with no located diagnostic gets Java's `BuildFailed` result with the
   output tail (stdout and stderr), as FR-13 says. Kotlin 1.x's `/path/A.kt: (3, 5)` form is not
   parsed (not measured); it falls to `BuildFailed`, which names the output.
4. The duplication baseline freezes the Java↔Kotlin clone (SF-01 walkthrough); it is re-frozen
   down when the clone goes.
5. Kotlin's `run --debug-jvm` waits for a debugger to attach, so a Gradle Kotlin debug run always
   runs to its 300 s limit. Not in FR-13 or FR-14; recorded here, not changed (NFR-1).

## Approach (pseudocode, ordered)

**CB-1 — the factory moves; the atom takes a runner (FR-12)** — kind `refactor`

1. Red, unit `tests/unit/sandbox/qa_runner/test_qa_runner_imports_no_language.py`: no file under
   `sandbox/qa_runner` imports `specweaver.sandbox.language`. Red today (the factory).
2. Move `factory.py` to `sandbox/language/core/runner_factory.py`: `resolve_runner` unchanged, plus
   `qa_atom(cwd, language=None, sandbox_settings=None, scenarios_root=None) -> QARunnerAtom`. The
   executor choice (`_build_container_executor`, the scratch dir and its `weakref.finalize`) moves
   from the atom into `qa_atom` unchanged.
3. `QARunnerAtom.__init__(self, cwd, runner, *, scenarios_mounted=False)`. The 4 handler call sites
   and every test call `qa_atom(...)`; `create_qa_runner_interface(role, atom)` takes the atom. String
   patches of `…qa_runner.core.factory.resolve_runner` / `…atom._resolve_runner` name the place the
   name is now looked up. `tach.toml` `specweaver.sandbox` exposes gain
   `language.core.runner_factory.qa_atom`.
4. Done when: the guard passes, the suite is green, and the 2 factory mutants are moved to the new
   file, re-pinned and killed.

**CB-2 — one JVM base; Kotlin compile errors located (FR-13)** — kind `bugfix`

5. Red, unit `tests/unit/sandbox/language/core/jvm/test_build_output.py` (from `test_maven_output.py`,
   moved): the two measured Kotlin Maven lines and a Gradle `e:` line give file (scheme stripped),
   line, column and message; Maven's doubled lines collapse; javac's form still parses; `program_output`
   unchanged. Red, unit `test_kotlin_runner.py`: a failed build printing those lines gives 2 located
   errors; one printing none gives `BuildFailed` with the tail. Red today: one error, raw stderr.
6. Green: `sandbox/language/core/jvm/runner.py` `JvmRunner(QARunnerInterface)` holds `run_tests`,
   `run_linter`, `run_complexity`, `run_compiler`; `JavaRunner` and `KotlinRunner` (in their folders)
   keep only their overrides. `maven_output.py` becomes `jvm/build_output.py`; `compile_errors`
   reads stdout and stderr.
7. Seam: the toolchain-marked `tests/integration/sandbox/language/test_test_target_sizes_toolchain.py`
   gains a Kotlin compile case with a broken source → located errors (runs with the toolchains).
8. Mutant `kotlin-compile-raw-stderr` (Kotlin's compile back to one raw-stderr error). Move and
   re-pin the Java, Kotlin and `maven_output` mutants.

**CB-3 — one copy of each; parsers beside the runners (FR-14)** — kind `refactor` — closes SF-04

9. `jvm/stack_trace_filter.py` `JvmStackTraceFilter`; the filter factory returns it for Java and
   Kotlin; the two files go. `test_stack_trace_filters.py` keeps both languages' cases.
10. `parse_sarif_complexity` (with `_complexity_of`, `_first_location`) moves into
    `language/core/sarif.py` and uses its `_findings`. The two one-call wrappers
    (`parse_pmd_complexity`, `parse_detekt_complexity`) go: each runner passes its rule markers and
    drift hint. `extract_tsc_errors` moves to `typescript/tsc_output.py` (beside `npm_output.py`).
    The `workspace/ast/parsers/{java,kotlin,typescript}/parsers.py` files and `_sarif_complexity.py`
    go, with their `tach.toml:198` exposes; their tests move to mirror `src`.
11. `evaluator.py` → `sandbox/code_structure/core/evaluator.py`; its importers follow.
12. Guard: `test_dead_qa_code_is_gone.py` gains the removed module paths.
13. Re-pin the `sarif.py` mutants; `stale_mutants.py` 0.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | `test_qa_runner_imports_no_language.py` | FR-12 | the factory imports six today |
| unit | `jvm/test_build_output.py` Kotlin and Gradle lines | FR-13 | only javac's form parses |
| unit | `test_kotlin_runner.py` compile cases | FR-13 | raw stderr, no location |
| toolchain | Kotlin broken-source compile | FR-13 seam (real compiler) | red on the old runner |
| unit | `test_dead_qa_code_is_gone.py` | FR-14 (copies gone) | the old modules import today |
| arch | `tach check` | NFR-2 | exposes follow the moves |
| all | the suite | NFR-1 | — |

Every new or changed test file names `Proves: TECH-087 FR-<n>`.

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–4 | guard green; suite green; factory mutants re-pinned |
| CB-2 | steps 5–8 | suite green; `kotlin-compile-raw-stderr` killed; JVM mutants re-pinned |
| CB-3 | steps 9–13 | suite green; 0 stale; stage and stop (closes SF-04) |

## Documentation

`docs/dev_guides/language_support_guide.md`: the factory's new home, `qa_atom`, the JVM base.

## Architecture Verification (Phase 3)

- No new `tach` module or edge: every move stays inside `specweaver.sandbox`, or goes from
  `workspace.ast.parsers` into it (an edge that exists). `core.flow.handlers` already depends on
  `specweaver.sandbox` (`tach.toml:65`).
- `sandbox/language` → `sandbox/qa_runner` only, held by the step-1 guard.
- `evaluator.py` is pure logic; `code_structure/core` (adapter) may hold it.

## Consistency (Phase 5)

- Coverage: FR-12 (steps 1–4, guard), FR-13 (steps 5–8, mutant, toolchain seam), FR-14 (steps 9–13,
  guard). NFR-1 suite; NFR-2 `tach`; NFR-3 `kotlin-compile-raw-stderr`. AD-3 (factory to
  `sandbox/language`) is step 2. Design risk "moves drift mutants": re-pinned in each CB.
- Next on the roadmap: SF-05 (FR-9) makes every runner take its executor; `qa_atom` is the one
  place that chooses it.
- Red/Blue, 2 cycles:
  - R1 (HIGH) Gradle may print Kotlin's `e:` lines on stderr; reading stdout only would miss them.
    Fixed: `compile_errors` reads both streams (step 6).
  - R2 (MEDIUM) Kotlin's `file` is a `file://` URI, Java's a path. Fixed: the scheme is stripped.
  - R3 (MEDIUM) step 10 left "beside their runners or into the JVM package" open. Fixed: the two
    wrappers go; runners pass their markers.
  - R4 (MEDIUM) `qa_atom` is not reachable through `tach` without an expose. Fixed: step 3.
  - R5 (MEDIUM) string patches of the old factory path would patch nothing and the tests would
    silently use the real runner. Blue: step 3 renames them; a stale target raises
    `AttributeError`/`ModuleNotFoundError` under `patch`, so a miss fails loudly.
  - R6 (LOW) Kotlin 1.x output form not parsed. Accepted: it falls to `BuildFailed` with the output.
  - Cycle 2: challenged R5 (does `patch` fail on a missing module? yes, it imports the target).
    No new finding.
- All decisions are resolved and documented inline in the plan; the user approved it `[agreed 2026-10-30]`.
