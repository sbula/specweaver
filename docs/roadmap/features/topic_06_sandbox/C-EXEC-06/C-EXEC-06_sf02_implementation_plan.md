# Implementation Plan: Per-Run (Session) Worktree Isolation — SF-02: Commit-Before-Reconcile + Authorized Strip-Merge

- **Feature ID**: C-EXEC-06
- **Sub-Feature**: SF-02 — Commit-Before-Reconcile + Authorized Strip-Merge
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf02_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-19. Audit Q1–Q5 all resolved to option **(a)**.

## Scope (from the Design Document)
The **reconcile** — the DAL-C authorization gate. Add a `worktree_commit` GitAtom primitive; at span end
(before teardown) commit the session worktree's accumulated changes onto the session branch, then run a
**single** `strip_merge` that writes back to the real repo **only** paths in `allowed_paths` (+ the existing
`README.md`/`docs/` hard-block); **surface** (never swallow) any failure. Fixes `TECH-012` Gap 1
(nothing committed) + Gap 2 mechanics (allow-list actually applied) + the swallowed-failure defect.
**FRs owned: FR-3, FR-4.** Depends on SF-01 (committed).

## Research Notes (Phase 0)

1. **The insertion point already exists** — `runner_utils.execute_run` (SF-01) has the marked seam:
   `# SF-02: commit-before-reconcile + authorized strip-merge go HERE (before teardown)`, between the loop
   result and the `finally` teardown. `atom = GitAtom(cwd=original.project_path)` is already in scope (bound
   to the REAL repo). `original.allowed_paths` is the SF-01 field.
2. **`strip_merge` already does the authorization** (`worktree_ops.handle_strip_merge:88-140`): `git merge
   --no-commit --no-ff <branch> -X ours` → `git diff --name-only --cached` → strip any file that is
   `README.md`, under `docs/`, or **not in `allowed_paths`** (`reset HEAD <f>` + `checkout -- <f>`) → commit
   survivors as `chore(sandbox): ...`. **Requires the branch to already carry committed changes** — hence
   the new commit step. It also short-circuits `SUCCESS "No changes to strip and merge"` when the cached
   diff is empty (`:113-119`). Runs against the real repo via `self._executor` (cwd = `project_path`).
3. **`worktree_sync` is NOT used** by per-run — it's the broken `git rebase` (Gap 1). Per-run replaces it
   with `worktree_commit` (stage+commit inside the worktree) → `strip_merge`. The commit-in-worktree pattern
   already exists: `worktree_sync` builds `EngineGitExecutor(cwd=worktree_path, whitelist=set(self._ENGINE_WHITELIST))`
   (`atom.py:461`) — the new `_intent_worktree_commit` uses the same bound executor.
4. **Intent dispatch is dynamic** (`atom.py:95`, `getattr(self, f"_intent_{intent}")`) — adding
   `_intent_worktree_commit` is enough; `_known_intents` auto-discovers it. `commit`/`add`/`diff` are already
   whitelisted (SF-01 added `branch`).
5. **Failure-surfacing gap to fix (FR-4/NFR-6):** the per-step `execute_in_sandbox` swallows the sync FAILED
   result (`runner_utils.py:195`) and only warns on strip_merge (`:205-206`). SF-02's reconcile in
   `execute_run` MUST instead raise on a failed commit/merge so a broken reconcile never returns green.

### External deps: git (existing). No new tool.

## Implementation Approach
> Pseudocode / ordered steps only.

### Change 1 — `worktree_commit` primitive (FR-3) · `sandbox/git/core/atom.py` (+ `worktree_ops.py`)
Add `_intent_worktree_commit(context)` (thin dispatch → `worktree_ops.handle_worktree_commit`):
- inputs: `path` (worktree rel path).
- build `EngineGitExecutor(cwd=cwd/path, whitelist=...)` (as `worktree_sync` does).
- `git add -A`; if `git diff --cached --quiet` reports **no** staged changes → return SUCCESS "nothing to
  commit" (skip empty commit, Q3). Else `git commit -m "chore(sandbox): session snapshot"`.
