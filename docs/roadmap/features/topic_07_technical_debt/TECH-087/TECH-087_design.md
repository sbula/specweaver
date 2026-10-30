# Design: QA Runners Are Split, Copied, and Can Report a Skipped Tool as Clean

- **Feature ID**: TECH-087
- **Phase**: Topic 07 (Technical Debt)
- **Status**: APPROVED
- **Kind**: `bugfix` (SF-01, SF-02, SF-03, SF-05); `refactor` for SF-04's moves, `bugfix` for its
  Kotlin diagnostics (FR-13). The plan names the kind per commit boundary (`scripts/tests.py`).
- **Design Doc**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_design.md
- **Origin**: 2026-10-22, read-only architecture audit of `src/specweaver`. The user grouped its
  findings into tickets by root cause `[agreed 2026-10-22]`; this ticket owns the 14 below.

## Feature Overview

TECH-087 makes a QA tool that did not run never read as clean, and keeps the code a step wrote
when git cannot save it. It solves a lint step that passes when ruff timed out or no container
engine was there, a C05 rule that says "all imports follow layering rules" for languages with no
architecture check, and a worktree that is deleted unmerged when `git add` fails. On the way it
puts the runners beside their factory, gives Java and Kotlin one base, removes dead parsers and
copies, and makes every command go through a runner the caller chose. It touches
`sandbox/language`, `sandbox/qa_runner`, `sandbox/git`, `core/flow` (lint-fix handler, sandboxed
execution, session), `assurance/validation` (C05, `sw check --drift`) and `assurance/standards`
(discovery). It does NOT move MCP servers into a container. No new command or option.

## Findings this ticket owns

Re-measured 2026-10-29 against `9a5abc70`. Paths under `src/specweaver/`.

| Finding | Today | FR |
|---|---|---|
| SB-1 | `sandbox/qa_runner/core/factory.py:49-77` lazy-imports the 5 runners in `sandbox/language/core/*/runner.py`, which import `qa_runner.core.interface` at top; tach sees one module `specweaver.sandbox` | FR-12 |
| SB-3, Real defect 3 | live reader `language/core/junit_reports.py:64 harvest_junit` (Java, Kotlin); dead copies `java/runner.py:55 _harvest_junit`, `kotlin/runner.py:150 _parse_junit_results`, `rust/runner.py:49 _tally_junit` (no caller at all); `tests/integration/sandbox/test_lost_results_warn.py:80-100` tests only the dead copies and asserts a WARNING the live reader does not give (it logs DEBUG, `junit_reports.py:84`) | FR-10, FR-11 |
| SB-5 | Java 429 lines, Kotlin 301; Kotlin reads SARIF inline (`kotlin:195-230`), returns raw stderr as one `CompileError` on a failed build (`kotlin:241-261`) | FR-13 |
| SB-6 | `java/stack_trace_filter.py` and `kotlin/stack_trace_filter.py` differ only in names | FR-14 |
| SB-8 | Python lint timeout / no engine and complexity timeout / no engine return zero findings (`python/runner.py:217-225, 309-320`); two tests pin it (`test_python_runner.py:256-278`); TS complexity is a stub returning zero (`typescript/runner.py:169-175`); `qa_runner/core/atom.py:361-409` turns zero into SUCCESS; `core/flow/handlers/lint_fix.py:100` turns zero into PASSED in `implement_spec.yaml` | FR-1, FR-2 |
| (found 2026-10-29) | `language/core/sarif.py:65-76 read_sarif_report` and Kotlin's inline read turn a missing or malformed report into zero findings | FR-3 |
| (found 2026-10-29) | Kotlin and Rust `run_architecture_check` set `note` (not built); the atom exports it (`atom.py:500-519`) but C05 reads only `violation_count` and passes (`c05_import_direction.py:53-56`) | FR-5 |
| SB-9 | `_findings` identical in `language/core/sarif.py:31` and `workspace/ast/parsers/_sarif_complexity.py:35` | FR-14 |
| AG-12 | PMD, detekt, clippy complexity parsers and `extract_tsc_errors` in `workspace/ast/parsers/{java,kotlin,rust,typescript}/parsers.py`; `parse_clippy_complexity` has no caller | FR-11, FR-14 |
| SB-22 | `language/core/evaluator.py` (one user, `code_structure/core/atom.py:322`), `language/core/maven_output.py` (one user, Java); `sandbox/rule_atom.py` has no `src` user | FR-11, FR-14 |
| SB-24 | `except getattr(__builtins__, "FileNotFoundError", OSError)` at `typescript/runner.py:192, 293`; dead, `SubprocessExecutor` never raises it (`execution/executor.py:150`) | FR-15 |
| Real defect 7 | `typescript/runner.py:393-399` reports an ESLint architecture timeout as "Jest timed out"; `did_not_run` (`:389`) is checked first, so the timeout reason is lost; tsc has the same order (`:209, :213`) | FR-15 |
| SB-23 | MCP uses raw `Popen` (`mcp/core/executor.py:16,45`), counted in `scripts/baselines/suppressions.json` but not listed in `docs/dev_guides/subprocess_execution.md`; `executor or …Executor(cwd)` in 7 places: `git/core/executor.py:73`, the 5 runners, `filesystem/core/search.py:131` | FR-9, FR-18 |
| SB-11 | stage-and-commit three ways: `git/core/atom.py:121-148`, `git/interfaces/tool.py:166-186` (`diff --stat` stdout), `git/core/worktree_ops.py:116-121` ignores the `git add -A` result, so a failed add reads as "Nothing to commit", and the callers (`core/flow/engine/sandboxed_execution.py:103-123`, `session.py:98-128`, `step_execution.py:237`) then tear the worktree down (`worktree remove --force`) | FR-6, FR-7, FR-8 |
| X-13 | `assurance/standards/discovery.py:31,80` runs `git ls-files` (its `context.yaml` forbids `specweaver/sandbox/*`); `assurance/validation/interfaces/cli_drift.py:128` runs `git diff --cached`, catches only `CalledProcessError`, so a missing git gives a traceback | FR-16, FR-17 |

