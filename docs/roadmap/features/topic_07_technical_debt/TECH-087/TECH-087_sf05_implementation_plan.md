# Implementation Plan: QA Runners Are Split, Copied, and Can Report a Skipped Tool as Clean [SF-05: Every command through a runner the caller chose]
- **Feature ID**: TECH-087
- **Sub-Feature**: SF-05 — Every command through a runner the caller chose
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-05
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf05_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-9 (no QA runner, `GitExecutor` or file search builds its own host executor; a missing one is a
`TypeError`), FR-16 (standards discovery runs no process: a walk that honours `.gitignore` and
`.specweaverignore` through `pathspec`), FR-17 (`sw check --drift` reads the index through
`SubprocessExecutor`; a missing git prints one line and exits 1), FR-18 (the subprocess guide
records MCP's raw `Popen` with why and its env filter). Kind `bugfix` for every boundary: FR-9
changes constructor calls in tests. NFR-1: no command, option or output changes beyond these.

## Research Notes

Measured 2026-10-30 against `0e98dc16`. Paths under `src/specweaver/`.

- **The host fallbacks (FR-9), 6 places now** (SF-04 merged Java and Kotlin into one base):
  `sandbox/language/core/jvm/runner.py:62`, `python/runner.py:105`, `typescript/runner.py:95`,
  `rust/runner.py:55` (`executor or …Executor(cwd=cwd)`); `sandbox/git/core/executor.py:73`
  (`subprocess_executor or SubprocessExecutor(cwd=cwd)`); `sandbox/filesystem/core/search.py:131`
  (`executor or SubprocessExecutor(cwd=search_dir)`, inside `_grep_ripgrep`).
- **Who builds them in `src`:**
  - Runners: only `language/core/runner_factory.py:59 resolve_runner`. `qa_atom` (`:100-109`)
    passes `None` on the host path. The docstring says "None lets each runner build its own host
    executor".
  - `EngineGitExecutor(cwd, whitelist)` (inherits `GitExecutor.__init__`): `git/core/atom.py:66`
    and `:460`, `git/interfaces/facades.py:282`. `GitExecutor(cwd, whitelist)`: `facades.py:284`.
  - `grep_content(...)`: `filesystem/interfaces/tool.py:191`, no executor.
- **Test call sites without an executor** (one-line count, a floor): `PythonQARunner` 22 in 14 files,
  `JavaRunner` 7, `KotlinRunner` 5, `TypeScriptRunner` 5, `RustRunner` 3, `resolve_runner` 15 in 3
  files, `EngineGitExecutor` 1, `grep_content` 2. About 60 calls in about 30 files.
  `tests/unit/sandbox/language/core/test_runner_migration.py:37-47` pins "auto-creates a
  SubprocessExecutor". That test inverts: it now asserts the `TypeError`.
- **`SubprocessExecutor.execute` never raises on a missing binary.** `OSError` becomes
  `exit_code=-1` with `stderr=str(exc)` (`sandbox/execution/executor.py:150-151`). FR-17 reads
  `exit_code != 0 or timed_out` and prints the stderr.
- **Standards discovery today** (`assurance/standards/discovery.py`):
  - In a git repo it runs `git ls-files --cached --others --exclude-standard` (raw `subprocess`,
    `noqa: TID251`).
  - Otherwise `os.walk` skips `.git`, every dot-directory and the analyzers' default directories:
    `__pycache__/ .pytest_cache/ .tox/ .venv/ target/ build/ .gradle/ vendor/ bin/ pkg/ out/ obj/
    data/ migrations/ node_modules/ dist/ …`.
  - Then `.specweaverignore` and the analyzers' binary patterns go through `pathspec` on top.
  - Users: `assurance/standards/interfaces/cli.py:146` and `interfaces/api/v1/standards.py:72`.
  - Tests: `tests/unit/assurance/standards/test_standards_discovery.py`. `TestWalkWithSkips` and
    `TestDiscoveryEdgeCases` pin the skips. `TestGitLsFiles` and `TestGitLsFilesIsolated` patch
    `subprocess`, and both go.
- **`pathspec` gitignore semantics.** `PathSpec.from_lines("gitignore", lines)` gives last-match-wins
  and `!` negation. A nested `.gitignore` is relative to its own directory, so its patterns are
  matched against the path relative to that directory. Git does not descend into an ignored
  directory, so the walk prunes it the same way and a `!` cannot re-include a file under it.
- **Drift today** (`assurance/validation/interfaces/cli_drift.py:119-139`): `subprocess.run(...,
  check=True)` catches only `CalledProcessError`. A missing git raises `FileNotFoundError` and gives
  a traceback. There is no timeout. Tests patch `_staged_files`
  (`tests/integration/interfaces/cli/test_cli_doors_build_alike.py:157`).
- **Boundaries for FR-17 (AD-5).** No module outside `specweaver.sandbox` imports
  `sandbox.execution.executor` today. `tach.toml:230` exposes no `execution.executor` path, so
  the edge needs one. `assurance.validation.interfaces` gains `specweaver.sandbox` in
  `depends_on` (`tach.toml:37`), and its `context.yaml` gains the consume. `specweaver.sandbox`'s
  own `depends_on` (`tach.toml:73`) does not reach `assurance.validation.interfaces`, so no loop
  forms.
- **The suppression baseline** (`scripts/baselines/suppressions.json`) counts `noqa:TID251` = 3:
  discovery, drift and MCP. After this SF it counts 1 (MCP). A decrease is re-frozen with
  `check_suppressions.py --update-baseline`.
- **The subprocess guide** (`docs/dev_guides/subprocess_execution.md`):
  - `:10-12` already names `MCPExecutor`'s exemption and the pipe reason. It does not name the env
    filter (`build_child_env`, `mcp/core/executor.py:41`).
  - `:74-87` says "Production: auto-creates a default executor". This goes with FR-9.
  - `:163-180` still shows `QARunnerAtom(cwd=…, sandbox_settings=…)`, which SF-04 replaced with
    `qa_atom`. It is stale, and it is fixed here because the same section changes.

## Audit (Phase 2) and Architecture (Phase 3)

### Decided at the Phase 4 gate

- **Q1 — the old built-in skips stay in the new walk, for every project** `[agreed 2026-10-30]`.
  These are the dot-directories and the analyzers' default directories (`node_modules/`, `.venv/`,
  `target/`, `build/`, `migrations/`, …). They apply on top of `.gitignore` and
  `.specweaverignore`. In a git repo, a tracked `.github/` or `migrations/` folder is no longer
  sampled; the user accepted that. The NFR-4 parity fixture holds no folder from the skip list, so
  the set equality still proves the `.gitignore` logic.

