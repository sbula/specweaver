# Implementation Plan: QA Runners Are Split, Copied, and Can Report a Skipped Tool as Clean [SF-02: Generated code is never lost]
- **Feature ID**: TECH-087
- **Sub-Feature**: SF-02 — Generated code is never lost
- **Design Document**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_07_technical_debt/TECH-087/TECH-087_sf02_implementation_plan.md
- **Status**: APPROVED

## Scope

FR-6 (a failed `git add -A` fails `worktree_commit`), FR-7 (a failed worktree commit fails the run
and keeps the worktree, naming its path and the remove command), FR-8 (one stage-and-check for the
checkpoint, the agent commit tool and `worktree_commit`). Path P-3. No command or option changes.

The user widened FR-7 at the plan gate `[agreed 2026-10-30]`: a failed strip-merge keeps the
worktree and its branch too (Q1), and a later run refuses to start while a kept worktree of the
same name is there, instead of removing it as a crash leftover (Q2).

## Research Notes

Read 2026-10-30 against `b25fa0fd`. Paths under `src/specweaver/`.

**The three stage-and-commit copies:**

| Caller | Stage | "Nothing staged" test | Its "nothing to commit" verdict | Line |
|---|---|---|---|---|
| `GitAtom._intent_checkpoint` | `add -A`, checked | `diff --staged --quiet` exit 0 | SUCCESS "No changes to commit (idempotent)." | `sandbox/git/core/atom.py:111-148` |
| `GitTool.commit` (agent) | `add -A`, checked | `diff --staged --stat` stdout empty | error "Nothing to commit (no staged changes)." | `sandbox/git/interfaces/tool.py:151-193` |
| `handle_worktree_commit` | `add -A`, **result ignored** | `diff --cached --quiet` exit 0 | SUCCESS "Nothing to commit.", `committed: False` | `sandbox/git/core/worktree_ops.py:106-135` |

`diff --cached --quiet` exits 0 (nothing staged), 1 (staged changes), other (git error, e.g. 128).
All three treat "other" as "staged" today; then `commit` fails and reports git's error.
Executors: `GitExecutor.run(command, *args, timeout=30) -> ExecutorResult` (`git/core/executor.py:85`);
`EngineGitExecutor` (the atom's, `atom.py:66`) and the tool's executor both offer it.

**The callers that tear the worktree down** (`git worktree remove --force` + `branch -D`,
`worktree_ops.py:29-77`):

| Caller | On commit failure today | Teardown | Line |
|---|---|---|---|
| sandboxed step (`use_worktree`, `enforce_worktree_isolation`) | raises `RuntimeError("worktree commit failed: …")` | always, in `finally` | `core/flow/engine/sandboxed_execution.py:98-123` |
| session reconcile (run COMPLETED) | `_reconcile_failed` → run FAILED, raises | in `finally`, unless PARKED with a store | `core/flow/engine/session.py:95-128` |
| session step snapshot (each step) | `_snapshot_step` raises → step ERROR → run FAILED | same `finally` | `core/flow/engine/step_execution.py:229-239` |

So today every failed commit ends with the uncommitted generated code deleted.

**Where a kept worktree meets the next run:** both callers start by tearing down a same-named
worktree ("left by a crash", `sandboxed_execution.py:76`, `session.py:70`). A sandboxed step names
it `.worktrees/<task_id>` with `task_id = context.run.task_id or run.run_id`, so a rerun of the same
task reuses it. A session names it `.worktrees/session-<run_id>` (`session.py:58`), unique per run;
only a resume reuses it. `.worktrees` is skipped by the code-structure scan
(`sandbox/code_structure/core/changes.py:51`).

**Existing tests that pin teardown on failure:** `test_session_reconcile.py:255`
(`test_worktree_torn_down_on_reconcile_failure`, strip-merge fails), `test_runner_sandbox.py:129`
(`test_bouncer_strip_merge_fail_resilience`), `test_session_reconcile.py:243, 312, 331` (commit and
snapshot failures fail the run; they do not check the worktree). See Q1.

**Real failures for tests** (no double): an unreadable file in the worktree (`chmod 000`) makes
`git add -A` fail with "Permission denied … adding files failed"; a `pre-commit` hook that exits 1
(`core.hooksPath`) makes `git commit` fail. Both run as a normal user; root ignores the mode bits,
so the add case checks it can still fail and skips with that reason otherwise.

## Approach (pseudocode, ordered)

**CB-1 — one stage-and-check; a failed add fails (FR-6, FR-8)** — kind `bugfix`

1. Red, unit `tests/unit/sandbox/git/core/git/test_stage_all.py`: `stage_all(executor)` →
   add fails → error with git's stderr; `diff --cached --quiet` 0 → nothing staged; 1 → staged;
   128 → error. Real git in `tmp_path` for the happy, nothing-staged and unreadable-file cases.
   Red in `test_worktree_commit.py`: add fails → FAILED naming git's error (today: "Nothing to
   commit."). Agreement test: the three callers on the same three repo states (clean, dirty,
   add fails) give their own verdicts (SUCCESS-idempotent / error / SUCCESS `committed: False`;
   all FAILED or error when the add fails).
