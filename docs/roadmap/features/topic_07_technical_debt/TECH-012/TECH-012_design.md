# Design: Multi-Step Git-Worktree Isolation is Broken (Reconcile Never Commits; Crashes on Step 2)

- **Feature ID**: TECH-012
- **Epic**: Topic 07 (Technical Debt)
- **Status**: ✅ RESOLVED (2026-07-21) by building `C-EXEC-06` (per-run/session worktree isolation,
  SF-01/02/03 committed) + its integration `INT-US-09-SF05` (delivered by `C-EXEC-06` SF-03). Multi-step
  untrusted spans now run in one worktree with a single authorized reconcile. The legacy per-step model stays
  single-step-only (multi-step per-step isolation = documented limitation; use session mode). Proof:
  `tests/e2e/sandbox/test_c_exec_06_session_isolation_e2e.py`.
- **Origin**: Found during `INT-US-03 SF-03`'s implementation-plan Phase 0 spike (2026-07-19). The spike
  proved `sw implement` cannot run its multi-step loop under US-9 worktree isolation.
- **Severity**: HIGH — `INT-US-09` Core is marked 🟢 Done but is non-functional for any **multi-step**
  isolated pipeline; the defect is masked because every isolation test drives a **single** step over
  **pre-committed** files.

## Problem Statement

INT-US-09's per-step isolation (`execute_in_sandbox`, `src/specweaver/core/flow/engine/runner_utils.py:151-221`)
wraps **each** pipeline step in `worktree_add → run step in worktree → worktree_sync → strip_merge →
worktree_teardown`. This works for a single untrusted step over already-committed code, but has three
independent defects that break any multi-step isolated pipeline (e.g. generate → test):

1. **Reconcile never commits the step's new file (Gap 1).** Handlers never `git commit`. `worktree_sync`
   (`sandbox/git/core/atom.py:427-475`) runs `git rebase main`, which refuses on the dirty worktree tree and
   aborts — and the FAILED result is **discarded** (`runner_utils.py:195`). `strip_merge`'s `git merge sf-*`
   is then a no-op ("nothing to merge"), so the file is lost at teardown.
2. **`allowed_paths` does not exist (Gap 2).** `execute_in_sandbox` reads
   `getattr(context, "allowed_paths", [])` (`runner_utils.py:202`), but `RunContext`
   (`core/flow/handlers/base.py`) has **no such field** and nothing in `src/` sets it → always `[]`. In
   `strip_merge` (`sandbox/git/core/worktree_ops.py:107`) `file not in allowed_paths` is then true for every
   file → everything is stripped, nothing is reconciled back.
3. **Multi-step isolation crashes at step 2 (Gap 3).** The worktree branch/path are named from the constant
   run id (`sf-{pipeline}-{task_id}`, `.worktrees/{task_id}`, `runner_utils.py:163-166`); teardown removes
   the worktree but **not** the branch (`tests/integration/sandbox/test_worktree_atoms.py:99`). So the 2nd
   isolated step's `git worktree add -b <existing-branch>` fails "branch already exists" → fail-closed
   `RuntimeError` (`runner_utils.py:170-178`).

**Test-coverage gap:** `tests/e2e/sandbox/test_int_us_09_isolation_e2e.py` uses only single-step pipelines
and commits its probe files up front (`:64-65`, `:134-135`). No test drives >1 isolated step or a
freshly-generated (uncommitted) file across steps — which is why the 🟢 Done was granted on incomplete
coverage.

## Goal

Make git-worktree isolation correct and tested for **multi-step** pipelines that generate and then execute
code, without silently swallowing reconcile failures. Restore honesty to INT-US-09's "Done" status.

## Relationship to `C-EXEC-06` / `INT-US-09-SF05`

The forward-looking fix — a **per-run (session) worktree mode** (one worktree for a whole untrusted span,
single end-of-run reconcile) — is the new **capability `C-EXEC-06`** (the build), integrated into the US-9
policy by the **`INT-US-09-SF05`** sub-story (the wiring). Per-run mode structurally sidesteps Gaps 1 & 3 and
needs Gap 2 (`allowed_paths`) only once. **This TECH-012 ticket tracks the underlying defect + coverage
gap**; it is expected to be **resolved by building `C-EXEC-06`**. If the per-*step* model must ALSO support
multi-step in future, Gaps 1/3 need a direct fix here too.

## Candidate Approaches (not yet designed)
1. **Resolve via `INT-US-09-SF05` (per-run worktree)** — recommended; the implement loop's real need.
2. **Fix the per-step model directly** — commit the worktree tree before sync (Gap 1); add + populate
   `RunContext.allowed_paths` (Gap 2); make the branch/worktree unique per step or delete the branch at
   teardown (Gap 3). Pollutes history with a commit per step.
3. **At minimum, stop swallowing the `worktree_sync` failure** — surface it instead of returning green over
   a broken reconcile (a cheap correctness guardrail regardless of the chosen model).

## Non-Goals (proposed, pending design)
- Container isolation (that's `INT-US-09-SF01`).
- Reworking the `strip_merge` allow-list semantics beyond adding the missing `allowed_paths` plumbing.

## Next Step
Run `specweaver-design TECH-012` **or** fold the fix into `INT-US-09-SF05`'s design (recommended). Add a
multi-step, freshly-generated-file e2e to the isolation proof either way.
