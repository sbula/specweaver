# C-EXEC-06 SF-02 — Commit-Before-Reconcile + Authorized Strip-Merge

**Status**: APPROVED — approved by Steve Bula on 2026-07-19. Audit Q1–Q5 all resolved to option
**(a)**. Implemented 2026-07-19. · **FRs owned**: FR-3, FR-4 · **Depends on**: SF-01 (committed) ·
Design: [C-EXEC-06_design.md](C-EXEC-06_design.md) §Sub-features → SF-02

## Goal

The **reconcile** — the DAL-C authorization gate. At span end, before teardown: commit the session
worktree's changes onto the session branch (new `worktree_commit` primitive), then run a **single**
`strip_merge` that writes back **only** paths in `allowed_paths` (+ the existing `README.md`/`docs/`
hard-block). **Surface** every failure; never swallow it.

Fixes `TECH-012` Gap 1 (nothing committed), Gap 2 mechanics (allow-list actually applied), and the
swallowed-failure defect.

## Where it plugs in

| Fact | Where |
|---|---|
| Gap 1 today: `worktree_sync` runs `git rebase main`, refuses on the dirty tree, returns FAILED; per-step `execute_in_sandbox` **discards** that result, and only warns on strip_merge | `git/core/atom.py:427-475`; `runner_utils.py:195`, `:205-206` |
| Gap 2 today: `getattr(context, "allowed_paths", [])` is always `[]` because `RunContext` had no such field, so every file is stripped | `runner_utils.py:202`, `handlers/base.py`, `git/core/worktree_ops.py:107` |
| The seam exists: `runner_utils.execute_run` (SF-01) has `# SF-02: commit-before-reconcile + authorized strip-merge go HERE (before teardown)` between the loop result and the `finally` teardown. `atom = GitAtom(cwd=original.project_path)` is in scope, bound to the REAL repo; `original.allowed_paths` is the SF-01 field. | `runner_utils.execute_run` |
| `strip_merge` already authorizes: `git merge --no-commit --no-ff <branch> -X ours` → `git diff --name-only --cached` → strip any file that is `README.md`, under `docs/`, or **not in `allowed_paths`** (`reset HEAD <f>` + `checkout -- <f>`) → commit survivors as `chore(sandbox): ...`. It needs the branch to already carry commits — hence the new commit step. Empty cached diff → `SUCCESS "No changes to strip and merge"` (`:113-119`). Runs against the real repo via `self._executor` (cwd = `project_path`). It already `--abort`s on a diff-read error (`:106`). | `worktree_ops.handle_strip_merge:88-140` |
| `worktree_sync` is NOT used by per-run (it is Gap 1). Its executor pattern is reused: `EngineGitExecutor(cwd=worktree_path, whitelist=set(self._ENGINE_WHITELIST))` | `atom.py:461` |
| Intent dispatch is dynamic: `getattr(self, f"_intent_{intent}")`; `_known_intents` auto-discovers `_intent_worktree_commit`. `commit`/`add`/`diff` are already whitelisted (SF-01 added `branch`). | `atom.py:95` |

Worktrees share the object store, so the commit on the `sf-` branch is visible to the real-repo
`strip_merge` — no push or fetch needed. External deps: git (existing). No new tool, no new module.

## Changes

1. **`worktree_commit` primitive** (FR-3) · `sandbox/git/core/atom.py` + `worktree_ops.py` —
   `_intent_worktree_commit(context)` dispatches to `worktree_ops.handle_worktree_commit`:
   - input: `path` (worktree rel path); builds `EngineGitExecutor(cwd=cwd/path, whitelist=...)`.
   - `git add -A`; if `git diff --cached --quiet` shows **no** staged changes → SUCCESS
     "nothing to commit" (Q3). Else `git commit -m "chore(sandbox): session snapshot"`.
   - returns SUCCESS/FAILED with the commit result surfaced.