2. Green: new `sandbox/git/core/staging.py` with `stage_all(executor) -> Staged` (a small frozen
   result: `staged: bool`, `error: str | None`). The three callers use it and keep their own
   "nothing to commit" verdicts and messages.
3. Mutant `worktree-add-ignored` (the error check in `handle_worktree_commit` removed) and
   `diff-error-reads-staged` (exit code other than 0/1 read as staged).

**CB-2 — a failed commit keeps the worktree (FR-7, P-3)** — kind `bugfix` — closes SF-02

4. Red, integration `tests/integration/core/flow/engine/test_failed_commit_keeps_worktree.py`
   (P-3), real git, no double: (a) sandboxed step whose generated file is unreadable → run
   fails, `.worktrees/<task>` still holds the file, the error names its absolute path and
   `git worktree remove --force <path>`; (b) session run, step snapshot fails the same way →
   same; (c) session reconcile commit fails (failing `pre-commit` hook) → same. Red today: the
   worktree is gone.
   (d) sandboxed step and (e) session reconcile whose strip-merge fails (a dirty real tree, as
   `test_session_reconcile.py:151` builds it) → the worktree **and its branch** stay (Q1).
   (f) a sandboxed rerun of the same task while the kept worktree is there → refuses to start,
   naming it and the remove command; the kept worktree is untouched (Q2). (g) after the user
   removed the worktree (`git worktree remove --force`), the rerun starts and drops the stale
   marker.
   The two tests that pinned teardown on a failed merge (`test_session_reconcile.py:255`,
   `test_runner_sandbox.py:129`) change to assert the worktree is kept `[agreed 2026-10-30]`.
5. Green, one module `core/flow/engine/kept_worktree.py` (the engine already drives teardown):
   - `keep(project, wt_path, reason) -> str`: writes the marker `.worktrees/<name>.kept`
     (holding the reason) and returns the message: "<reason>. The worktree is kept at <abs path>
     with the run's work. Remove it when done: git worktree remove --force <path>".
   - `refuse_if_kept(project, wt_path) -> str | None`: marker and worktree both there → the
     refusal message; marker without worktree → remove the marker, None; no marker → None.
   - Sandboxed step: `refuse_if_kept` before the crash-leftover teardown (raise like a failed
     `worktree_add`); a failed commit or merge calls `keep`, sets `kept`, and `finally` skips the
     teardown (worktree and branch) when set.
   - Session: the same check before its teardown (`_worktree_failed` with the message);
     `_snapshot_step`, the reconcile commit and the reconcile merge call `keep` and set the run's
     in-memory `kept` flag; `finally` skips the teardown when it is set, as it already does for a
     parked run. The marker is only for the next run.
   - Nothing removes a kept worktree (`[agreed 2026-10-29]`).
