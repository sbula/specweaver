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
