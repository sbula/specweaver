# Walkthrough — C-EXEC-06 SF-02: Commit-Before-Reconcile + Authorized Strip-Merge

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-19

## What changed and why
SF-02 adds the **reconcile** — the DAL-C authorization gate. At span end (COMPLETED runs only), the session
worktree's changes are committed onto the session branch and a single `strip_merge` writes back to the real
repo **only** paths in `allowed_paths` (+ the `README.md`/`docs/` hard-block). This lands generated code back
safely and fixes `TECH-012` Gap 1 (nothing was ever committed) + Gap 2 (allow-list now actually applied).

### Source changes (3 files)
- **`sandbox/git/core/worktree_ops.py`** — `handle_worktree_commit` (stage+commit in the worktree, skip if
  clean); `_strip_forbidden_files` (extracted; now **deletes** stripped *new* files from disk);
  `handle_strip_merge` gained a `cwd` param, a **merge-failure guard** (dirty real tree → `--abort` + FAILED),
  and a **post-strip empty check** (all-stripped → abort, no noise commit).
- **`sandbox/git/core/atom.py`** — `_intent_worktree_commit`; `_intent_strip_merge` passes `self._cwd`;
  (`branch` whitelist entry was added in SF-01).
- **`core/flow/engine/runner_utils.py`** — reconcile in `execute_run`: COMPLETED-only,
  `worktree_commit → strip_merge(allowed_paths)`, **raise** on either FAILED (never swallow — fixes the
  INT-US-09 swallowed-failure defect).

### Two real bugs found & fixed (exposed by the corner-case tests)
1. **Stripped NEW files were left on disk** untracked — `checkout -- <file>` can't remove a file absent from
   HEAD. Now deleted → a disallowed file never reaches the real working tree (the core DAL-C property).
2. **All-stripped created an empty noise merge commit** — completing an in-progress merge commits even with
   no changes. Now a post-strip `diff --cached --quiet` aborts cleanly.

### Test changes
- `tests/unit/sandbox/git/core/git/test_worktree_commit.py` (4)
- `tests/integration/core/flow/engine/test_session_reconcile.py` (11 — real git: lands-allowed/strips-
  disallowed, failed-run-skip, strip/commit-fail surfaced, dirty-tree fail-loud, empty-allowed, hard-block,
  graceful-teardown-on-failure, all-stripped, empty-session, doc_updates-survives)
- `test_atom.py` intent-set + 2 strip_merge mock sequences updated

## Verification results
| Check | Result |
|-------|--------|
| Unit | **4703 passed**, 15 skipped |
| Integration | **472 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5319 passed, 0 failures** |
| ruff / mypy / C901 / tach / file-size | ✅ all clean |

## HITL gate decisions
- **Impl-plan Phase 4 (audit):** Q1–Q5 all → (a) — COMPLETED-only reconcile, dirty-tree fail-loud +
  merge-abort, skip empty commit, `chore` commit lands the code.
- **Dev Phase 2 (task list):** approved (single CB-1).
- **Pre-commit Phase 1–2:** no architecture violations; combined findings presented.
- **Pre-commit Phase 3:** user pushed on corner cases / graceful teardown → expanded to 7 gap tests (incl.
  graceful-teardown-on-reconcile-failure), which surfaced the two latent bugs above.

## Scope boundaries
The reconcile is wired but `session_isolation`/`allowed_paths` are still set directly in tests — the
composition-root **policy + allow-list population + the multi-step generated-file e2e proof** are SF-03,
which completes `C-EXEC-06` and unblocks `INT-US-09-SF05` → `INT-US-03 SF-03`.