6. Mutants: `failed-commit-tears-down` (sandboxed `kept` check removed), `snapshot-failure-tears-
   down` (session check removed), `failed-merge-tears-down` (merge failure not kept),
   `rerun-removes-kept` (`refuse_if_kept` returns None).

## Test Plan

| Tier | Test | Proves | Red first because |
|---|---|---|---|
| unit | `test_stage_all.py` | FR-8 | no shared function |
| unit | `test_worktree_commit.py` add fails | FR-6 | reads as "Nothing to commit." |
| unit | three callers, three repo states agree | FR-8 (one verdict each, unchanged) | the add failure differs today |
| integration | `test_failed_commit_keeps_worktree.py` a–g (P-3) | FR-7 (and Q1, Q2) | worktree deleted today; a rerun deletes it |
| unit | `kept_worktree` marker cases (none, kept, stale marker) | FR-7 | module does not exist |
| all | the suite | NFR-1 | — |

Every new file: `Proves: TECH-087 FR-<n>`.

## Commit Boundaries

| CB | Holds | Done when |
|---|---|---|
| CB-1 | steps 1–3 | suite green; 2 mutants killed |
| CB-2 | steps 4–6 | suite green; 4 mutants killed; stage and stop (closes SF-02) |

## Documentation

`docs/dev_guides/pipeline_engine_guide.md` (worktree section): a failed commit keeps the worktree,
and how to remove it.

## Architecture Verification (Phase 3)

- `staging.py` sits in `sandbox/git/core`; `git/interfaces/tool.py` already imports `git/core`.
- The keep logic stays in `core/flow/engine`, which already drives the teardown. No new edge.

## Audit (Phase 2)

- **Q1 — a failed merge also deletes committed work.** A: keep the worktree and branch on a failed
  merge too; B: keep only on a failed commit. The user chose A `[agreed 2026-10-30]` (step 4 d/e,
  step 5).
- **Q2 — the next run with the same name deletes the kept worktree.** A: the next run refuses while
  a kept worktree is there, with a marker telling "kept" from "crash leftover"; B: a new name. The
  user chose A `[agreed 2026-10-30]` (step 4 f/g, step 5).

## Consistency (Phase 5)

- Coverage: FR-6 (step 1–2, `worktree-add-ignored`), FR-7 (steps 4–6, a–g), FR-8 (steps 1–2, the
  agreement test, `diff-error-reads-staged`). NFR-1: suite; NFR-2: no new edge; NFR-3: 6 mutants.
  Risk "kept worktrees pile up": only on a failed commit or merge; each blocks its own rerun and
  names the remove command.
- Red/Blue, 2 cycles:
  - R1 (HIGH) keeping the branch after a failed merge leaves the real repo mid-merge? Blue: the
    strip-merge already aborts a conflicting merge (`test_session_reconcile.py:151` asserts no
    `UU`); keeping the worktree changes nothing in the real repo.
  - R2 (MEDIUM) the marker file sits in `.worktrees/`, beside an untracked worktree that is
    already there; it adds no new path to the real repo's status outside that folder.
  - R3 (MEDIUM) the user removes the worktree with plain `rm -rf` instead of the command. Blue:
    the marker without a worktree is dropped and the crash-leftover teardown runs `worktree prune`
    and removes the branch, as today.
  - R4 (MEDIUM) writing the marker can fail (disk full). Blue: the run still fails and the
    worktree is still kept (teardown skipped by the in-memory flag); the message says the marker
    could not be written, so a rerun may remove it.
  - R5 (LOW) root ignores `chmod 000`. Blue: the test checks the add really fails and skips with
    that reason otherwise; the hook-based commit failure covers the same path as any user.
  - Cycle 2: challenged R4 (session `finally` reads the marker, not a flag). Fixed in step 5:
    session also keeps an in-memory flag; the marker is for the next run only.
- All decisions are resolved and documented inline in the plan.