## Path List (`ADR-005`)

| Path | Span | Proof |
|---|---|---|
| P-1 `sw implement`: the lint step runs while ruff cannot run → the step FAILS, says why, calls no model | `core/flow/handlers/lint_fix` → `sandbox/qa_runner` atom → Python runner | integration test, FR-1 + FR-4 |
| P-2 `sw check` on Kotlin or Rust code → C05 shows SKIPPED with the reason | `assurance/validation` C05 → `core/flow/handlers/validation_hydrator` → atom | integration test, FR-5 |
| P-3 a sandboxed step or a session run whose worktree commit fails → the run FAILS, the worktree stays, the message names its path and the remove command | `core/flow/engine` → `sandbox/git` | integration test with real git, FR-6 + FR-7 |
| P-4 `sw standards` on a project → the files it samples honour `.gitignore`, with no process run | `assurance/standards` | unit + integration on a fixture, FR-16 |
| P-5 `sw check --drift` where git is missing → a clear error, exit 1, no traceback | `assurance/validation/interfaces` → `sandbox/execution` | unit, FR-17 |
| P-6 an agent calls `run_complexity` and the tool did not run → an error result, not "within threshold" | `sandbox/qa_runner` tool → runner | unit, FR-2 |

## Research Findings

### Codebase Patterns

- **The not-run shape already exists.** `sandbox/language/core/toolchain.py:107-170` holds one
  factory per result type (`failed_tests`, `failed_lint`, `failed_complexity`,
  `failed_architecture`, `failed_compile`): count 1, file/nodeid `<toolchain>`, code
  `ToolchainUnavailable`. Its comment says the factories exist so the shape cannot drift between
  languages. The Python runner predates them and still hand-builds its own markers
  (`<validation_engine>`, `<sandbox>`, `<timeout>`, `<no tests>`) and, in four branches, zero.
- **A check that is not built has its own shape.** `ArchitectureRunResult.note`
  (`commons/qa.py:157-175`, `TECH-064`) says "no verdict was reached". The atom exports it.
- **C05 can skip.** `c05_import_direction.py:38` already returns `self._skip(...)` when the QA
  context is missing; the skip path exists.
- **The lint-fix loop** (`lint_fix.py:94-190`): initial lint → zero means PASSED → else linter
  auto-fix → re-lint → else up to `max_reflections` model calls. A not-run result with count 1
  enters the model loop today when ruff is missing (the model is asked to fix `<toolchain>`).
- **Worktree lifecycle**: `sandboxed_execution.py` commits, strip-merges, and tears down in
  `finally`, whatever happened. `session.py:126` already keeps a parked run's worktree, so
  "keep the worktree" has a precedent.
- **`pathspec>=0.12.0`** is a declared dependency (`pyproject.toml:40`), used with
  `PathSpec.from_lines("gitignore", …)` in `workspace/ast/parsers/exclusions.py:78` and
  `assurance/graph/hasher.py:116`.
