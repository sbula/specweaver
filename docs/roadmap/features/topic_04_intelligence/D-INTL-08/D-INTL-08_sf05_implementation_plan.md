# Implementation Plan: Polyglot Implementation Loop [SF-05: The real toolchains]
- **Feature ID**: D-INTL-08
- **Sub-Feature**: SF-05 — The real toolchains
- **Design Document**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_04_intelligence/D-INTL-08/D-INTL-08_sf05_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-21

**FRs owned**: FR-9 (the real-toolchain half) · **NFRs**: NFR-2, NFR-3 · **Depends on**: SF-02, SF-03,
SF-04 (committed) · US-03 P-5, the real half.

## Shape

| Piece | Where | Tag |
|---|---|---|
| A `toolchain` marker, kept out of the default run like `live` (`addopts -m 'not live and not toolchain'`) | `pyproject.toml` | MODIFY |
| Five sample projects that build and test for real: Python (pytest), Java (Maven, JUnit 5, PMD), Kotlin (Maven with the Kotlin Maven plugin 2.4.10, `kotlin.test`, detekt through antrun — the machine's Gradle 4.4.1 is too old for its Java `[agreed 2026-10-22]`), TypeScript (npm, Vitest, ESLint, `tsc`) — new — and Rust (cargo, no dependencies). Each is a template copied to `tmp_path` per test | `tests/fixtures/toolchain/<language>/` | NEW |
| The journey: `sw implement` on each sample, the model doubled with correct code and tests for that sample, everything else real. Asserts: exit 0; the real runner ran the task's test file and counted at least one passing test; lint ran with the language's linter; for Rust, `cargo test` reached the module through `src/lib.rs`. Skipped where the tool is missing, or (Q1) where its package registry cannot be reached — both are environment facts (`check_conventions` R8) | `tests/e2e/capabilities/workflows/test_implement_with_real_toolchains_e2e.py` | NEW |
| Per sample, a prepare step before `sw implement`, as a user would: `npm install`, `mvn -q test-compile`, `gradle testClasses`. It fetches the packages once, so the run's 120 s test timeout covers tests, not downloads | the journey | NEW |
| The registry check: one TCP connect per registry host (3 s), cached for the session, only for a sample that needs it — Rust and Python never probe | the journey's conftest | NEW |
| The nightly run of the tier and its verdict (Q2) | `scripts/toolchain.py` (beside `scripts/live.py`), `scripts/_mutation_timer.py`, `scripts/session_handover.py` | NEW / MODIFY |

> [!NOTE]
> NFR-2 holds: the tier runs on the host. The container stays Python-validated.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the marker, the five samples, the journey | FR-9 (real), NFR-3 | the journey on the TypeScript sample before it exists; a Rust sample whose `lib.rs` the run must declare |
| CB-2 | the nightly runner and its verdict | NFR-3 | `scripts/toolchain.py --status` before any run says "never ran" and exits 1 |

| CB | Tier | Test |
|---|---|---|
| CB-1 | e2e (`toolchain`) | the journey per language, as above |
| CB-1 | unit | the default run excludes `toolchain` (the marker is registered and `addopts` drops it); every `toolchain` test skips only on a tool or a registry, never on repo state (R8) |
| CB-2 | unit | `scripts/toolchain.py`: the pytest command it builds (`-m toolchain`), the verdict file, `--status` fresh / stale / failed / never; the nightly service runs it with `-` before the mutation run; `session_handover` shows its line |

## Mutants (into `D-INTL-08_mutants.json`, NFR-3)

| Neutralise | Killed by |
|---|---|
| the marker dropped from the pytest call; the verdict written as passed on a failing run; the stale check removed; the service line dropped | CB-2 unit tests |

The Rust sample has only `src/main.rs`, so the real `cargo test` proves the created `src/lib.rs` (SF-03 Q2). The journey itself is a real-toolchain proof: its mutants are SF-02/SF-03's, already in the corpus.

## Research Notes

- `scripts/live.py` is the shape to follow: it runs `pytest -m live tests/e2e`, writes
  `.tmp/live/last.json` (`at`, `passed`, `summary`), and `--status` reads it (48 h freshness).
  `_mutation_timer.timer_units()` runs it as `ExecStart=-…/live.py` before the mutation corpus;
  `session_handover.py:292` prints its status.
- `pyproject.toml:72`: `addopts = "--import-mode=importlib -v --tb=short -m 'not live'"`.
- On this workstation: `mvn`, `gradle`, `npm` (Node 24.18), `cargo`, `java`, `kotlinc` exist.
  `~/.m2` holds the compiler, Surefire and PMD plugins and JUnit 4 only; the Gradle cache is empty;
  no Vitest or ESLint in the npm cache. So JUnit 5, the Kotlin Gradle plugin, detekt, Vitest and
  ESLint must be downloaded on first run (Q1, Q3). Cargo with no dependencies runs offline.
- The runners: `JavaRunner.run_linter` runs PMD through Maven; `KotlinRunner.run_linter` runs
  `gradle detekt` (`kotlin/runner.py:161`); TypeScript `npx eslint --format json`; Rust clippy.
- The existing real-runner tests (`test_polyglot_runners_live.py`, `test_one_test_file_live.py`)
  stay in the default run, skipped where a tool is missing: they are runner seams, not journeys.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Where do the samples' packages come from (JUnit 5, Kotlin plugin, detekt, Vitest, ESLint)? | the build tools download them, as in a real project; a test skips only on a missing tool or an unreachable registry `[agreed 2026-10-21]` |
| Q2 | How does the tier run nightly? | its own `scripts/toolchain.py` and verdict, in the nightly service beside `live.py` `[agreed 2026-10-21]` |
| Q3 | Who sees the network-needing journeys pass first? | the user runs `python scripts/toolchain.py` once after CB-2; failures are fixed before sign-off. In this session only the offline journeys (Python, Rust) run `[agreed 2026-10-21]` |

## Backlog

none