- **Q2 — `TECH-002`'s layer test and the drift import** (found during CB-2). The test forbids every
  sandbox import under `assurance/validation`, which AD-5's import broke. The test now names
  `cli_drift.py: specweaver.sandbox.execution.executor` as its one exception, by equality, so an
  unused exception fails too. Chosen over keeping raw `subprocess` in drift `[agreed 2026-10-30]`.

### Settled by the design or the code

1. **FR-9 signature.** Each constructor takes `executor` as a required parameter, with no default:
   `JvmRunner`, `PythonQARunner`, `TypeScriptRunner`, `RustRunner`, `GitExecutor`
   (`subprocess_executor`), and `grep_content`/`_grep_ripgrep` (`executor`). Missing it raises
   Python's own `TypeError`. `resolve_runner(cwd, executor, language=None)` requires it too.
2. **Who chooses the host, explicitly** (design R1):
   - `qa_atom` builds `SubprocessExecutor(cwd=cwd)` when there is no container.
   - `GitAtom` and the git facade pass `SubprocessExecutor(cwd=…)` to `EngineGitExecutor` and
     `GitExecutor`. Git always runs on the host.
   - `FileSystemTool.grep` passes `SubprocessExecutor(cwd=resolved)`.
3. **FR-9 guard.** A unit test reads with `ast` every file under `sandbox/language/core/*/runner.py`
   (the glob, so a new runner is covered), plus `runner_factory.py`, `git/core/executor.py` and
   `filesystem/core/search.py`. It fails on a `BoolOp(Or)` whose right side calls a name ending in
   `Executor`, and on a parameter `executor` or `subprocess_executor` with a default. It is red
   today on the 6 fallbacks and on `resolve_runner`'s default. The `TypeError` cases prove the
   behaviour.