- return SUCCESS/FAILED with the commit result surfaced.

### Change 2 — reconcile orchestration in `execute_run` (FR-3, FR-4) · `runner_utils.py`
At the marked seam, **only when the run completed successfully** (Q1), in order:
1. `commit_res = atom.run({"intent":"worktree_commit","path":wt_path})` → on FAILED raise `RuntimeError`.
2. `merge_res = atom.run({"intent":"strip_merge","branch":branch,"allowed_paths":original.allowed_paths})`
   → on FAILED raise `RuntimeError` (surface — never swallow).
On a non-`COMPLETED` run (failure/park), **skip reconcile** — teardown discards the worktree (don't write
back unvalidated/broken code). Dirty-real-repo guard: see Q2.

### Files to modify
| File | Change | FR |
|------|--------|-----|
| `src/specweaver/sandbox/git/core/worktree_ops.py` | `handle_worktree_commit` | FR-3 |
| `src/specweaver/sandbox/git/core/atom.py` | `_intent_worktree_commit` dispatch | FR-3 |
| `src/specweaver/core/flow/engine/runner_utils.py` | reconcile in `execute_run` (commit → strip_merge, surface failures, COMPLETED-only) | FR-3, FR-4 |
| `tests/...` | see Test Plan | all |

No new module.

## Test Plan (4 Adversarial Buckets — DAL-C rigor on the authorization gate)

**Unit — `handle_worktree_commit`:** [Happy] dirty worktree → `add -A` + commit; [Boundary] clean worktree
→ SUCCESS "nothing to commit", no commit; [Degradation] commit fails → FAILED surfaced.

**Unit/Integration — `strip_merge` authorization (the security core):** [Happy] a file in `allowed_paths`
survives + is committed to real HEAD; [Hostile] a file **not** in `allowed_paths` is stripped (not written
back); [Hostile] `README.md` / `docs/x` hard-blocked even if in `allowed_paths`; [Boundary] `allowed_paths=[]`
→ **nothing** merged back (write-back-nothing, never everything); [Hostile] a `../traversal` allow-list entry
does not authorize an out-of-tree write.

**Integration — reconcile end-to-end (real git):** [Happy] a session run generates `src/foo.py` (in
`allowed_paths`) → after the run the file **IS** committed in the real repo; [Hostile] it also writes
`secret.py` (not allowed) → **absent** from the real repo; [Degradation] a run that fails (loop not
COMPLETED) → **no reconcile**, real repo unmutated; [Degradation] dirty real working tree → **fail loud**
(Q2), real uncommitted changes untouched.

## Audit (Phase 2) — open questions for HITL
| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | Reconcile on **COMPLETED only**, or always (incl. failed/parked runs)? | (a) COMPLETED only [rec]; (b) always. | **(a)** — never write back unvalidated/broken generated code; a failed autonomous run should leave the real repo untouched. | **HIGH** |
| Q2 | **Dirty real working tree** when the reconcile merges — fail loud vs auto-stash vs merge anyway? | (a) **fail loud** with an actionable "commit/stash first" error [rec]; (b) auto-stash + restore; (c) merge anyway. | **(a)** — NFR-6; never silently touch the user's uncommitted work. Auto-stash is a bigger, riskier feature for a later SF. | **HIGH** |
| Q3 | `worktree_commit` when nothing changed → empty commit vs skip? | (a) skip (SUCCESS "nothing to commit") [rec]; (b) `--allow-empty`. | **(a)** — no noise; `strip_merge` then finds an empty diff and no-ops cleanly. | MEDIUM |
| Q4 | The reconcile writes a `chore(sandbox)` **commit** to the user's real branch — acceptable, or leave staged/unstaged? | (a) commit (existing `strip_merge` behavior) [rec]; (b) leave staged for the user to commit. | **(a)** — "generated code lands via authorized reconcile" = a commit; consistent with `D-EXEC-02`. Revisit as a config option later. | MEDIUM |
| Q5 | Should `strip_merge` failure (e.g. merge conflict) **abort the merge** before raising, to leave the real repo clean? | (a) `merge --abort` then raise [rec]; (b) raise leaving the half-merge. | **(a)** — leave the real repo in a clean state on failure (it already `--abort`s on a diff-read error, `:106`). | MEDIUM |

