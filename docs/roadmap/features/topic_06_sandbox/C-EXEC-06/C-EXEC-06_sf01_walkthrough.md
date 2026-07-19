# Walkthrough — C-EXEC-06 SF-01: Session Worktree Lifecycle + Context Rebind

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-19

## What changed and why
SF-01 introduces the **per-run (session) worktree isolation** lifecycle: when `RunContext.session_isolation`
is on, the whole pipeline run executes in **one** ephemeral git worktree instead of `D-EXEC-02`'s per-step
create/reconcile/teardown. This is the foundation that fixes `TECH-012` (multi-step isolation was broken).
No reconcile yet (SF-02) — worktree changes are discarded at teardown, so isolation is proven by "steps
share one worktree + the real source root stays unmutated."

### Source changes (4 files)
- **`core/flow/engine/runner_utils.py`** — new `execute_run(runner, run, logger)`: default-off → unchanged;
  session-on → idempotent `worktree_teardown`(prune)→`worktree_add` (unique `.worktrees/session-{run_id}` /
  `sf-session-{run_id}`), fail-closed RuntimeError on non-git, rebind a `copy.copy` context
  (`project_path`/`execution_root`→worktree, `output_dir=None`, `enforce_isolation=False`),
  `setup_sandbox_caches`, run the loop (swap+restore `runner._context`), park-guard, teardown+branch in
  `finally`.
- **`core/flow/engine/runner.py`** — `run()`/`resume()` call `execute_run(self, run, logger)`; the per-step
  dispatch is **unconditionally bypassed** while `_session_active` (no nested isolation for explicit
  `use_worktree=True` steps). The session orchestration lives in `runner_utils` (kept `runner.py` at 598 ≤ 600).
- **`core/flow/handlers/base.py`** — `RunContext.session_isolation: bool` + `allowed_paths: list[str]` (the
  latter used by SF-02's reconcile).
- **`sandbox/git/core/worktree_ops.py`** + **`atom.py`** — `handle_worktree_teardown` deletes the session
  branch (`git branch -D`, best-effort, both clean + fallback paths); `branch` added to `_ENGINE_WHITELIST`.

### Test changes
- `tests/unit/core/flow/handlers/test_run_context_session_fields.py` (5)
- `tests/unit/sandbox/git/core/git/test_worktree_teardown_branch.py` (4)
- `tests/integration/core/flow/engine/test_session_isolation.py` (8 — real git, skip-clean)
- `test_atom.py` whitelist-pin test updated (+`branch`)

## Verification results
| Check | Result |
|-------|--------|
| Unit | **4699 passed**, 15 skipped |
| Integration | **461 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5304 passed, 0 failures** |
| ruff / mypy (303) / C901 / tach | ✅ all clean |
| file size | 0 errors (`runner.py` 658→598 via the `execute_run` extraction) |

## HITL gate decisions
- **Design Phase 6:** APPROVED (2026-07-19); AD-1..5 incl. the AD-5 architectural switch (new per-run mode).
- **Impl-plan Phase 4 (audit):** Q1–Q4 all → (a) (swap+restore context; new `session_isolation` bool;
  idempotent prune-before-add; `project_path` rebind).
- **Impl-plan Phase 5:** Red/Blue merged the mandatory session-active per-step bypass.
- **Dev Phase 2 (task list):** approved (single CB-1).
- **Pre-commit Phase 1–2:** no architecture violations; combined findings presented.
- **Pre-commit Phase 3:** user pushed on corner cases → added crash-orphan recovery (Q3 proof),
  context-restore-after-exception, and fallback-path branch-delete.
- **Pre-commit Phase 5:** my `execute_run` wrapper bumped `runner.py` over the 600 line limit → extracted it
  to `runner_utils` (behavior-preserving; 826 flow tests + full mypy re-verified).

## Scope boundaries
No reconcile (SF-02) and no policy wiring (SF-03) yet — `session_isolation` is set directly in tests. Static
QA (lint/validate) and generation all run in the one worktree; the reconcile that lands generated code back
in the real repo is SF-02. Container isolation (`B-EXEC-01`) is out of scope for the whole capability.
