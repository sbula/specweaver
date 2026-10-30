# Implementation Plan: QA Runners Are Split, Copied, and Can Report a Skipped Tool as Clean [SF-01: A check that did not run is never clean]
- **Feature ID**: TECH-087
- **Sub-Feature**: SF-01 — A check that did not run is never clean
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf01_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-1, FR-2, FR-3 (runners), FR-4 (lint-fix step), FR-5 (C05), FR-19 (language guide). Paths P-1,
P-2, P-6. No command, option or output field changes (NFR-1); only results that were a false
"clean" become FAILED or SKIPPED.

Not in scope: the Python runner's test, debugger and architecture markers (`<sandbox>`,
`<timeout>`, `<validation_engine>`). They already fail closed (count ≥ 1) `[agreed 2026-10-30]`. Dead code and TS
timeout text are SF-03; moves are SF-04.

## Research Notes

Read 2026-10-30 against `40e88d47`. Paths under `src/specweaver/`.

**The shared shape** — `sandbox/language/core/toolchain.py:125-143`:
`failed_lint(reason) -> LintRunResult` and `failed_complexity(reason, max_complexity) ->
ComplexityRunResult`; count 1, file `<toolchain>`, lint code `ToolchainUnavailable`, complexity
function `<toolchain>`. `did_not_run(result, tool)` (`:45`) keys on empty stdout and non-zero exit;
it does **not** look at `timed_out`.

**Every false-clean site** (each one is a test row below):

| # | Runner · method | Today | Line |
|---|---|---|---|
| S1 | Python `run_linter`, no container engine | `LintRunResult(0, …)` | `python/runner.py:217-221` |
| S2 | Python `run_linter`, timed out | zero | `:223-225` |
| S3 | Python `run_linter`, ruff stdout not JSON | `_parse_ruff_json` logs and returns `[]` → zero | `:247-254` |
| S4 | Python `run_complexity`, no engine | zero | `:309-313` |
| S5 | Python `run_complexity`, timed out | zero | `:315-320` |
| S6 | Python `run_complexity`, stdout not JSON | zero (same parser) | `:337` |
| S7 | TS `run_complexity` | stub, zero | `typescript/runner.py:169-175` |
| S8 | Java `run_linter`/`run_complexity`, SARIF malformed | `read_sarif_report` → `{}` → zero | `java/runner.py:224, 246`; `sarif.py:65-76` |
| S9 | Kotlin `run_linter`/`run_complexity`, SARIF malformed | inline `json.loads`, catches only `JSONDecodeError` → zero; an `OSError` escapes | `kotlin/runner.py:196-203, 226-233` |
| S10 | Java, Kotlin, Rust lint/complexity, timed out | no `timed_out` check: Rust parses partial stdout; Java/Kotlin read whatever report is on disk | `java:213`, `kotlin:186, 218`, `rust:164, 198` |
| S11 | Rust `run_complexity`, exception | hand-built violation `complexity=max+1` | `rust/runner.py:227-235` |
| S12 | Java, Kotlin lint/complexity, a report left by an earlier run | `report_never_written` passes on the old file; its verdict reads as today's | `java/runner.py:192-203`, `kotlin/runner.py:168-178` |

Already right: Python's `why_it_did_not_run` branches (count 1, but file `<validation_engine>`);
TS `run_linter` (`eslint_findings` → `None` → `failed_lint`); Rust `run_linter`'s exception branch
(`failed_lint`). Python's complexity branch names the tool "complexipy"; the command is ruff.

**Timeout result** — `sandbox/execution/executor.py:136-147`: `timed_out=True`, partial stdout
kept, `exit_code` the killed process's code. So a timed-out run may carry stdout and pass
`did_not_run`. Java, Kotlin and Rust call `execute(cmd)` without a timeout: the executor default
(120 s) applies; the reason text uses the executor's effective timeout only where the runner knows
it (`self._DEFAULT_TIMEOUT` in Python, `120` in TS); elsewhere "timed out" without a number.

**The atom** — `qa_runner/core/atom.py:343-372, 374-409`: aggregates `error_count`; exports
`errors` as `dataclasses.asdict(LintError)` dicts; FAILED when the count > 0. No change needed:
the runners' count 1 already gives FAILED. `run()` (`:126-156`) does not catch runner exceptions.

