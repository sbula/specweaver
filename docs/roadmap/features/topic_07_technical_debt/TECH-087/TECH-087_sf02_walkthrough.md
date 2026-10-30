# Walkthrough: TECH-087 SF-02 — Generated code is never lost

Plan: [TECH-087_sf02_implementation_plan.md](TECH-087_sf02_implementation_plan.md).

## CB-1 — one stage-and-check; a failed add fails (FR-6, FR-8)

### What changed

- New `sandbox/git/core/staging.py`: `stage_all(executor) -> Staged(staged, error)`. `git add -A`,
  then `diff --cached --quiet`: 0 nothing staged, 1 staged, anything else an error; git's own words
  in the error, else the exit code.
- The checkpoint (`git/core/atom.py`), the agent commit tool (`git/interfaces/tool.py`, which read
  `diff --stat` text before) and `handle_worktree_commit` (which ignored the add result) stage
  through it. Each keeps its own "nothing to commit": checkpoint SUCCESS, agent tool error,
  worktree SUCCESS with `committed: False`.

### Red first

- `test_each_caller_fails_on_a_failed_add[worktree-commit]`
  (`tests/integration/sandbox/git/test_commit_paths_agree.py`, real git, `index.lock` held): the
  worktree commit returned SUCCESS; the checkpoint and the tool already failed.
- `test_worktree_commit.py::test_a_failed_add_fails_the_commit`: "Nothing to commit." before.
- `test_stage_all.py`: the function did not exist.
- Five agent-tool unit tests scripted the old `diff --stat` stdout ("1 file"); they now script
  `diff --cached --quiet` exit 1.

### Proof

Mutants `worktree-add-ignored` and `diff-error-reads-staged`, both killed. The C-EXEC-06 mutant
`no-commit` went stale (its symbol changed, its anchor did not); re-pinned and killed again.

### Gate notes

- The first draft made `git add` fail with a mode-000 file and skipped as root; the conventions
  check refuses a skip on something the repo controls. A held `.git/index.lock` fails for any
  user, so no skip is left.
- `tests.py cb` needs an integration test mirroring `sandbox/git`: the agreement tests live in
  `tests/integration/sandbox/git/`.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) the agent tool's roles must allow `diff`. Blue: the agreement test builds the tool
  with `whitelist_for_role("implementer")` on real git and commits.
- R2 (LOW) git output with no error text. Blue: the error names the exit code
  (`test_a_failure_with_no_error_text_still_says_which_step`).
- Cycle 2: no new finding.

## CB-2 — a failed commit or merge keeps the worktree; a rerun refuses (FR-7, P-3)

### What changed

- New `core/flow/engine/kept_worktree.py`: `keep(worktree, reason)` writes `<worktree>.kept` and
  returns the run's error (why, the path, `git worktree remove --force <path>`);
  `refuse_if_kept(worktree)`; `clear_for_new_run(...)` refuses on kept work, else prunes a crash
  leftover as before.
- Sandboxed step (`sandboxed_execution.py`): a failed commit or strip-merge keeps the worktree and
  branch; `finally` tears down only when nothing was kept; a kept worktree refuses the rerun.
- Session (`session.py`, `step_execution._snapshot_step`): a failed step snapshot, final commit or
  strip-merge sets `runner._session_kept` and keeps the worktree; `_teardown_unless_kept` holds the
  decision (a resumable park, or kept work). A new session run refuses on a kept worktree of the
  same name.
- `docs/dev_guides/pipeline_engine_guide.md` §7: the kept-work rule.

### Red first

- P-3 `tests/integration/core/flow/engine/test_failed_commit_keeps_worktree.py`, real git: the
  step's script takes the worktree's `index.lock`, so `git add -A` fails (commit cases); a dirty
  real tree fails the strip-merge (merge cases); the session's final commit is the one patched
  intent (every real failure fails a snapshot first). All seven cases failed before: the
  worktree was gone.
- `tests/unit/core/flow/engine/test_kept_worktree.py`: the module did not exist.
- Two tests that pinned teardown on a failed merge changed as agreed (Q1, 2026-10-30):
  `test_session_reconcile.py::test_worktree_kept_on_reconcile_failure`,
  `test_runner_sandbox.py::test_bouncer_strip_merge_fail_resilience`.

### Proof

Four FR-7 mutants, all killed (`failed-commit-tears-down`, `snapshot-failure-tears-down`,
`failed-merge-tears-down`, `rerun-removes-kept`). The edits moved code that 21 mutants of
B-FLOW-05, B-FLOW-07, C-EXEC-06, C-EXEC-08, D-EXEC-02 and TECH-087 rest on: each re-pinned, five
re-anchored to the same meaning (`park-tears-down-worktree`, `unresumable-park-leaks-worktree`,
`no-teardown` now in `_teardown_unless_kept`; `merge-failure-silent` on the kept branch), and all
six corpora pass.

### Gate notes

- `execute_run` rose over the cognitive-complexity limit and the new-run start was copied in two
  files; `clear_for_new_run` and `_teardown_unless_kept` fixed both.

### Red/Blue (Phase 7.5), 2 cycles

- R1 (MEDIUM) a damaged marker (not UTF-8) crashed the next run. Fixed: read with `replace`;
  `test_a_damaged_marker_still_refuses`.
- R2 (MEDIUM) the marker cannot be written (a folder in its place, disk full). Blue: this run still
  keeps the worktree (the in-memory flag decides), and the error says a later run may remove it.
- R3 (LOW) the user deletes the worktree with `rm` instead of the command. Blue: the stale marker is
  dropped and the crash-leftover teardown prunes the registration and branch, as before.
- R4 (LOW) `core/CLAUDE.md` calls core "pure"; the engine is an `orchestrator` that already reads
  and writes files and drives git; the marker belongs beside the teardown it guards.
- Cycle 2: no new finding.
