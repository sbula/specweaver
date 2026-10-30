# Walkthrough: TECH-087 SF-05 — Every command through a runner the caller chose

Plan: [TECH-087_sf05_implementation_plan.md](TECH-087_sf05_implementation_plan.md).

## CB-1 — the caller chooses the executor (FR-9)

### What changed

- The JVM, Python, TypeScript and Rust runners, `GitExecutor` (and so `EngineGitExecutor`),
  `grep_content` and `_grep_ripgrep` take their executor as a required parameter. The
  `executor or …Executor(cwd)` defaults are gone, so leaving the executor out is a `TypeError`.
- `resolve_runner(cwd, executor, language=None)` requires it. On the host path, `qa_atom` builds
  `SubprocessExecutor(cwd)` itself.
- These callers now choose the host explicitly:
  - `GitAtom` (the engine and its worktree commit);
  - `create_git_interface` (every role);
  - `FileSystemTool.grep`.
- Guides:
  - `subprocess_execution.md`: callers pass the executor. The stale `QARunnerAtom(cwd,
    sandbox_settings)` section now shows `qa_atom`.
  - `language_support_guide.md`: the runner constructor takes the executor.

### Red first

- `tests/unit/sandbox/test_no_host_executor_fallback.py` (`ast`) was red on the 6 fallbacks and on
  `resolve_runner`'s default. It globs `language/core/*/runner.py`, so a new runner is covered.
- These went red because each constructor still built a default:
  - `test_runner_migration.py`: the 5 `test_creates_default_executor` cases became
    `test_needs_an_executor`;
  - `test_git_executor.py::TestNeedsAnExecutor`;
  - `test_search.py::test_grep_without_an_executor_is_refused`.
- `test_runner_factory.py::test_on_the_host_the_factory_chooses_the_executor` was red because
  `qa_atom` passed `None`.
- 19 test files now pass `SubprocessExecutor(cwd=…)` where they relied on the default.
  `test_git_atom.py` patches `execution.executor.SubprocessExecutor.execute`: the class itself, no
  longer the name in `git.core.executor`.

### Proof

- New FR-9 campaign, all 4 killed:
  - `runner-builds-host-executor`;
  - `factory-passes-no-executor`;
  - `git-builds-host-executor`;
  - `grep-builds-host-executor`.
- Re-pinned (`qa_atom` changed): `B-FLOW-01` FR-14 `scenario-mount-on-coder` and `D-INTL-08` FR-2
  `atom-drops-the-language`. Both corpora have no survivor, and 0 mutants are stale in 51 corpora.
- Probes:
  - the `FileSystemTool.grep` executor removed: the tool's grep tests go red;
  - the `conflict_resolver` facade's executor removed: it survived at first, and is killed by
    `test_git_interfaces.py::TestTheFactoryChoosesTheHost` (Phase 3 gap).

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) Python accepts an explicit `executor=None`, which fails later with
  `AttributeError`. Accepted: FR-9 is about a missing executor; `mypy` in `cb` rejects `None`
  for the required type.
- R2 (MEDIUM) The constructors' signatures changed, so an outside caller that relied on the default
  breaks. Accepted: that is FR-9's point. No entry point or guide builds a runner directly.
