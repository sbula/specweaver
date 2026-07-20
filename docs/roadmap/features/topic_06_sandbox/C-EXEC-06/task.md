# Task List — C-EXEC-06 SF-02: Commit-Before-Reconcile + Authorized Strip-Merge

- **Impl Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf02_implementation_plan.md
- **FRs**: FR-3 (worktree_commit), FR-4 (authorized strip-merge + surface failures)
- **Commit boundary**: single **CB-1**. Foundation-first (primitive → reconcile → dirty-tree hardening).
- **(SF-01 task record preserved in git history + walkthrough.)**

## Tasks

- [x] **T1 — `worktree_commit` primitive** (FR-3, Q3)
  - src: `sandbox/git/core/worktree_ops.py` (`handle_worktree_commit`) + `atom.py` (`_intent_worktree_commit`).
  - Behavior: bind `EngineGitExecutor(cwd=worktree)`; `git add -A`; if `git diff --cached --quiet` → SUCCESS "nothing to commit" (skip empty commit); else `git commit -m "chore(sandbox): session snapshot"`; surface a commit failure as FAILED.
  - test: `tests/unit/sandbox/git/core/git/test_worktree_commit.py` — dirty→commit; clean→skip; commit-fail→FAILED; unknown-intent still lists it.

- [x] **T2 — Reconcile orchestration in `execute_run`** (FR-3, FR-4, Q1)
  - src: `runner_utils.py` — at the SF-02 seam, ONLY when `run.status == COMPLETED`: `worktree_commit` → `strip_merge(branch, allowed_paths=original.allowed_paths)`; raise `RuntimeError` on either FAILED (surface, never swallow). Skip reconcile on failed/parked runs.
  - test: `tests/integration/core/flow/engine/test_session_reconcile.py` (real git) — [Happy] session generates `src/foo.py` (in allowed_paths) → committed to real repo after run; [Hostile] also writes `secret.py` (not allowed) → absent from real repo; [Degradation] a failed run (loop not COMPLETED) → no reconcile, real repo unmutated; [Degradation] strip_merge FAILED → RuntimeError surfaced.

- [x] **T3 — Dirty-real-tree hardening** (FR-4, Q2/Q5)
  - src: `runner_utils.py` (reconcile) — detect a dirty real working tree that the merge would clobber → fail loud with an actionable "commit/stash first" error; on any strip_merge failure, `git merge --abort` so the real repo is left clean.
  - test: integration — real repo has an uncommitted change to a path the reconcile touches → RuntimeError (clear message), merge aborted, real repo clean, the user's uncommitted change intact.

- [x] **T4 — Full suite + pre-commit gate (CB-1)**
  - Full unit/integration/e2e; fix any regression project-wide. Run pre-commit skill. HITL commit stop (direct to master).

## Adversarial Test Matrix (per task — 4 buckets)
| Task | Happy | Boundary/Edge | Graceful Degradation | Hostile/Wrong Input |
|------|-------|---------------|----------------------|---------------------|
| T1 | dirty worktree → commit | clean → skip (nothing to commit) | commit fails → FAILED surfaced | missing `path` → FAILED |
| T2 | allowed file lands in real repo | empty allowed_paths → nothing merged | failed run → no reconcile; strip_merge FAILED → raise | non-allowed / README / docs stripped |
| T3 | clean real tree → reconcile proceeds | non-conflicting dirty file left untouched | dirty-clobber → fail loud + merge-abort + repo clean | traversal allow-list entry doesn't authorize out-of-tree |

## Progress
- T1–T3 complete (TDD, lint clean). Fixed a strip_merge new-file gap (stripped new files now deleted from disk) + merge-failure surfacing. mypy + tach ✅.
- Full suite: unit 4703 · integration 465 (+4 reconcile) · e2e 144 (5312 passed, 0 failures).
- Pre-commit skill: _running_
  - Phase 1 (architecture): ✅ no violations (tach ✅)
  - Phase 2 (test gap): ✅ combined findings; user pushed on corner/teardown cases → 7 gaps approved
  - Phase 3 (implement tests): ✅ G1–G7 (empty-allowed, hard-block, commit-fail-raise, graceful-teardown-on-failure, all-stripped, empty-session, doc_updates-survives). Found+fixed a latent noise-commit bug (all-stripped created an empty merge commit). 66 pass, lint+mypy clean.
  - Phase 4 (full suite): ✅ unit 4703 · integration 472 · e2e 144 (5319 passed, 0 failures)
  - Phase 5 (code quality): ✅ ruff, C901, tach, mypy (303), file-size all clean
  - Phase 6 (docs): ✅ SF-02 as-built notes (C-EXEC-06 stays 🟡)
  - Phase 7 (walkthrough): ✅ C-EXEC-06_sf02_walkthrough.md
  - Phase 7.5 (Red/Blue): ✅ no critical findings (SF-03/production notes recorded)
  - Phase 8 (commit boundary): ✅ committed to master (CB-1). Re-verified post-reboot: 70 SF-02 tests pass, ruff/mypy/tach clean.