- **Boundaries.** `assurance/standards/context.yaml` forbids `specweaver/sandbox/*`.
  `assurance/validation/interfaces/context.yaml` has no forbids; `specweaver.sandbox` depends on
  `specweaver.assurance.validation`, not on its `interfaces`, so a new edge
  `assurance.validation.interfaces → specweaver.sandbox` closes no loop
  (`tach.toml:36-37, 72-73`).

### External Tools

| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| pathspec | ≥0.12.0 (declared) | `PathSpec.from_lines("gitignore", lines).match_file(rel)` | `exclusions.py:78` |
| git | system | `add -A`, `diff --cached --quiet` (exit 1 = staged changes), `diff --cached --name-only --diff-filter=ACM` | `worktree_ops.py`, `cli_drift.py` |
| SARIF 2.1.0 | — | `invocations[].executionSuccessful`: `false` means the tool failed to start, exited with failure or crashed | [SARIF notification ref](https://llaville.github.io/sarif-php-sdk/2.1/reference/notification), [GitLab MR 52](https://gitlab.com/gitlab-org/security-products/analyzers/report/-/merge_requests/52) |

Practice: a timed-out analysis job gives no signal about the change and is treated as a failure,
not a pass; fail-open linters are a known CI gap (CircleCI timeout study, ICSE 2025; Drupal
#3560616). SARIF itself separates "ran and found nothing" from "did not run" — the split this
ticket makes in SpecWeaver's own results.

### Blueprint References

None. `TECH-064` (the architecture `note`) is the in-repo precedent.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | A lint run whose tool timed out, found no container engine, or otherwise did not run SHALL return `toolchain.failed_lint(reason)` in every runner, so the QA atom reports FAILED with the reason `[agreed 2026-10-29]` | language runners | report | a lint that did not run never reads as clean |
| FR-2 | A complexity run whose tool timed out, found no container engine or did not run SHALL return `toolchain.failed_complexity(reason, max)`; the TypeScript complexity check, not built, SHALL return it with the reason "TypeScript complexity checks are not implemented" `[agreed 2026-10-29]` | language runners | report | a complexity check that did not run never reads as clean |
| FR-3 | A tool report (SARIF or JSON) that is missing or cannot be parsed after the tool ran SHALL give the not-run result of that check, not zero findings `[agreed 2026-10-29]` | `sarif.read_sarif_report`, Java and Kotlin runners | report | an unreadable report never reads as clean |
| FR-4 | When any lint of the lint-fix step (the first, after auto-fix, or after a model fix) is a not-run result, the step SHALL return FAILED with the reason at once, with no further auto-fix and no further model call `[agreed 2026-10-29]` | `LintFixHandler` | stop | no money is spent fixing an error that is not in the code |
| FR-5 | C05 SHALL return SKIPPED, with the runner's note as the reason, when the architecture result carries a `note` (no check exists for the language) `[agreed 2026-10-29]` | C05 | skip | `sw check` does not claim layering was checked when it was not |
| FR-6 | `worktree_commit` SHALL return FAILED with git's error when `git add -A` fails `[agreed 2026-10-29]` | `handle_worktree_commit` | report | a failed stage is never "Nothing to commit" |
| FR-7 | When a worktree commit fails, in a sandboxed step or a session run, the run SHALL fail and the worktree SHALL stay on disk; the error SHALL name the worktree path and the command `git worktree remove --force <path>`; nothing removes it automatically `[agreed 2026-10-29]` | `sandboxed_execution`, `session` | keep | generated code is never deleted unmerged |
| FR-8 | The checkpoint (`git/core/atom.py`), the agent commit tool (`git/interfaces/tool.py`) and `worktree_commit` SHALL stage through one function that fails on a failed `add` and detects "nothing staged" by the exit code of `diff --cached --quiet`; each keeps its own meaning of "nothing to commit" (checkpoint SUCCESS, agent tool error, worktree SUCCESS with `committed: False`) | `sandbox/git` | stage | one stage-and-check, three unchanged verdicts |
| FR-9 | No QA runner, `GitExecutor` or file search SHALL build its own host executor: the `executor or …Executor(cwd)` default goes from all 7 places and each caller passes the executor; a missing one is a `TypeError` at construction; a class that owns the choice (e.g. `EngineGitExecutor`, git always on the host) passes its executor explicitly `[agreed 2026-10-29]` | runner factory, git, filesystem search | require | host vs container is always the caller's choice, never a silent fallback |
| FR-10 | `harvest_junit` SHALL log an unreadable JUnit report at WARNING, naming the file; the test that checked the dead copies checks it instead | `junit_reports.harvest_junit` | warn | the promised warning is given by the reader that runs |
| FR-11 | The dead code SHALL be deleted: `java/runner.py _harvest_junit`, `KotlinRunner._parse_junit_results`, `rust/runner.py _tally_junit`, `parse_clippy_complexity`, `sandbox/rule_atom.py` and their tests `[agreed 2026-10-29]` | — | delete | no test keeps code no run uses |
| FR-12 | The runner factory SHALL live in `sandbox/language`, beside the runners; `sandbox/qa_runner` holds the contract and the atom/tool, and imports nothing from `sandbox/language` at any depth, lazy imports included `[agreed 2026-10-29]` | `sandbox/qa_runner`, `sandbox/language` | move | the two packages import one way |
| FR-13 | Java and Kotlin runners SHALL share one JVM base; a failed Kotlin build SHALL report its diagnostics with file and line as Java does, falling back to the build output (stdout and stderr) when none parse | JVM runners | report | a Kotlin compile error shows where it is |
| FR-14 | One copy each SHALL remain of: the JVM stack-trace filter, the SARIF walker; the PMD, detekt and tsc report parsers SHALL move from `workspace/ast/parsers` to `sandbox/language`; `evaluator.py` SHALL move beside `code_structure`, `maven_output.py` beside the Java runner | `sandbox/language`, `workspace/ast/parsers` | move | report parsing lives with the runners that read the reports |
| FR-15 | The TypeScript runner SHALL report a timeout of ESLint (architecture) and of tsc as "<tool> timed out after N s", checking the timeout before `did_not_run`; the dead `getattr(__builtins__, …)` branches go | TypeScript runner | report | a timeout names the right tool and says it timed out |
| FR-16 | Standards discovery SHALL run no process: it walks the project, skips what the project's `.gitignore` files (root and nested) and `.specweaverignore` ignore, using `pathspec`; git's global ignore file is not read `[agreed 2026-10-30]` | `assurance/standards/discovery` | walk | `sw standards` and the API find the same files with or without git |
| FR-17 | `sw check --drift` SHALL read the staged files through `SubprocessExecutor`; when git is missing or fails it SHALL print "Failed to query git index: <reason>" and exit 1, without a traceback `[agreed 2026-10-29]` | `cli_drift._staged_files` | read | no raw subprocess, no traceback |
| FR-18 | `docs/dev_guides/subprocess_execution.md` SHALL list MCP's raw `Popen` as the recorded exception, with why (a long-lived JSON-RPC pipe) and its env filter | dev guide | document | every exception to "no subprocess" is written where developers look |
| FR-19 | `docs/dev_guides/language_support_guide.md` SHALL say, for each QA method of a new language: run the tool; or, when it did not run, return the shared `failed_*` result (the step fails); or, when the check is not built, say so (`note` for architecture: C05 skips; the `failed_*` result with "not implemented" otherwise) — never a bare zero; the "static no-op violation array" advice goes `[agreed 2026-10-30]` | dev guide | document | the next language cannot bring the false clean back |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1, FR-2 | the not-run result | `toolchain.failed_lint(reason)`, `failed_complexity(reason, max_complexity)` | read `sandbox/language/core/toolchain.py:122-141` |
| FR-4 | whether the first lint is a not-run result | `QARunnerAtom._intent_run_lint` exports `errors` (asdict of `LintError`, code `ToolchainUnavailable`) | read `qa_runner/core/atom.py:350-372`, `lint_fix.py:94-104` |
| FR-5 | the runner's note | atom exports `note` → `validation_hydrator._hydrate_architecture` → `context["qa_architecture_result"]["exports"]["note"]` | read `atom.py:500-519`, `validation_hydrator.py:291-317`, `c05_import_direction.py:36-56` |
| FR-6, FR-7 | the commit verdict and the worktree path | `GitAtom.run({"intent": "worktree_commit", ...})` → `AtomResult.status/message`; teardown `{"intent": "worktree_teardown"}` | read `worktree_ops.py:105-125`, `sandboxed_execution.py:98-123`, `session.py:98-128` |
| FR-16 | gitignore matching | `pathspec.PathSpec.from_lines("gitignore", lines).match_file(rel)` | read `assurance/graph/hasher.py:103-116`, `exclusions.py:78` |
| FR-17 | a governed git call | `SubprocessExecutor(cwd).execute(cmd, *, timeout_seconds=None, ...) -> SubprocessResult` (`exit_code`, `stdout`, `stderr`, `timed_out`) | read `sandbox/execution/executor.py:56-80, 118-171` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | No command, option, API field or output changes beyond what FR-1..FR-17 name **[proof: meta — the full suite before every commit]** | suite green at every commit |
| NFR-2 | `tach check` passes at every commit with no `deprecated` edge (`TECH-081` FR-20) **[proof: arch — tach gate]** | `quality.py cb` green |
| NFR-3 | Every behaviour FR (FR-1..FR-10, FR-13, FR-15..FR-17) has a mutant in `TECH-087_mutants.json` that the suite kills **[proof: meta — corpus]** | 0 survived, 0 stale |
| NFR-4 | Discovery parity: on a fixture with a root `.gitignore`, a nested `.gitignore`, a tracked file and an untracked-not-ignored file, FR-16's walk returns exactly the set `git ls-files --cached --others --exclude-standard` returns | set equality, integration test with real git |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| pathspec | 0.12.0 | `PathSpec.from_lines("gitignore", …)` | yes — already used | no new dependency |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | "Did not run" is the shared `failed_*` result (count 1); "not built" is `note` for architecture only | the factories exist and fail closed for any reader that only counts; `note` already means "no verdict" and C05 can skip | No |
| AD-2 | The lint-fix step recognises a not-run result by the `ToolchainUnavailable` code of the shared factory, through one helper beside the factories | one place defines the shape and the test for it | No |
| AD-3 | The factory moves to `sandbox/language`; `qa_runner` keeps the contract `[agreed 2026-10-29]` | smaller move; imports go language → qa_runner only | No |
| AD-4 | Standards discovery drops git and walks with `pathspec` `[agreed 2026-10-30]` | `assurance/standards` forbids `sandbox/*`; injecting a git lister would add sandbox edges to two interface modules | No — the forbid stays |
| AD-5 | `assurance.validation.interfaces` gains `specweaver.sandbox` in `depends_on` and `consumes` for `SubprocessExecutor` `[agreed 2026-10-29]` | rule 4 "no subprocess"; no forbids rule, no loop (`tach.toml:36, 72`) | No |
| AD-6 | MCP servers stay on the host; a container for them is not this ticket `[agreed 2026-10-29]` | a security feature of its own | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| SF-01 not-run results | ~10 return sites, 1 handler, 1 rule, 2 guides | low |
| SF-02 worktree commit | ~40 lines + caller changes | medium — engine `finally` paths |
| SF-03 dead code, TS fixes | ~−150 lines | low |
| SF-04 layout and JVM base | ~−250 lines, many moves | medium — mutant drift |
| SF-05 executors, discovery, drift | 7 constructors + callers, 2 modules | medium — many callers |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| `sw implement` user | a lint step that did not run fails instead of passing, and costs no model call | high |
| any run | generated code survives a failed `git add` | high |
| `sw check` on Kotlin/Rust | C05 no longer claims a check it never ran | medium |
| developers | one JVM base, one parser each, runners beside their factory | medium |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| a pipeline that passed on a not-run lint now fails | medium | the user sees a real reason | intended (`[agreed 2026-10-29]`); the message names the tool and why |
| kept worktrees pile up | low | disk | only on a failed commit; the message gives the remove command |
| moves drift mutants | high | stale corpus | re-pin in the same commit (`TECH-081` practice) |
| `.gitignore` walk differs from git | low | standards samples another file set | NFR-4 parity test |

### Refactoring Opportunities
| Existing Feature | Current Issue | Benefit from This Feature | Effort |
|-----------------|---------------|---------------------------|--------|
| QA atom compile/test intents | the same zero-reads-clean risk | already use the factories; FR-1..FR-3 complete the set | none |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `language_support_guide.md` | FR-19: did-not-run vs not-built per QA method | ✅ SF-01 |
| `subprocess_execution.md` | FR-18: MCP's recorded exception | ⬜ SF-05 |

## Works For Real

`sw check` on a Kotlin file of a scratch project (temporary `HOME`) shows C05 SKIPPED with
"Kotlin architecture checks are not implemented". The P-1 and P-3 integration tests run the real
ruff path and real git in the suite.

## Non-Goals

- MCP servers in a container (AD-6) `[agreed 2026-10-29]`.
- Building the Kotlin/Rust architecture checks or the TypeScript complexity check.
- Findings owned by the other tickets of the 2026-10-22 audit (`TECH-079`..`TECH-091`, `TECH-070`).

## Sub-Feature Breakdown

### SF-01: A check that did not run is never clean
- **Scope**: every runner, the atom, the lint-fix step and C05 tell "did not run" and "not built" from "clean".
- **FRs**: [FR-1, FR-2, FR-3, FR-4, FR-5, FR-19]
- **Inputs**: runner results; `toolchain.failed_*`.
- **Outputs**: FAILED lint/complexity on a tool that did not run; a lint-fix step that stops without a model call; C05 SKIPPED.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf01_implementation_plan.md

### SF-02: Generated code is never lost
- **Scope**: one stage-and-check in `sandbox/git`; a failed commit fails the run and keeps the worktree.
- **FRs**: [FR-6, FR-7, FR-8]
- **Inputs**: git results.
- **Outputs**: FAILED commits; a kept worktree with its path and remove command in the error.
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf02_implementation_plan.md

### SF-03: Dead code goes, TypeScript timeouts say what timed out
- **Scope**: delete the dead readers and parsers, make the live JUnit reader warn, fix the TS timeout messages.
- **FRs**: [FR-10, FR-11, FR-15]
- **Inputs**: SF-01's runner edits.
- **Outputs**: smaller runners; correct timeout text.
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf03_implementation_plan.md

### SF-04: Runners beside their factory, one JVM base
- **Scope**: move the factory, merge Java/Kotlin, keep one copy of each parser and filter, move single-user modules.
- **FRs**: [FR-12, FR-13, FR-14]
- **Inputs**: SF-03's smaller runners.
- **Outputs**: one-way imports `language → qa_runner`; Kotlin diagnostics with file and line.
- **Depends on**: SF-03
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf04_implementation_plan.md

### SF-05: Every command through a runner the caller chose
- **Scope**: no host fallback; discovery without git; drift through `SubprocessExecutor`; MCP's exception documented.
- **FRs**: [FR-9, FR-16, FR-17, FR-18]
- **Inputs**: SF-04's factory in its new home.
- **Outputs**: constructors that require an executor; a process-free discovery; a drift command without raw subprocess.
- **Depends on**: SF-04
- **Impl Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf05_implementation_plan.md

## Execution Order

1. SF-01 and SF-02 (no deps; may run in parallel — different files)
2. SF-03 (after SF-01: same runner files)
3. SF-04 (after SF-03)
4. SF-05 (after SF-04)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | A check that did not run is never clean | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Generated code is never lost | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-03 | Dead code goes, TypeScript timeouts say what timed out | SF-01 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |
| SF-04 | Runners beside their factory, one JVM base | SF-03 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |
| SF-05 | Every command through a runner the caller chose | SF-04 | ✅ | ⬜ | ⬜ | ⬜ | ⬜ |

## Session Handoff

### Red/Blue (Phase 6), 2 cycles
- R1 (HIGH) FR-9's `TypeError` breaks classes that build a `GitExecutor` without an executor
  (`EngineGitExecutor`, `GitAtom`). Blue: the owning class passes one explicitly; SF-05's plan
  counts every constructor call first.
- R2 (MEDIUM) FR-4 covered only the first lint; a ruff timeout on a re-lint would still feed the
  model a `<toolchain>` error. Blue: FR-4 now covers every lint of the step.
- R3 (MEDIUM) FR-7 must cover the session snapshot (`step_execution._snapshot_step` raises) and the
  reconcile commit, both torn down by `session.py`'s `finally`. Blue: FR-7 names session runs; P-3
  tests both.
- R4 (MEDIUM) FR-2 fails the TS complexity stub, but no pipeline step calls complexity (only the
  agent tool, `QARunnerTool`). Blue: correct and intended; P-6 proves it at the tool.
- R5 (LOW) NFR-4: nested `.gitignore` with `!` negation. Blue: `pathspec` gitignore patterns
  support it; the fixture includes one.
- Cycle 2: challenged R1 (does git on the host contradict FR-9? No: the rule is "no silent
  fallback", and an explicit host choice is a choice). No new finding.

**Current status**: SF-01 and SF-02 committed 2026-10-30; SF-03 plan approved 2026-10-30; SF-04, SF-05 not planned.
**Next step**: Dev SF-03 (`TECH-087_sf03_implementation_plan.md`), CB-1 then CB-2.
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜
in any row and resume from there using the appropriate skill.