2. **Reconcile in `execute_run`** (FR-3, FR-4) · `runner_utils.py` — at the seam, **only when
   `run.status == COMPLETED`** (Q1), after the park-guard:
   1. `commit_res = atom.run({"intent":"worktree_commit","path":wt_path})` → FAILED raises `RuntimeError`.
   2. `merge_res = atom.run({"intent":"strip_merge","branch":branch,"allowed_paths":original.allowed_paths})`
      → FAILED raises `RuntimeError`.
   A failed or parked run **skips the reconcile**; teardown discards the worktree, so unvalidated code
   never lands.

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/sandbox/git/core/worktree_ops.py` | `handle_worktree_commit` | FR-3 |
| `src/specweaver/sandbox/git/core/atom.py` | `_intent_worktree_commit` dispatch | FR-3 |
| `src/specweaver/core/flow/engine/runner_utils.py` | reconcile in `execute_run` (commit → strip_merge, surface failures, COMPLETED-only) | FR-3, FR-4 |
| `tests/...` | see Tests | all |

> [!CAUTION]
> **Dirty real tree (Q2):** do not rely on git's cryptic merge error. Detect the clobber case, raise
> an actionable "commit/stash first" message, and always `merge --abort` (Q5) so the real repo is
> left clean. A non-conflicting dirty file is left untouched by git, which is fine.

## Tests

DAL-C rigor on the authorization gate.

| Tier | Bucket | Case |
|---|---|---|
| Unit — `handle_worktree_commit` | Happy | dirty worktree → `add -A` + commit |
| | Boundary | clean worktree → SUCCESS "nothing to commit", no commit |
| | Degradation | commit fails → FAILED surfaced |
| Unit/Integration — `strip_merge` authorization | Happy | a file in `allowed_paths` survives and is committed to real HEAD |
| | Hostile | a file **not** in `allowed_paths` is stripped |
| | Hostile | `README.md` / `docs/x` hard-blocked even if in `allowed_paths` |
| | Boundary | `allowed_paths=[]` → **nothing** merged back (never everything) |
| | Hostile | a `../traversal` allow-list entry does not authorize an out-of-tree write |
| Integration — reconcile, real git | Happy | session run generates `src/foo.py` (allowed) → committed in the real repo |
| | Hostile | it also writes `secret.py` (not allowed) → **absent** from the real repo |
| | Degradation | run not COMPLETED → **no reconcile**, real repo unmutated |
| | Degradation | dirty real working tree → **fail loud** (Q2), real uncommitted changes untouched |

## Decisions (audit)

| # | Question | Options | Chosen | Severity |
|---|----------|---------|--------|----------|
| Q1 | Reconcile on COMPLETED only, or always (incl. failed/parked)? | (a) COMPLETED only; (b) always | **(a)** — never write back unvalidated or broken code; a failed autonomous run leaves the real repo untouched | **HIGH** |
| Q2 | Dirty real working tree at merge time? | (a) **fail loud** with a "commit/stash first" error; (b) auto-stash + restore; (c) merge anyway | **(a)** — NFR-6; never silently touch the user's uncommitted work. Auto-stash is a bigger, riskier feature for a later SF | **HIGH** |
| Q3 | `worktree_commit` with nothing changed? | (a) skip (SUCCESS "nothing to commit"); (b) `--allow-empty` | **(a)** — no noise; `strip_merge` then no-ops cleanly | MEDIUM |
| Q4 | The reconcile writes a `chore(sandbox)` **commit** to the user's real branch — or leave it staged? | (a) commit (existing `strip_merge` behavior); (b) leave staged | **(a)** — authorized code lands as a commit, consistent with `D-EXEC-02`. Revisit as a config option later | MEDIUM |
| Q5 | Abort the merge before raising on a `strip_merge` failure (e.g. conflict)? | (a) `merge --abort` then raise; (b) raise leaving the half-merge | **(a)** — leave the real repo clean | MEDIUM |

Architecture check: `worktree_commit` is a new git-orchestration intent in `sandbox/git.core`, sibling
to `worktree_sync`/`strip_merge` — the missing primitive, since `worktree_sync` rebases and does not
commit. `strip_merge` is reused verbatim for authorization (no parallel merge logic). The
`core.flow.engine → sandbox.git` edge already exists. No new cross-layer import;
`tach`/`ruff`/`mypy --strict` must stay green. Coverage: FR-3, FR-4; NFR-4 (adversarial allow-list
tests), NFR-6 (Q2/Q5).

## As built (2026-07-19)

| Where | What |
|---|---|
| `worktree_ops.py` | new `handle_worktree_commit`; extracted `_strip_forbidden_files`; `handle_strip_merge` gained a `cwd` param, a **merge-failure guard** (dirty real tree → `--abort` + FAILED, Q2/Q5) and a **post-strip empty check** |
| `atom.py` | `_intent_worktree_commit`; `_intent_strip_merge` passes `self._cwd` |
| `runner_utils.execute_run` | reconcile at the seam: COMPLETED-only, `worktree_commit` → `strip_merge`, raise on either FAILED |

Two real gaps the tests exposed, both fixed:
- **Stripped NEW files stayed on disk** (untracked): `checkout -- <file>` cannot remove a file absent
  from HEAD. They are now deleted, so a disallowed file never reaches the real working tree — the core
  DAL-C property.
- **All-stripped made an empty merge commit**: `git commit` completes an in-progress merge even with no
  changes, so the old "all stripped → abort" branch was dead. A post-strip `diff --cached --quiet` now
  aborts cleanly. 2 existing mocked strip_merge unit tests updated for the new git call.

No new whitelist entries (SF-01 added `git branch`). Commit boundary: CB-1. Next: SF-03.