## Architecture Verification (Phase 3)
- **Mechanism × constraint:** `worktree_ops.py`/`atom.py` — a new git-orchestration intent in `sandbox/git.core`
  (the correct layer; sibling to `worktree_sync`/`strip_merge`). `runner_utils.py` — reconcile via existing
  `GitAtom` surfaces; the `core.flow.engine → sandbox.git` edge is pre-existing. **No new cross-layer import;
  no boundary violation.** `tach`/`ruff`/`mypy --strict` must stay green.
- **Zoom-out/duplication:** `worktree_commit` is the missing primitive (there is no commit-in-worktree op
  today — `worktree_sync` rebases, doesn't commit); it reuses the `EngineGitExecutor(cwd=worktree)` pattern.
  Reuses `strip_merge` verbatim for authorization (no parallel merge logic).
- **Acyclic imports / stability:** no new edge; additive. **Verdict:** no CRITICAL violation.

## Consistency + Red/Blue (Phase 5)
- **FR/NFR coverage:** FR-3 (worktree_commit), FR-4 (authorized strip-merge + surface failures); NFR-4
  (adversarial allow-list tests), NFR-6 (fail-loud Q2/Q5).
- **Red/Blue notes merged:** (1) worktrees share the object store → the session commit on `sf-branch` is
  visible to the real-repo `strip_merge` (no push/fetch needed); (2) a dirty real tree that the merge would
  clobber makes `git merge` refuse — SF-02 catches it, `git merge --abort`s, and raises a clear "commit/stash
  first" error (a non-conflicting dirty file is left untouched by git, which is fine); (3) reconcile is
  ordered AFTER the park-guard and gated on `run.status == COMPLETED`.

> [!CAUTION]
> **Dirty-real-tree clarity (Q2):** don't rely solely on git's cryptic merge error — detect the clobber
> case and raise an actionable message; always `merge --abort` (Q5) so the real repo is left clean on failure.

## Implementation Notes (as-built, 2026-07-19)

Delivered the reconcile. Source: `worktree_ops.py` (new `handle_worktree_commit`; extracted
`_strip_forbidden_files` which now **deletes** stripped *new* files from disk, not just unstages them;
`handle_strip_merge` gained a `cwd` param, a **merge-failure guard** (dirty real tree → `--abort` + FAILED,
Q2/Q5), and a **post-strip empty check** so an all-stripped reconcile aborts cleanly instead of committing an
empty merge), `atom.py` (`_intent_worktree_commit`; `_intent_strip_merge` passes `self._cwd`), and
`runner_utils.execute_run` (reconcile at the seam: COMPLETED-only, `worktree_commit`→`strip_merge`, raise on
either FAILED — never swallow).

Found & fixed during dev (both real gaps the tests exposed):
- **Stripped NEW files were left on disk** (untracked) — `checkout -- <file>` can't remove a file absent from
  HEAD. Now deleted, so a disallowed file never reaches the real working tree (the core DAL-C property).
- **All-stripped created an empty noise merge commit** — `git commit` completes an in-progress merge even
  with no changes, so the old "all stripped → abort" branch was dead. Now a post-strip `diff --cached
  --quiet` aborts cleanly. Updated 2 existing mocked strip_merge unit tests for the new git call.
- Added `git branch` (SF-01) and no new whitelist entries here.

Decisions confirmed: Q1 (COMPLETED-only reconcile), Q2/Q5 (dirty tree → fail-loud + merge-abort, repo left
clean), Q3 (skip empty commit), Q4 (`chore(sandbox)` commit is how authorized code lands).

## Session Handoff
**Current status**: Implemented; pre-commit gate in progress (2026-07-19). Ready for commit boundary CB-1.
**Next step**: SF-03 (composition-root policy + `allowed_paths` population + the multi-step generated-file e2e proof).
**Next step**: After approval, `/dev` for SF-02. Then SF-03 (composition-root policy + verifiable proof).
