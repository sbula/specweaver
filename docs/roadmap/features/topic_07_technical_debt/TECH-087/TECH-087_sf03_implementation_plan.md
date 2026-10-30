# Implementation Plan: QA Runners Are Split, Copied, and Can Report a Skipped Tool as Clean [SF-03: Dead code goes, TypeScript timeouts say what timed out]
- **Feature ID**: TECH-087
- **Sub-Feature**: SF-03 — Dead code goes, TypeScript timeouts say what timed out
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf03_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-10 (the live JUnit reader warns on an unreadable report), FR-11 (the dead code and its tests
go), FR-15 (TypeScript tsc and ESLint-architecture timeouts say "<tool> timed out after N s",
checked before `did_not_run`; the dead `getattr(__builtins__, …)` branches go). At the CB-2 gate the
user widened FR-15 to the debugger timeout of the TypeScript and the Python runner: "<entrypoint>
timed out after 300 s" `[agreed 2026-10-30]`. No command,
option or output field changes beyond those messages.

## Research Notes

Read 2026-10-30 against `e428bd6b`. Paths under `src/specweaver/`.

**FR-10.** `sandbox/language/core/junit_reports.py:64-91 harvest_junit` is the reader Java and
Kotlin use; on an unreadable report it logs at DEBUG (`:84`) and skips it. The promised WARNING
("<file> is unreadable, so its tests are not counted") exists only in the dead copies.
`tests/integration/sandbox/test_lost_results_warn.py:80-100` tests only those copies.

**FR-11, every reference (grep of `src`, `tests`, `tach.toml`, docs, corpora):**

