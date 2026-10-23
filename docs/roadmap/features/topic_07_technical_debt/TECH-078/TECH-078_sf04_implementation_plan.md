# Implementation Plan: Review, Validation and the API Still Assume Python [SF-04: Test and debug targets]
- **Feature ID**: TECH-078
- **Sub-Feature**: SF-04 — Test and debug targets
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-04
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-078/TECH-078_sf04_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-7 (a test target runs exactly what it names — one test, one file, one folder with its
subfolders, the whole project — in Python, Java, Kotlin, TypeScript and Rust) and FR-8 (the Rust
debugger runs the entrypoint it is given). Kind `bugfix`. No dependency. NFR-1 applies (Python keeps
what pytest already does).

## Research Notes

- **Each runner today** (read 2026-10-23), `run_tests(target, kind, scope, ...)`:
  - Python (`sandbox/language/core/python/runner.py:106`): `pytest <target>`; pytest already takes a
    file, a folder (recursive) and `<file>::<name>`. Nothing to change but the zero-tests answer.
  - TypeScript (`typescript/runner.py:85`): `npm test -- <target>` only for a file; a folder ending
    in `/`, `src/` or `tests/` runs **everything**; no name filter.
  - Java (`java/runner.py:168`) and Kotlin (`kotlin/runner.py:79`): `jvm_test_class(target)` turns a
    test file into its class (`run_targets.py:17`); a folder returns None and runs **everything**;
    no method.
  - Rust (`rust/runner.py:116`): `cargo_test_file(target)` turns `tests/<x>.rs` into `--test <x>`; a
    folder, or a file under `src/`, runs **everything**; no name.
- **Tool filters** (documented behaviour, no new dependency): Gradle `--tests <Class>.<method>`,
  `--tests '<pkg>.*'` (its `*` spans subpackages); Maven Surefire `-Dtest=<Class>#<method>`,
  `-Dtest='<pkg path>/**'`; cargo `cargo test --test <x> <name>`, `cargo test --lib <module>::` for a
  file or folder under `src/`, `cargo test --tests` for `tests/`; Jest and Vitest take a path (file or
  folder) and `-t <pattern>`.
- **Debuggers**: `run_debugger(target, entrypoint)`; Python runs `python <entrypoint>`; Rust runs
  `cargo run` whatever the entrypoint (`rust/runner.py:279`).
- **Real tools on this machine**: `mvn`, `cargo`, `java`, `node`, `npm`; no `gradle`, no `kotlinc`.
  The live runner tests (`tests/integration/sandbox/language/test_one_test_file_live.py`,
  `test_polyglot_runners_live.py`) run in the default suite and skip where a tool is missing; tests
  that need a package download (Jest/Vitest) belong in the `toolchain` tier (nightly).
- **One grammar**: `<path>::<name>` — the first `::` splits; a Windows drive letter has one colon.

## Decisions (Phase 4, user answered "all A" 2026-10-23)

1. A test name means exactly that test in every language: cargo runs with `--exact`; Jest/Vitest get
   the name escaped and anchored at its end (`-t "<name>$"`), so `describe` prefixes still match
   `[agreed 2026-10-23]`.
2. A run that ran no test is a failure in every language, naming the target `[agreed 2026-10-23]`.

## Approach (pseudocode, ordered)

