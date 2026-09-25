# C-EXEC-06 SF-01 — Walkthrough

**Commit boundary:** CB-1 (single) · **Date:** 2026-07-19 · Plan:
[sf01](C-EXEC-06_sf01_implementation_plan.md)

## Delivered

With `RunContext.session_isolation` on, the whole run executes in **one** ephemeral git worktree
instead of `D-EXEC-02`'s per-step create/reconcile/teardown — the foundation of the `TECH-012` fix. No
reconcile yet (SF-02): changes are discarded at teardown, so isolation is proven by "steps share one
worktree + the real source root stays unmutated".

| File | Change |
|---|---|
| `core/flow/engine/runner_utils.py` | `execute_run(runner, run, logger)`: default-off → unchanged. Session on → idempotent `worktree_teardown` (prune) → `worktree_add` (`.worktrees/session-{run_id}` / `sf-session-{run_id}`); fail-closed RuntimeError on non-git; rebind a `copy.copy` context (`project_path`/`execution_root` → worktree, `output_dir=None`, `enforce_isolation=False`); `setup_sandbox_caches`; run the loop (swap + restore `runner._context`); park-guard; teardown + branch in `finally` |
| `core/flow/engine/runner.py` | `run()`/`resume()` call `execute_run(self, run, logger)`; per-step dispatch is **unconditionally bypassed** while `_session_active`, so an explicit `use_worktree=True` step does not nest. `runner.py` 658 → 598 lines (≤ 600) via the `execute_run` extraction; 826 flow tests + full mypy re-verified |
| `core/flow/handlers/base.py` | `RunContext.session_isolation: bool` + `allowed_paths: list[str]` (read by SF-02) |
| `sandbox/git/core/worktree_ops.py` + `atom.py` | `handle_worktree_teardown` deletes the session branch (`git branch -D`, best-effort, clean + fallback paths); `branch` added to `_ENGINE_WHITELIST` |

Out of scope: policy wiring (SF-03 — tests set `session_isolation` directly); container isolation
(`B-EXEC-01`).

## Proof

| Test | Cases |
|---|---|
| `tests/unit/core/flow/handlers/test_run_context_session_fields.py` | 5 |
| `tests/unit/sandbox/git/core/git/test_worktree_teardown_branch.py` | 4 |
| `tests/integration/core/flow/engine/test_session_isolation.py` (real git, skip-clean) | 8 |
| `test_atom.py` whitelist-pin | updated (+`branch`) |

Corner cases covered: crash-orphan recovery (plan Q3), `runner._context` restored after an exception,
branch delete on the rmtree-fallback path.

| Check | Result |
|-------|--------|
| Unit | **4699 passed**, 15 skipped |
| Integration | **461 passed**, 5 skipped |
| E2E | **144 passed**, 1 skipped |
| **Grand total** | **5304 passed, 0 failures** |
| ruff / mypy (303) / C901 / tach | ✅ all clean |
| file size | 0 errors |

Approvals: design 2026-07-19 (AD-1..5 incl. the AD-5 switch); plan audit Q1–Q4 → (a); Red/Blue added
the mandatory session-active per-step bypass.