4. **FR-16 walk.**
   - Walk from the root and prune `.git`. Apply the built-in skip list (Q1).
   - In each directory, read its `.gitignore`, if there is one, into a spec scoped to that
     directory. A path is ignored when the last matching pattern, root first and nearest last,
     says so (git's order).
   - Prune ignored directories before descending into them.
   - `.specweaverignore` and the binary patterns apply on top, as today.
   - Git's global excludes and `.git/info/exclude` are not read `[agreed 2026-10-30]`.
   - A tracked file that `.gitignore` names is skipped. Git would list it. This is accepted (see
     R-list).
5. **FR-16 "no process"** is proven two ways. The module imports no `subprocess` (the `noqa` goes,
   so TID251 now guards it). The NFR-4 test runs real git only to compute the expected set.
6. **FR-17.** `_staged_files` runs `SubprocessExecutor(cwd=Path.cwd()).execute(cmd,
   timeout_seconds=30)`. When `timed_out` is set or `exit_code != 0`, it prints `Failed to query
   git index: <stderr or "timed out">` and exits 1. It keeps the same stdout parsing.
   It passes `extra_env` with `GIT_INDEX_FILE` and `GIT_WORK_TREE` when they are set. Inside a
   pre-commit hook, `git commit -a` and `git commit <paths>` point `GIT_INDEX_FILE` at a temporary
   index. `child_env._DEFAULT_ENV_ALLOWLIST` keeps `GIT_DIR` but strips these two, so without them
   drift would read the main index: the wrong files (Red/Blue R7).
7. **FR-18** adds the env filter to the existing exemption line: `build_child_env`, which applies
   the same allowlist and credential strip as `SubprocessExecutor`. A doc test asserts that the
   guide names `MCPExecutor`, the pipe and `build_child_env`.

## Approach (pseudocode, ordered)

**CB-1 — the caller chooses the executor (FR-9)**
1. Red: write the guard (Settled 3). Write the `TypeError` cases: one per class and one for
   `grep_content`. Invert `test_runner_migration.py`. Write a `qa_atom` host case: the runner's
   executor is a `SubprocessExecutor` with `cwd` equal to the project root, and it was built by
   `qa_atom`.
2. Remove the 6 defaults. Make `resolve_runner` require `executor`. `qa_atom` builds the host
   executor.
3. Change the `src` callers (Settled 2). Change the test call sites to pass
   `SubprocessExecutor(cwd=…)` or their existing mock.
4. Guide: change `subprocess_execution.md` §"Injecting an executor" (the caller passes one) and
   §"Opt in" (`qa_atom`, not `QARunnerAtom(...)`). In `language_support_guide.md`, the runner
   constructor takes the executor.
5. Add mutants: `runner-builds-host-executor` (restore one `or` default), `git-builds-host-executor`
   and `grep-builds-host-executor`.

**CB-2 — discovery without git, drift through the executor, MCP recorded (FR-16, FR-17, FR-18)**
6. Red: the NFR-4 parity test (integration, real git), with this fixture:
   - a root `.gitignore`;
   - a nested `.gitignore` with a `!` negation;
   - a tracked file and an untracked, not-ignored file;
   - an ignored directory that holds a file.

   Expected: `git ls-files --cached --others --exclude-standard`. It is red because the walk
   ignores `.gitignore` when there is no `.git`; the test runs discovery on a copy without `.git`.
   Unit cases: nested scope, negation, a pruned directory, and a `.gitignore` that cannot be read
   (skipped and logged).
7. Rewrite `discover_files`: one walk, no git, no `subprocess` (Settled 4). Delete
   `_git_ls_files` and its tests. Keep the built-in skips (Q1).
8. Red: three drift unit cases with a doubled executor:
   - exit -1 with stderr: the message and exit 1, no traceback;
   - timed out: the message and exit 1;
   - success: the staged paths;
   - integration, real git: with `GIT_INDEX_FILE` pointing at a second index that stages a file
     the main index does not, the file is listed. Red: the executor strips the variable.

   Then the green: `_staged_files` through `SubprocessExecutor` (Settled 6).
9. Boundaries: `tach.toml` adds `specweaver.sandbox` to `assurance.validation.interfaces`'
   `depends_on` and exposes `execution.executor.SubprocessExecutor`. The interfaces `context.yaml`
   consumes `specweaver/sandbox/execution`. Drop both `noqa: TID251`, then re-freeze the
   suppression baseline (3 → 1).
10. FR-18: the guide line and its doc test (Settled 7).
11. Add mutants: `discovery-ignores-gitignore`, `nested-gitignore-unscoped`,
    `drift-traceback-on-missing-git` (catch narrowed back), `drift-error-swallowed` and
    `drift-hook-index-dropped` (the `extra_env` removed).

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | `test_no_host_executor_fallback.py` (ast guard) | FR-9 | 6 fallbacks today |
| unit | the `TypeError` cases, the inverted `test_runner_migration.py`, the `qa_atom` host case | FR-9 | the constructors default today |
| integration | `tests/integration/assurance/standards/test_discovery_matches_git.py` | FR-16, NFR-4 | without `.git` the walk reads no `.gitignore` |
| unit | `test_standards_discovery.py` nested, negation, prune, unreadable | FR-16 | no `.gitignore` logic today |
| unit | `test_cli_drift_staged_files.py` | FR-17 | `FileNotFoundError` gives a traceback today |
| integration | `test_drift_hook_index.py` (real git, `GIT_INDEX_FILE`) | FR-17 seam, NFR-1 | the executor strips the variable |
| unit | the subprocess-guide doc test | FR-18 | no `build_child_env` in the guide |
| arch | `tach check`, TID251 | NFR-2, FR-16/17 | the `noqa`s go |
| all | the suite | NFR-1 | — |

Every new or changed test file names `Proves: TECH-087 FR-<n>`.

## Commit Boundaries

| CB | Holds | Kind | Done when |
|---|---|---|---|
| CB-1 | steps 1–5 | bugfix | guard green; suite green; the 3 FR-9 mutants killed |
| CB-2 | steps 6–11 | bugfix | parity green; suite green; 0 stale; stage and stop (closes SF-05 and the last SF) |

After CB-2: the closure gate (`check_fr_coverage.py TECH-087`, `tests.py feature TECH-087`), the
live demo (C05 SKIPPED for Kotlin in a scratch `HOME`), the README counts, then the finished message.

## Documentation

- `docs/dev_guides/subprocess_execution.md`: FR-9 (callers pass the executor), the stale `qa_atom`
  section, and FR-18.
- `docs/dev_guides/language_support_guide.md`: the runner constructor takes the executor.
- The design's guide row for `subprocess_execution.md` changes to ✅ SF-05.

## Architecture Verification (Phase 3)

| Mechanism | Module | Allowed? |
|---|---|---|
| process (git) through `SubprocessExecutor` | `assurance/validation/interfaces` (orchestrator, no forbids) | yes, AD-5 `[agreed 2026-10-29]` |
| file walk, `pathspec` | `assurance/standards` (forbids `specweaver/sandbox/*`) | yes: no sandbox import, no process |
| executor parameters | `sandbox/language`, `sandbox/git`, `sandbox/filesystem` | yes: inside `specweaver.sandbox` |

- One new `tach` edge, `assurance.validation.interfaces → specweaver.sandbox`, plus one expose.
  `specweaver.sandbox` does not depend on it, so the graph stays acyclic.
- No new module. The walk stays in `discovery.py`, its one user. `workspace/ast/parsers/exclusions.py`
  (`SpecWeaverIgnoreParser`, consumable from here) reads only `.specweaverignore` into one flat
  spec. It has no nested scoping, so there is nothing to share. The walk does not grow into it
  either, because only discovery needs nested `.gitignore`.

## Consistency (Phase 5)

- **Coverage.**
  - FR-9: CB-1, with the guard, the `TypeError` cases and 3 mutants.
  - FR-16: CB-2, with the NFR-4 parity test and 2 mutants.
  - FR-17: CB-2, with the unit cases, the hook-index integration test and 3 mutants.
  - FR-18: CB-2, with a doc test.
  - NFR-1 is covered by the suite at every commit, NFR-2 by `tach`, and NFR-3 by the mutants
    above.
  - AD-4 is step 7 and AD-5 is step 9. AD-6 does not apply: MCP stays on the host and is only
    documented.
  - Design risk "the `.gitignore` walk differs from git": NFR-4.
- **Built-in skips (Q1) are held by tests already.**
  `test_build_artefacts_stay_out_of_context_e2e.py` (no `.git`, no `.gitignore`) expects
  `node_modules/`, `target/`, `build/` and `.venv/` to stay out. Keeping the skips keeps it green.
- **Hand-off risk.**
  - Step 6 is red only on a copy without `.git`: today, with `.git` present, discovery uses
    `git ls-files` and is green by construction.
  - The expected set comes from git on the original. Compare relative posix paths, because
    discovery returns resolved absolute paths.
  - The fixture uses only `.py` and `.txt` files, so the analyzers' binary patterns remove nothing.
- **Red/Blue, 2 cycles:**
  - R1 (MEDIUM) the parity test would pass first on a git fixture, so it would never go red.
    Fixed: it runs discovery on a copy without `.git` (step 6, hand-off note).
  - R2 (MEDIUM) a guard listing 6 files misses the next runner. Fixed: it globs the runner files,
    and covers `resolve_runner`'s default too (Settled 3).
  - R3 (MEDIUM) does `SubprocessExecutor`'s env strip break git in drift? No:
    `child_env._DEFAULT_ENV_ALLOWLIST` keeps `PATH`, `HOME` and `GIT_EXEC_PATH`.
  - R4 (LOW) a tracked file that `.gitignore` names is listed by git but skipped by the walk.
    Accepted: rare, and the design's NFR-4 fixture excludes it.
  - R5 (LOW) a project nested inside a larger repo does not read the parent repo's `.gitignore`.
    Accepted: FR-16 names the project's own files.
  - R6 (LOW) a symlinked directory is not followed (`os.walk` default), and git does not follow it
    either. No action.
  - Cycle 2: challenged R3. Git sets more than `PATH` and `HOME` for a hook.
    - R7 (HIGH) `GIT_INDEX_FILE` and `GIT_WORK_TREE` are not on the allowlist. In a pre-commit
      hook after `git commit -a`, drift would read the main index and check the wrong files. Fixed:
      `_staged_files` forwards both when set (Settled 6), with an integration test and a mutant.
    - The allowlist itself is not widened: it is shared by every agent command.
  - Cycle 3: challenged R7 (is a missing `GIT_INDEX_FILE` harmless? yes: nothing is forwarded, and
    git uses the default index). No new finding.
- All decisions are resolved and documented inline in the plan; the user approved it `[agreed 2026-10-30]`.