| Dead code | Callers | Its tests | Other references |
|---|---|---|---|
| `java/runner.py:53 _harvest_junit` | none | `test_lost_results_warn.py:80-89` | — |
| `KotlinRunner._parse_junit_results` (`kotlin/runner.py:146`) | none | `test_lost_results_warn.py:92-100` | — |
| `rust/runner.py:50 _tally_junit` | none | none | — |
| `workspace/ast/parsers/rust/parsers.py parse_clippy_complexity` (the file's only function) | none | `tests/unit/workspace/ast/parsers/rust/test_rust_parsers.py` (2 tests, nothing else) | `tests/unit/test_logging_rollout.py:113` imports the module |
| `sandbox/rule_atom.py RuleAtom` | none in `src` | `tests/unit/sandbox/test_rule_atom.py` | `tach.toml:230` expose `rule_atom`; `tach.toml:73` edge `specweaver.sandbox → specweaver.assurance.validation` (its only user); `sandbox/context.yaml:15` consumes `assurance/validation`; named as the single-operation example in `docs/dev_guides/adding_tools_and_atoms.md:57` and `docs/architecture/01_foundational_principles/atoms_vs_tools.md:91` |

No mutant in any corpus rests on these. `tach` runs `exact = true`, so the `sandbox →
assurance.validation` edge must go with its last import, or `tach check` fails. The two `docs/`
examples move to `BashActionAtom` (`sandbox/execution/core/atom.py:87`), which reads its keys off
`context` the same way. Historical documents (`legacy_feature_map.md`, the D-VAL-02 plan) record
what was; they stay.

**FR-15, `typescript/runner.py`:**

| Method | Today | Line |
|---|---|---|
| `run_compiler` | `except getattr(__builtins__, "FileNotFoundError", OSError)` (dead: `SubprocessExecutor` catches `OSError` and returns it as stderr, `execution/executor.py:150`); `did_not_run` before `timed_out`, so a timeout with empty stdout says "tsc did not run"; the timeout result is hand-built, code `TIMEOUT`, message "Timeout during compilation" | `:184-224` |
| `run_debugger` | the same dead `except` | `:283-295` |
| `run_architecture_check` | `did_not_run` before `timed_out`; the timeout result says "Jest timed out" (code `Timeout`) | `:389-399` |

The timeouts the runner passes: tsc 120 s (`:185`), ESLint architecture 60 s (`:385`). After the
change both use the shared results (`failed_compile`, `failed_architecture`), as FR-19's rule says
for a check that did not reach a verdict. `test_typescript_runner.py:54-61`
(`test_run_compiler_missing_binary`) drives the dead branch with a mock that raises
`FileNotFoundError`, which the real executor never does; `:63-70` pins code `TIMEOUT`.

## Approach (pseudocode, ordered)

**CB-1 — the live reader warns; the dead code goes (FR-10, FR-11)** — kind `bugfix` for FR-10,
deletion for FR-11

1. Red, `test_lost_results_warn.py`: the two dead-copy tests become one on `harvest_junit` (an
   unreadable `TEST-x.xml` beside a good report → the good one counted, a WARNING naming
   `TEST-x.xml` and "not counted"). Red today: DEBUG only.
2. Green: `harvest_junit` logs at WARNING with that text.
3. Delete: `_harvest_junit`, `_parse_junit_results`, `_tally_junit` (and imports only they used);
   `workspace/ast/parsers/rust/parsers.py` and `test_rust_parsers.py`; the `rust_p` line in
   `test_logging_rollout.py`; `sandbox/rule_atom.py` and `test_rule_atom.py`; the `rule_atom`
   expose and the `sandbox → assurance.validation` edge in `tach.toml`; the `assurance/validation`
   consumes line in `sandbox/context.yaml`. The two guide examples name `BashActionAtom`.
4. Guard: a unit test asserts none of the five names is importable any more
   (`tests/unit/sandbox/test_dead_qa_code_is_gone.py`), so a revert shows.
5. Mutant `junit-unreadable-silent` (the WARNING back to DEBUG).

**CB-2 — TypeScript timeouts name the tool (FR-15)** — kind `bugfix` — closes SF-03

6. Red, `test_typescript_runner.py`: tsc timed out with empty stdout → `failed_compile`, message
   "tsc timed out after 120 s"; ESLint architecture timed out (empty and partial stdout) →
   `failed_architecture`, "ESLint timed out after 60 s"; a missing tsc as the real executor
   reports it (exit -1, stderr "No such file or directory") → "tsc did not run: …". The dead-branch
   test and the `TIMEOUT` pin are replaced by these.
7. Green: in both methods check `result.timed_out` first, return the shared result with the
   message; remove the two dead `except` clauses (the `try` goes with them).
8. Mutants `ts-arch-timeout-says-jest` (the old message back) and `ts-timeout-after-did-not-run`
   (the timeout check moved after `did_not_run` in `run_compiler`).

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| integration | `test_lost_results_warn.py` live reader warns | FR-10 | DEBUG today |
| unit | `test_dead_qa_code_is_gone.py` | FR-11 | the five names import today |
| unit | TS compile/architecture timeouts, missing tsc | FR-15 | "did not run" / "Jest timed out" today |
| arch | `tach check` (`quality.py cb`) | FR-11, NFR-2 | the edge would be unused after the delete |
| all | the suite | NFR-1 | — |

Every new or changed test file names `Proves: TECH-087 FR-<n>`.

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–5 | suite green; `tach check` green; `junit-unreadable-silent` killed |
| CB-2 | steps 6–8 | suite green; 2 mutants killed; stage and stop (closes SF-03) |

## Documentation

Step 3 (two guide examples). No user guide change.

## Architecture Verification (Phase 3)

- One edge goes (`specweaver.sandbox → specweaver.assurance.validation`); none is added. The
  `sandbox/context.yaml` consumes line goes with it (`test_manifests_match_tach`).
- AD-5 (SF-05 adds `assurance.validation.interfaces → specweaver.sandbox`) stays loop-free; with
  this edge gone it is further from a loop.

## Audit (Phase 2)

No open question; the user approved the plan `[agreed 2026-10-30]`. Each finding is settled by the design or by the code:
- FR-11 says delete `parse_clippy_complexity`; it is its file's only function, so the file goes.
- The `sandbox → assurance.validation` edge exists only for `RuleAtom`; `exact = true` makes its
  removal part of the delete, not a choice.
- FR-15's timeouts use the shared `failed_*` results, as FR-19 (`[agreed 2026-10-30]`) says for
  every QA method; their `code` changes from `TIMEOUT`/`Timeout` to `ToolchainUnavailable`. No
  reader keys on the old codes (grep of `src`).

## Consistency (Phase 5)

- Coverage: FR-10 (steps 1–2, mutant), FR-11 (steps 3–4, guard test, `tach`), FR-15 (steps 6–8,
  two mutants). NFR-1 suite; NFR-2 `tach`; NFR-3 three mutants (FR-11 is a deletion; its guard is
  the import test).
- Red/Blue, 2 cycles:
  - R1 (MEDIUM) deleting `RuleAtom` may break a plugin outside `src`. Blue: no entry point, no
    registry and no doc tells users to use it; the D-VAL-02 plan shows it was never wired.
  - R2 (MEDIUM) the guard test could pass vacuously if it imports the wrong path. Blue: it first
    imports each parent module (which must exist), then asserts the name is absent.
  - R3 (LOW) the WARNING could flood the log on a large broken report set. Blue: one line per
    file, as the dead copies did.
  - R4 (LOW) `test_logging_rollout.py` loses the rust parsers module. Blue: the module is gone;
    the line goes with it.
  - Cycle 2: no new finding.
- All decisions are resolved and documented inline in the plan.