**The lint-fix step** — `core/flow/handlers/lint_fix.py:94-190`. Three lint calls feed decisions:
initial (`:97`), after the linter's own fix (`:115`), after each model fix (`:174`). The `fix=True`
call (`:112`) is not read. The atom comes from `_get_atom` (`:208-217`) with
`coder_sandbox(context)` settings. `core.flow.handlers` depends on `specweaver.sandbox`
(`tach.toml:65`), whose interface exposes `language.core` (`tach.toml:229`).

**C05** — `assurance/validation/rules/code/c05_import_direction.py:32-80`; `self._skip(message)`
exists (`models.py:172`). The atom exports `note` (`atom.py:500-519`); the hydrator copies exports
unchanged (`core/flow/handlers/validation_hydrator.py:291-317`). Kotlin's note: "Kotlin
architecture checks are not implemented; no boundary was examined." (`kotlin/runner.py:300`);
Rust's at `rust/runner.py:323`. Neither runs a process.

**The agent tool** — `qa_runner/interfaces/tool.py:178-199`: `run_complexity` maps atom SUCCESS
to `"success"`, else `"error"`. So FR-2's FAILED reaches the agent as an error with no tool change.

**Container absence, for real** — `container_executor.py:111-133 _ensure_engine` looks up
`podman`/`docker` with `shutil.which` and raises `ContainerEngineUnavailableError` when none
answers. A test that sets `execution_mode = "container"` and a `PATH` without either engine walks
the real path, with no double.

**Tests that pin today's false clean**:
`tests/unit/sandbox/language/core/language/python/test_python_runner.py:256-278` (engine
unavailable → 0, twice); `typescript/test_typescript_runner.py:165` (`test_run_complexity_stub`).
Both change in the boundary that fixes them.

**The guide** — `docs/dev_guides/language_support_guide.md:58-59`: "No native complexity checker?
Map `run_complexity` to a static no-op violation array or an open equivalent". FR-19 replaces it.

## Approach (pseudocode, ordered)

**CB-1 — runners never return a false clean (FR-1, FR-2, FR-3)** — kind `bugfix`

1. Red, unit, one test per site S1–S11 (mock executor; real files for SARIF): each asserts count 1,
   the `<toolchain>` marker and a reason naming the tool. S3/S6: ruff stdout `"not json"`.
   S8/S9: a SARIF file with `{` and one with `[]`. S10: `timed_out=True` with partial stdout.
   S12: a clean SARIF report on disk before the run, a run that writes none → not-run.
   The two pinned Python tests and the TS stub test flip to the new contract.
2. Green:
   - Python: S1, S2, S4, S5 return `failed_lint`/`failed_complexity`; the `why_it_did_not_run`
     branches use the same factories (file becomes `<toolchain>`); "complexipy" becomes "ruff".
     `_parse_ruff_json` tells "not JSON" apart from `[]` (returns `None` on a parse error); the
     two builders turn `None` into the not-run result (S3, S6). The `fix=True` pre-pass keeps
     reading leniently: its count is only `fixed_count`.
   - `sarif.read_sarif_report` returns `None` for unreadable or non-object JSON; Java and Kotlin
     return the not-run result on `None` (S8). Kotlin reads through `read_sarif_report` instead of
     its inline `json.loads` (S9; the walker merge itself is SF-04).
   - Java, Kotlin, Rust: check `result.timed_out` right after `execute`, before `did_not_run` and
     before any report is read, and return the not-run result "<tool> timed out" (S10). Python
     and TS keep their number: "ruff timed out after {self._DEFAULT_TIMEOUT} s" (`python/runner.py:93`).
   - Java, Kotlin: remove the report file before each run (`unlink(missing_ok=True)`), so only
     today's run can be read (S12) `[agreed 2026-10-30]`. If removing fails (`OSError`), return
     the not-run result "cannot clear the old report <name>: <error>" without running the tool.
   - TS `run_complexity` returns `failed_complexity("TypeScript complexity checks are not
     implemented", max_complexity)` (S7). Rust's exception branch uses `failed_complexity` (S11).