1. `run_targets.parse_target(target) -> TestTarget(path, name, kind)` — `kind` is `test`, `file`,
   `folder` or `project` (empty, `.`, or the language's test root).
2. Per runner, `TestTarget` → the tool's filter (Research Notes); a folder includes its subfolders.
3. A run that ran no test fails, naming the target (decision 2).
4. Rust debugger: `src/bin/<x>.rs` → `cargo run --bin <x>`; `examples/<x>.rs` → `--example <x>`;
   anything else → `cargo run`.

## Proposed Changes

| File | Change |
|---|---|
| `src/specweaver/sandbox/language/core/run_targets.py` [MODIFY] | `parse_target`, the JVM and cargo filters for all four sizes |
| `src/specweaver/sandbox/language/core/{python,typescript,java,kotlin,rust}/runner.py` [MODIFY] | use them; Rust debugger entrypoint |

## Test Plan

| FR | Tier | Test file | Cases (bucket) |
|---|---|---|---|
| FR-7 | unit | `tests/unit/sandbox/language/core/test_test_targets.py` [NEW] | for each language and each size — one test, one file, one folder with a subfolder, the project — the exact command (happy, boundary); a Windows path `C:\p\T.java::m` (hostile); a folder outside the test root (boundary); a target with `::` but no name (hostile) |
| FR-7 | integration (real tools, skip if missing) | `tests/integration/sandbox/language/test_test_target_sizes_live.py` [NEW] | pytest, Maven (Java), cargo: a project with two test files in two folders, one passing and one failing test in each file: one test runs one; one file runs its two; one folder runs its subfolder's too; the project runs all (happy, boundary); a target naming no test fails, naming it (degradation, decision 2); a name that is a prefix of another test's runs only its own (hostile, decision 1) |
| FR-7 | integration, `toolchain` tier | `tests/integration/sandbox/language/test_test_target_sizes_toolchain.py` [NEW] | the same four sizes with Gradle (Kotlin) and Vitest (TypeScript), which download their packages |
| FR-8 | unit | `tests/unit/sandbox/language/core/language/rust/test_rust_debugger.py` [NEW] | `src/bin/cli.rs` → `--bin cli`; `examples/demo.rs` → `--example demo`; `src/main.rs` → `cargo run` (happy, boundary); `../x.rs` → `cargo run`, nothing passed (hostile) |
| FR-8 | integration (real cargo) | in the live file | a crate with two binaries: the chosen one's output comes back |

Expected reds: every size but "file" (and Python) fails today — a folder runs everything, a name is
dropped; the Rust debugger always runs the default binary.

Mutants: a folder target loses its filter (FR-7); the name is dropped (FR-7); the zero-tests answer
reverts (FR-7); the debugger ignores `--bin` (FR-8).

## Commit Boundaries

| CB | Tasks | Done when |
|---|---|---|
| CB-1 | `parse_target`; Python, Java, Kotlin, Rust on all four sizes; the live file (pytest, Maven, cargo) | green with the real tools; FR-7 mutants killed |
| CB-2 | TypeScript; the toolchain file (Gradle, Vitest); the Rust debugger. Closes SF-04: stops for the user's acceptance | green; FR-8 mutant killed |

## Documentation

`docs/dev_guides/agent_tools_reference.md` (the run_tests target forms); `language_support_guide.md`
(a runner turns all four sizes into its tool's filter).

## Audit (Phase 2) — answered: all A, 2026-10-23

| # | Question | Options | Proposal | Severity |
|---|---|---|---|---|
| 1 | "One test" in each tool: pytest and JUnit match a test name exactly; cargo's name filter is a **substring** (`place` runs `place_order` and `place_refund`); Jest/Vitest `-t` is a regex on the full name, which includes the `describe` blocks. | A: a name means exactly that test everywhere — cargo with `--exact`, Jest/Vitest with the name anchored at its end (`-t "<name>$"`, so `describe` prefixes still match). B: each tool's own matching (substring / regex). | A — "runs exactly what it names" | MEDIUM |
| 2 | A target that runs **no** test (a folder with no tests, a misspelt name): pytest exits 5, Maven fails, cargo and Jest pass with 0 tests. D-INTL-08 FR-5 already fails a file that names no test class. | A: a run with zero tests is a failure in every language, naming the target. B: zero tests is a pass. | A — a misspelt target must not look green | MEDIUM |

## Architecture Verification (Phase 3)

| Change | Module · archetype | I/O & state | Execution | LLM | Dependencies | Domain | Verdict |
|---|---|---|---|---|---|---|---|
| `run_targets.py` | `sandbox/language/core` · pure helper | none | none | none | none new | test targets | ok |
| runners | `sandbox/language/core/<lang>` · adapter | unchanged | `SubprocessExecutor` as today | none | none new | test runs | ok |

## Consistency Check and Red/Blue (Phase 5)

- **Coverage**: FR-7 (CB-1 Python, Java, Kotlin, Rust; CB-2 TypeScript and the toolchain tier), FR-8
  (CB-2). NFR-1: pytest's own handling of the four sizes stays; only the zero-tests answer changes.
- **Open questions**: none. All decisions are resolved and documented inline in the plan.
- **Handoff risk**: (a) decision 2 also applies where a pipeline runs tests before any exist — the
  implement pipeline writes tests first, so its `run_tests` always has some; any other existing test
  relying on "0 tests passes" is updated, not the rule. (b) Gradle and Kotlin are proven only in the
  `toolchain` tier here (no `gradle`, no `kotlinc` on this machine).
- **Architecture**: `run_targets.py` stays the one place that turns a target into a filter.
- **DDD/KISS/DRY/hexagonal/SoC**: one grammar, one parser, each runner only its tool's spelling.
- **Code detail limit**: no code block; pseudocode only.
- **Red/Blue**, 2 cycles:
  - R1 (MEDIUM) a test name with regex characters (`place (EUR)`) breaks the Jest pattern. Blue: the
    name is escaped before anchoring (decision 1); a unit case covers it.
  - R2 (MEDIUM) a Rust test in a `src/` file has the path `<module>::tests::<name>`, and `--exact`
    needs it whole. Blue: a name in a `src/` file is matched as `<module>::tests::<name>`, the `mod
    tests` convention generation writes; a test module named otherwise is reached by its file or
    folder. Accepted and recorded in the agent tools reference.
  - R3 (LOW) Maven's `#method` needs Surefire 2.7.3 or later (2010). Blue: accepted.
  - Cycle 2: no new finding. Below every threshold.