- R3 (LOW) The worktree commit's executor gets the worktree as `cwd`. Git runs as `git -C
  <worktree>`, so the executor's `cwd` is only the confinement root, as before. No change.
- R4 (LOW) The `conflict_resolver` facade had no test. Fixed (Proof).
- Cycle 2: challenged R1 (could a caller pass `None` through `qa_atom`? No: `qa_atom` always
  builds one). No new finding.

## CB-2 — discovery without git, drift through the executor, MCP recorded (FR-16, FR-17, FR-18)

### What changed

- `assurance/standards/discovery.py` is one `os.walk`, and it runs no process.
  - It still skips `.git`, hidden folders and the analyzers' build and cache folders (Q1).
  - Each folder's `.gitignore` is scoped to that folder. The last matching pattern wins, and a
    deeper file comes later.
  - It does not enter an ignored folder.
  - `.specweaverignore` and the binary patterns apply on top, as before.
  - Removed: `_git_ls_files`, its tests, and the raw `subprocess` import with its `noqa`.
  - Also removed: the "pathspec not installed" fallback and its test. `pathspec` is a required
    dependency, and the walk needs it.
- `cli_drift._staged_files` runs `git diff --cached` through `SubprocessExecutor`, with a 30 s
  timeout.
  - When git is missing, fails or times out, it prints one line `Failed to query git index:
    <reason>` and exits 1. Before, a missing git gave a traceback.
  - It forwards `GIT_INDEX_FILE` and `GIT_WORK_TREE` when they are set, so a pre-commit hook after
    `git commit -a` checks the commit's own index.
- Boundaries:
  - `tach.toml`: `assurance.validation.interfaces` depends on `specweaver.sandbox`, which exposes
    `execution.executor.SubprocessExecutor`. The interfaces `context.yaml` consumes
    `specweaver/sandbox/execution` (AD-5).
  - `TECH-002`'s layer test names that one import as its only exception, by equality (Q2,
    `[agreed 2026-10-30]`).
- Suppression baseline re-frozen down: `noqa:TID251` 3 → 1 (MCP only), total 189 → 185.
- `subprocess_execution.md` (FR-18): MCP's raw `subprocess.Popen` is listed with its reason (a
  long-lived JSON-RPC pipe) and its safeguard (`build_child_env`, the same allowlist and credential
  strip). The design's guide row is ✅.
- `README.md` counts: 12,051 tests (9,581 unit, 2,020 integration), 24 toolchain, 11,988 by
  default, 51 corpora with 1,253 mutants.

### Red first

- `tests/integration/assurance/standards/test_discovery_matches_git.py` (NFR-4) runs real git on a
  fixture with a root and a nested `.gitignore`, a `!` negation, an anchored pattern, an ignored
  folder, tracked and untracked files. It was red with 6 extra files: discovery on the copy without
  `.git` read no `.gitignore`.
- `test_standards_discovery.py::TestGitignore`:
  - red: root scope, nested scope, anchoring, negation, "no process in a git repo" (it caught
    `git ls-files`), and "no `subprocess` import";
  - green from the start, because the old walk already behaved this way: the pruned folder and the
    unreadable `.gitignore`.
- `tests/unit/assurance/validation/interfaces/test_cli_drift_staged_files.py` was red (no executor
  in `cli_drift`). It now has 7 cases, including the forwarded variables and nothing else.
- `tests/integration/assurance/validation/test_drift_staged_files_git.py` (real git):
  - "no git on PATH" was red with a `FileNotFoundError` traceback;
  - "the hook's index" passed on raw `subprocess`. It went red (`[] == ['b.py']`) once drift moved
    to the executor without forwarding, and green with it.
- `tests/unit/test_subprocess_guide_records_mcp.py` was red until the guide named
  `subprocess.Popen` and `build_child_env`. It also pins MCP as the only `noqa: TID251` in `src`.
- `test_drift_rot_handler.py` patches `cli_drift.SubprocessExecutor.execute`.

### Proof

- New FR-16 campaign, 3 killed: `discovery-ignores-gitignore`, `parent-rules-not-inherited` and
  `nested-gitignore-unscoped`.
- New FR-17 campaign, 3 killed: `drift-error-swallowed`, `drift-timeout-unnamed` and
  `drift-hook-index-dropped`.
  - The plan's `drift-traceback-on-missing-git` (a narrowed `except`) has no line to mutate now:
    there is no `try`. `drift-timeout-unnamed` takes its place.
- 0 stale mutants in 51 corpora.
- Probes:
  - `_HOOK_GIT_ENV` without `GIT_WORK_TREE` survived at first; the Phase 3 test kills it;
  - a second sandbox import in `cli_drift.py` is killed by the layer test.
- `check_fr_coverage.py TECH-087`: 19 of 19 FRs planned and cited.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) In a git repo, hidden and tool folders (`.github/`, `migrations/`) are now skipped
  where git listed them. Accepted by the user (Q1).
- R2 (MEDIUM) A tracked file that `.gitignore` names is listed by git but skipped by the walk.
  Accepted (plan R4): rare, and not a source the standards should learn from.
- R3 (MEDIUM) A project inside a larger repo does not read the parent repo's `.gitignore`.
  Accepted: FR-16 names the project's own files.
- R4 (LOW) Other hook variables (`GIT_OBJECT_DIRECTORY`, `GIT_COMMON_DIR`) are not forwarded.
  `GIT_DIR` is on the allowlist already, and the two forwarded variables are the ones `git commit
  -a` and `git commit <paths>` set for a hook. Accepted.
- R5 (LOW) `.env` and other hidden *files* are listed when not ignored. Git lists them too, and the
  old walk did as well. Unchanged.
- Cycle 2: challenged R4 by testing the forwarded set exactly, not a subset, so a credential cannot
  ride along. Found the untested `GIT_WORK_TREE` and fixed it. No new finding.