3. Mutants (corpus `TECH-087`): `py-lint-timeout-clean` (S2 back to zero), `py-ruff-garbage-clean`
   (S3), `sarif-malformed-clean` (`read_sarif_report` returns `{}`), `jvm-timeout-ignored` (Kotlin
   check removed), `ts-complexity-stub-clean` (S7), `jvm-stale-report-read` (Java's unlink
   removed). Each must turn a CB-1 test red.

**CB-2 — the lint step stops on a lint that did not run (FR-4, P-1)** — kind `bugfix`

4. Helper beside the factories (AD-2): `toolchain.did_not_run_reason(errors) -> str | None` takes
   the atom's exported error dicts and returns the joined messages of those with code
   `ToolchainUnavailable`, else `None`. Unit-tested on dicts and on `asdict(failed_lint(…))`, so
   the factory and the check cannot drift.
5. Red, integration `tests/integration/core/flow/handlers/test_lint_step_tool_did_not_run.py`
   (P-1): real `LintFixHandler`, real atom, real Python runner; project config
   `execution_mode = "container"`, `PATH` without podman/docker → real
   `ContainerEngineUnavailableError`. If building `ContainerSubprocessExecutor` fails earlier
   for another reason (image resolution, `container_executor.py:104`), patch
   `container_executor.shutil.which` to return `None` instead of `PATH`: the engine lookup and
   everything after it stay real. Asserts: status FAILED, `error_message` names the engine,
   the model router got zero calls (`tests/scripted_llm.py` double), no auto-fix pass ran
   (the handler made exactly one lint call). Red today: the step enters the model loop.
   Second case, unit (`tests/unit/core/flow/handlers/test_lint_fix_handler.py`): the first lint
   is real errors, the re-lint after auto-fix is not-run → FAILED, zero model calls; and the
   re-lint after a model fix is not-run → FAILED, no second model call (R2 of the design).
6. Green: after each of the three reading lint calls, call the helper; on a reason return
   `_lint_outcome(status=FAILED, remaining=<error_count>, error="The linter did not run: <reason>")`
   at once.
7. Mutant `lint-step-feeds-not-run` (the helper call after the first lint removed): P-1 red.

**CB-3 — C05 skips what was not built; the guide says so (FR-5, FR-19, P-2, P-6)** — kind
`bugfix` — closes SF-01

8. Red, integration `tests/integration/assurance/validation/test_c05_not_built.py` (P-2): real
   `QARunnerAtom` for a Kotlin file and for a Rust file in `tmp_path` → `_hydrate_architecture`
   → `ImportDirectionRule.check` → `Status.SKIP`, message = the runner's note. Red today: PASS.
   Unit beside the C05 tests: a note with `violation_count` 0 → SKIP; no note → PASS unchanged.
9. Green: in C05, after the "no `violation_count`" branch, `exports.get("note")` → `_skip(note)`.
10. P-6, unit `tests/unit/sandbox/qa_runner/...`: `QARunnerTool.run_complexity` over a real atom
    with the TS runner → `status == "error"`, message holds "not implemented". (Green after CB-1;
    its red is the CB-1 mutant `ts-complexity-stub-clean`, which it must also kill.)
11. FR-19, `docs/dev_guides/language_support_guide.md`: replace lines 58-59 with the rule per QA
    method: run the tool; when it did not run, timed out or its report cannot be read, return the
    shared `failed_*` result (the step fails); when the check is not built, say so — `note` on
    `run_architecture_check` (C05 skips), `failed_complexity`/`failed_lint` with "not implemented"
    otherwise; never a bare zero. A unit test reads the guide and asserts the rule's sentence is
    there and "static no-op" is not.
12. Mutant `c05-ignores-note` (the skip branch removed): P-2 red. Design tracker row: SF-01
    Dev/Pre-Commit/Committed; Developer Guides row ✅.

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | runner tests S1–S11 | FR-1, FR-2, FR-3 | each site returns zero today |
| unit | `did_not_run_reason` on dicts and on `asdict(failed_lint)` | AD-2 | helper does not exist |
| integration | `test_lint_step_tool_did_not_run.py` (P-1) | FR-1 + FR-4, seam handler→atom→runner | step calls the model today |
| unit | handler: not-run on re-lint after auto-fix / after model fix | FR-4 (every lint) | loop continues today |
| integration | `test_c05_not_built.py` (P-2), Kotlin and Rust | FR-5, seam C05←hydrator←atom | C05 passes today |
| unit | C05 note → SKIP; no note → PASS | FR-5 | no note branch |
| unit | tool `run_complexity` on TS → error (P-6) | FR-2 at the agent surface | mutant `ts-complexity-stub-clean` |
| unit | guide holds the FR-19 rule | FR-19 | the old sentence is there |
| all | the suite | NFR-1 | — |

