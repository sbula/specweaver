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
