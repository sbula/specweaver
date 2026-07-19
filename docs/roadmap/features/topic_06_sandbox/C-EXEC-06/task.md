# Task List — C-EXEC-06 SF-01: Session Worktree Lifecycle + Context Rebind

- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf01_implementation_plan.md
- **FRs**: FR-1 (lifecycle+teardown+branch), FR-2 (rebind), FR-5-field, FR-6 (fail-closed), FR-7 (park-guard)
- **Commit boundary**: single **CB-1**. Foundation-first (fields → teardown primitive → wrapper → bypass/guards).
- **No reconcile in SF-01** — worktree changes discarded at teardown (SF-02 adds commit+reconcile).

## Tasks

- [x] **T1 — `RunContext` fields** (FR-5 field, FR-7)
  - src: `src/specweaver/core/flow/handlers/base.py` — add `allowed_paths: list[str] = Field(default_factory=list)` and `session_isolation: bool = False`.
  - test: `tests/unit/core/flow/handlers/test_run_context_session_fields.py` — defaults.

- [x] **T2 — Branch-aware teardown** (FR-1)
  - src: `src/specweaver/sandbox/git/core/worktree_ops.py` — `handle_worktree_teardown` deletes the branch (`git branch -D <branch>`) when `context["branch"]` is set; best-effort, logged; no `branch` → unchanged.
  - test: `tests/unit/sandbox/git/...` (or extend existing worktree_ops test) — branch deleted when passed; untouched when absent; delete-failure logged not raised.

- [x] **T3 — Session lifecycle wrapper** (FR-1, FR-2, FR-6)
  - src: `runner.py` (+ helper in `runner_utils.py`) — `run()`/`resume()` call `_execute_maybe_session(run)`: if `context.session_isolation` → create worktree `.worktrees/session-{run_id}` / branch `sf-session-{run_id}` (**idempotent: prune a stale same-named worktree+branch before add**, Q3); rebind `copy.copy(context)` (`project_path`/`execution_root`→worktree, `output_dir=None`); `setup_sandbox_caches`; run `_execute_loop` against it (swap+restore `self._context`, Q1); teardown worktree+branch in `finally`; **fail-closed** RuntimeError on create failure. Else → `_execute_loop` unchanged.
  - test: `tests/integration/sandbox/...test_session_isolation.py` (real git, skip-clean) — 2-step pipeline: step1 writes a file, step2 reads it → persists across steps in ONE worktree; real source root unmutated; `.worktrees/` + branch gone after; non-git project → fail-closed; `session_isolation=False` → per-step path unchanged (control).

- [x] **T4 — Session-active per-step bypass + park-guard** (FR-7, Red/Blue)
  - src: `runner.py` — when a session is active, **unconditionally bypass** the per-step `execute_in_sandbox` dispatch (`:321-327`) even for `use_worktree=True` steps (no nested isolation); raise a clear error if a step PARKS under session isolation (v1 unsupported).
  - test: integration — a `use_worktree=True` step inside a session runs in the SESSION worktree (not nested); a parking step under session → clear error.

- [ ] **T5 — Full suite + pre-commit gate (CB-1)**
  - Full unit/integration/e2e; fix any regression project-wide. Run pre-commit skill. HITL commit stop (direct to master).

## Adversarial Test Matrix (per task — 4 buckets)
| Task | Happy | Boundary/Edge | Graceful Degradation | Hostile/Wrong Input |
|------|-------|---------------|----------------------|---------------------|
| T1 | fields present | defaults empty/False | — (pure model) | wrong type rejected by Pydantic |
| T2 | branch passed → deleted | no branch → untouched | branch-delete fails → logged, not raised | non-existent branch → best-effort no crash |
| T3 | 2-step file persists in one worktree; real root unmutated | cleanup removes worktree+branch; crash-orphan pruned before re-add | non-git project → fail-closed RuntimeError | `session_isolation` on a run with no steps → clean no-op |
| T4 | `use_worktree=True` step runs in session worktree | session-off → per-step path unchanged | — | parking step under session → clear error |

## Progress
- T1–T4 complete (TDD red→green→refactor, lint clean). mypy clean on 4 changed src files. tach ✅.
- Full suite: unit 4698 · integration 459 (+6 session) · e2e 144 — 0 failures (fixed 1 whitelist-pin test after adding `branch`).
- Pre-commit skill: _running_
  - Phase 1 (architecture): ✅ no violations (tach ✅)
  - Phase 2 (test gap): ✅ combined findings presented; 3 gaps approved
  - Phase 3 (implement tests): ✅ crash-orphan recovery (Q3), context-restore-on-exception, fallback-path branch-delete — 12 pass, lint clean
  - Phase 4 (full suite): ✅ unit 4699 · integration 461 · e2e 144 (5304 passed, 0 failures)
  - Phase 5 (code quality): ✅ ruff, C901, tach, mypy (303); file-size fixed (runner.py 658→598 via execute_run extraction)
  - Phase 6 (docs): ✅ as-built notes; C-EXEC-06 → 🟡 in matrix + topic_06
  - Phase 7 (walkthrough): ✅ C-EXEC-06_sf01_walkthrough.md
  - Phase 7.5 (Red/Blue): ✅ no critical findings (v1 limitations documented)
  - Phase 8 (commit boundary): ⏸ HITL — awaiting user commit (direct to master)