Every new test file starts its docstring with `Proves: TECH-087 FR-<n>` (the form
`check_fr_coverage.py` reads, e.g. `tests/unit/test_tach_sees_every_module.py:6`).

Buckets: happy (a real finding still counts as before — each runner keeps its existing finding
tests); boundary (SARIF `[]`, empty-but-valid ruff `[]` stays clean, mixed real + not-run errors
on one lint → not-run wins); degradation (timeout, no engine, malformed report); hostile (a
`ToolchainUnavailable` code inside a real tool's output: ruff never emits it and a project rule
named so in a SARIF report would only stop the step early, failing closed — accepted).

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–3 | suite green; 6 mutants killed |
| CB-2 | steps 4–7 | suite green; P-1 killed `lint-step-feeds-not-run` |
| CB-3 | steps 8–12 | suite green; `c05-ignores-note` killed; stage and stop (closes SF-01) |

## Documentation

Step 11 (FR-19). No user guide changes: no command or option changes.

## Architecture Verification (Phase 3)

- `core.flow.handlers` → `sandbox.language.core.toolchain`: allowed (`tach.toml:65` depends on
  `specweaver.sandbox`; interface exposes `language.core`). SF-04 moves only the factory module of
  `qa_runner`, not `toolchain.py`.
- C05 stays pure: it reads one more key of the context it already gets. No new import.
- No new module, no new edge, no loop.

## Audit (Phase 2)

- **Q1 — Java and Kotlin can read an old report.** A: remove the report before each run; B: leave
  it. The user chose A `[agreed 2026-10-30]` (S12, step 2).
- **Q2 — Python's other hand-built markers.** A: leave them, SF-01 changes lint and complexity
  only; B: move them to the shared factories. The user chose A `[agreed 2026-10-30]` (Scope).

## Consistency (Phase 5)

- Coverage: FR-1 (S1–S3, S10), FR-2 (S4–S7, S10, S11, P-6), FR-3 (S3, S6, S8, S9, S12), FR-4
  (steps 4–7, every reading lint), FR-5 (steps 8–9, P-2), FR-19 (step 11). NFR-1: the suite; NFR-2:
  no new edge; NFR-3: 8 mutants over FR-1..FR-5. AD-1 (shared `failed_*`, `note` for
  architecture), AD-2 (helper beside the factories, step 4). Risk "a pipeline that passed now
  fails": intended, the message names the tool and why.
- Red/Blue, 2 cycles:
  - R1 (MEDIUM) removing the report can fail and leave the old one. Blue: a failed removal is a
    not-run result; the tool does not run.
  - R2 (MEDIUM) P-1 may fail before the engine lookup (image resolution). Blue: fall back to
    patching `shutil.which` in `container_executor`; the lookup stays real (step 5).
  - R3 (MEDIUM) `check_fr_coverage` needs each FR cited by a test file. Blue: `Proves:` line in
    every new file (Test Plan).
  - R4 (MEDIUM) `_parse_ruff_json` returning `None` also feeds the `fix=True` pre-pass. Blue: that
    pass reads only `fixed_count` and keeps treating `None` as zero fixed (step 2).
  - R5 (LOW) "after 120 s" hard-coded. Blue: the reason uses `self._DEFAULT_TIMEOUT`.
  - R6 (LOW) a lint with real and not-run errors (two targets). Blue: not-run wins; the step stops
    (Buckets, boundary).
  - Cycle 2: challenged R1 (removing a report the user made by hand: it is a build output under
    `target/` or `build/` that the same command rewrites; accepted). No new finding.
- Handoff: a fresh agent needs only this plan and the design; every site has a line number, every
  test a file, every mutant a name.
- All decisions are resolved and documented inline in the plan.
