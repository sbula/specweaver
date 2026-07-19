# Implementation Plan: Per-Run (Session) Worktree Isolation — SF-01: Session Worktree Lifecycle + Context Rebind

- **Feature ID**: C-EXEC-06
- **Sub-Feature**: SF-01 — Session Worktree Lifecycle + Context Rebind
- **Design Document**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_06_sandbox/C-EXEC-06/C-EXEC-06_sf01_implementation_plan.md
- **Status**: APPROVED — approved by Steve Bula on 2026-07-19. Audit Q1–Q4 all resolved to option **(a)**.

## Scope (from the Design Document)
The new **run-level** isolation lifecycle: create ONE ephemeral worktree (unique branch/path) at the start
of a session-isolated run, rebind the session workspace root to it for **all** steps, tear down **once**
(worktree **and** branch) in a guaranteed `finally`, fail-closed on creation failure, and add the
`RunContext.allowed_paths` field (unpopulated) + a `session_isolation` trigger. **No reconcile yet** —
that is SF-02, so under SF-01 the worktree's changes are simply discarded at teardown (proving isolation:
the real source root is unmutated). **FRs owned: FR-1, FR-2, FR-5 (field only), FR-6, FR-7 (park-guard).**
Depends on: none.

## Research Notes (Phase 0)

1. **Wrap points** — `run()` (`runner.py:130-134`) and `resume()` (`:176-181`) both do
   `try: async with cqrs_context(): return await self._execute_loop(run) finally: save_handover; flush`.
   The session lifecycle wraps `_execute_loop` (create worktree → run loop rebound → teardown in finally).
2. **`_execute_loop` uses `self._context` directly** — per-step dispatch at `runner.py:321-327`:
   `if resolve_should_isolate(step_def, self._context): result = execute_in_sandbox(...) else
   handler.execute(step_def, self._context)`. To rebind for the session, the wrapper must make the loop use
   an isolated context (temporarily set `self._context = isolated_context` for the loop, restore in
   finally — or thread a context param; the dev picks, tests assert behavior).
3. **`RunContext`** (`handlers/base.py:30-74`) has `project_path`, `output_dir` (`:55`), `enforce_isolation`
   (`:56`, per-step policy), `execution_root` (`:57`). **No `allowed_paths`, no session flag.** `db` is a
   live `Database` object (`:65`), not path-derived — so rebinding `project_path` does NOT re-open the DB.
4. **Per-step isolation reference** — `execute_in_sandbox` (`runner_utils.py:151-221`): `worktree_add` →
   `copy.copy(context)` + rebind `output_dir`/`execution_root` to `wt_path` → `setup_sandbox_caches` →
   handler → sync/strip_merge → `worktree_teardown` (finally). SF-01 builds the **per-run** analog (once
   around the whole loop) reusing `setup_sandbox_caches` (symlinks `.specweaver`/caches into the worktree).
5. **GitAtom intents** (`git/core/atom.py`): `worktree_add` (`:385-415`, `git worktree add -b <branch>
   <path> HEAD`), `worktree_teardown` (`:417-425` → `worktree_ops.handle_worktree_teardown:20-64`, removes
   the worktree but **NOT the branch**). **No branch-delete intent exists** → SF-01 must add branch
   deletion (extend `handle_worktree_teardown` to `git branch -D <branch>` when a `branch` key is passed —
   backward-compatible: per-step teardown passes no branch → unchanged).
6. **Naming fixes Gap 3 structurally** — session mode creates the worktree **once per run**, so a
   `run_id`-based unique name (`.worktrees/session-{run_id}`, branch `sf-session-{run_id}`) has no per-step
   collision. Cross-run uniqueness holds (distinct `run_id`). Crash-orphan on a same-`run_id` retry is the
   design's idempotency risk (see Audit Q3).
7. **Composition root** — `enforce_isolation` is set from `sandbox.enforce_worktree_isolation`
   (`flow/interfaces/cli.py:270-272`); SF-03 will populate `session_isolation` similarly. SF-01 tests set
   `context.session_isolation` directly.

### External deps: git (existing). No new tool.

## Implementation Approach
> Pseudocode / ordered steps only.

### Change 1 — `RunContext` fields (FR-5 field) · `handlers/base.py`
Add `allowed_paths: list[str] = Field(default_factory=list)` and
`session_isolation: bool = False` (the per-run trigger, independent of the per-step `enforce_isolation`).

### Change 2 — Branch-aware teardown (FR-1) · `git/core/worktree_ops.py`
Extend `handle_worktree_teardown`: after removing the worktree, if `context.get("branch")` is set, run
`git branch -D <branch>` (best-effort, logged). Backward-compatible (no `branch` → today's behavior).

### Change 3 — Session lifecycle wrapper (FR-1, FR-2, FR-6, FR-7) · `runner.py` (+ helper in `runner_utils.py`)
A wrapper the `run()`/`resume()` try-blocks call instead of `_execute_loop` directly, e.g.
`_execute_maybe_session(run)`:
1. If `not context.session_isolation` → `return await _execute_loop(run)` (unchanged path).
2. Else (ordered):
   a. `worktree_add` at `.worktrees/session-{run_id}`, branch `sf-session-{run_id}`. **Fail-closed:** on
      failure raise an actionable `RuntimeError` (non-git project / stale worktree) — do NOT run the loop
      (FR-6).
   b. Build `isolated_context = copy.copy(context)`: `project_path = worktree`, `execution_root =
      worktree`, `output_dir = None` (so generate writes to `worktree/src`, run_tests cwd = worktree),
      `enforce_isolation = False` (so **per-step** `execute_in_sandbox` is NOT triggered inside the
      session — one worktree, no double-isolation). `setup_sandbox_caches(isolated_context, wt_path)`.
   c. Run the loop against `isolated_context` (swap `self._context` for the loop, restore after).
   d. **Park-guard (FR-7):** if the run ends `PARKED` under session isolation → raise a clear
      "isolation does not support HITL parking (v1)" error (a torn-down worktree loses state).
   e. `finally`: `worktree_teardown` with the `branch` (removes worktree + deletes branch) — guaranteed.
      (SF-02 inserts commit + reconcile **before** teardown; SF-01 just tears down, discarding changes.)

### Files to modify
| File | Change | FR |
|------|--------|-----|
| `src/specweaver/core/flow/handlers/base.py` | add `allowed_paths` + `session_isolation` fields | FR-5, FR-7 |
| `src/specweaver/sandbox/git/core/worktree_ops.py` | branch-delete in `handle_worktree_teardown` | FR-1 |
| `src/specweaver/core/flow/engine/runner.py` (+ `runner_utils.py`) | session lifecycle wrapper; call from `run()`/`resume()`; park-guard | FR-1, FR-2, FR-6, FR-7 |
| `tests/unit|integration/...` | see Test Plan | all |

No new module; no DB migration.

## Test Plan (4 Adversarial Buckets)

**Unit — `RunContext`:** [Happy] new fields default (`allowed_paths == []`, `session_isolation is False`).

**Unit — teardown branch-delete:** [Happy] `branch` passed → worktree removed + `git branch -D` invoked;
[Boundary] no `branch` → branch untouched (backward-compat); [Degradation] branch-delete failure logged, not raised.

**Integration — session lifecycle (real git, skip-clean if no git):**
- [Happy] 2-step pipeline under `session_isolation=True` where step 1 writes a file and step 2 reads it →
  succeeds, proving the file **persisted across steps in one worktree** (the thing the per-step model can't
  do). The bash/probe process `cwd` is inside `.worktrees/session-...`.
- [Boundary] real source root is **unmutated** after the run (no reconcile in SF-01); `.worktrees/` and the
  `sf-session-*` branch are **gone** after teardown (guaranteed cleanup).
- [Graceful degradation] `session_isolation=True` on a **non-git** project → fail-closed `RuntimeError`; the
  loop did NOT run against the real root (FR-6).
- [Hostile] a step that returns `WAITING_FOR_INPUT` under session isolation → clear park-guard error (FR-7).
- [Control] `session_isolation=False` → byte-identical to today (per-step path untouched, NFR-2).

## Audit (Phase 2) — open questions for HITL
| # | Question | Options | Proposal | Severity |
|---|----------|---------|----------|----------|
| Q1 | How to rebind for the loop — temporarily set `self._context` vs thread a context param into `_execute_loop`? | (a) swap+restore `self._context` [rec, minimal]; (b) refactor `_execute_loop(run, context)`. | **(a)** — smaller blast radius on the core loop; restore in `finally`. | MEDIUM |
| Q2 | `session_isolation` as a bool vs folding into an `isolation_mode` enum with `enforce_isolation`. | (a) new bool [rec]; (b) enum refactor of the existing per-step flag. | **(a)** — additive, zero risk to INT-US-09's per-step path; enum refactor is a separate cleanup. | MEDIUM |
| Q3 | Crash-orphan: a hard kill skips `finally`, leaving `.worktrees/session-{run_id}` + branch; a same-`run_id` retry then collides on `worktree_add`. | (a) idempotent create — prune/delete a stale same-named worktree+branch before add [rec]; (b) per-attempt random suffix; (c) accept + document. | **(a)** — prune-before-add is robust and cheap; keeps names deterministic. | HIGH |
| Q4 | `output_dir = None` under rebind so generate targets `worktree/src` — confirm no handler hard-codes the real `project_path` for writes. | (a) rely on `project_path` rebind [rec, verified: generate uses `context.output_dir or project_path/src`]; (b) also set `output_dir` explicitly. | **(a)** — `project_path` rebind is the single source of truth; SF-01 tests assert files land in the worktree. | MEDIUM |

## Architecture Verification (Phase 3)
- **Mechanism × constraint:** `base.py` — two Pydantic fields (pure data). `worktree_ops.py` — one extra
  git call in an existing helper (sandbox/git.core, the right layer). `runner.py`/`runner_utils.py` — the
  session lifecycle uses `GitAtom` surfaces + `copy.copy` + `setup_sandbox_caches`; the
  `core.flow.engine → sandbox.git` edge is **pre-existing** (INT-US-09's `execute_in_sandbox`). **No new
  cross-layer dependency; no boundary violation.** `tach`/`ruff`/`mypy --strict` must stay green.
- **Zoom-out/duplication:** the per-run lifecycle is a deliberate sibling to per-step `execute_in_sandbox`
  (the design's approved new mode), not a duplicate; it reuses the same atom primitives + cache setup.
- **Acyclic imports:** no new edge. **Stability:** `base.py` (`RunContext`) is relatively stable — the
  change is additive (two optional fields), no volatile dep introduced.
- **Verdict:** no CRITICAL architectural violation (the new mode was approved as AD-5 in the design).

## Consistency + Red/Blue (Phase 5)
- **FR/NFR/AD coverage:** FR-1/2/5-field/6/7 mapped; NFR-2 (session-off byte-identical), NFR-3 (Q3
  idempotency + guaranteed teardown), NFR-5 (Windows teardown reuse), NFR-7 (arch) honored. AD-1/3/4/5 applied.
- **KISS/DRY:** swap+restore context (minimal); reuse `setup_sandbox_caches` + atom primitives; additive fields.
- **Red/Blue correction merged:** inside an active session the runner MUST **unconditionally bypass the
  per-step `execute_in_sandbox` dispatch** (`runner.py:321-327`), not merely rely on `enforce_isolation=False`
  — otherwise a step with an explicit `use_worktree=True` would `resolve_should_isolate → True` and
  double-isolate (a per-step worktree nested in the session worktree). Add a session-active short-circuit.
- **Restore/teardown ordering:** the `finally` must restore `self._context` AND teardown; on a mid-loop
  exception both still run. Park-guard errors after teardown (v1 unrecoverable-by-design).

> [!CAUTION]
> **Session-active per-step bypass is mandatory** — cover it with a test: a `use_worktree=True` step inside a
> session runs in the SESSION worktree, not a nested per-step one.

## Implementation Notes (as-built, 2026-07-19)

Delivered the SF-01 scope. Source changes: `handlers/base.py` (`session_isolation` + `allowed_paths`
fields), `sandbox/git/core/worktree_ops.py` (branch-delete in `handle_worktree_teardown` +
`_delete_branch_if_present`, best-effort on both the clean and rmtree-fallback paths),
`sandbox/git/core/atom.py` (`branch` added to `_ENGINE_WHITELIST`), and the session lifecycle as
`runner_utils.execute_run(runner, run, logger)` (called by `run()`/`resume()`).

Decisions confirmed during dev:
- **Q1 (rebind):** swap `runner._context` for the loop, restore in `finally` — verified restored even when
  the session raises (park-guard test).
- **Q2 (trigger):** new `session_isolation` bool (independent of the per-step `enforce_isolation`).
- **Q3 (crash-orphan):** idempotent create — a `worktree_teardown` (prune) runs before `worktree_add`;
  proven by a fixed-`run_id` orphan-recovery integration test.
- **Per-step bypass:** inside an active session `runner._session_active` short-circuits the per-step
  dispatch, so an explicit `use_worktree=True` step still shares the ONE session worktree.
- **Extraction:** the session orchestration lives in `runner_utils` (not `runner.py`) — this also kept
  `runner.py` under the 600-line file-size limit (658 → 598 after moving it out).
- **Whitelist:** `git branch` was not in the engine whitelist; added it (+ updated the whitelist-pin test).

Deferred (correctly): no reconcile in SF-01 — worktree changes are discarded at teardown (SF-02 inserts
commit-before-reconcile + authorized strip-merge at the marked point in `execute_run`). The
`pipeline_engine_guide.md §7` session-mode guide is deferred until the feature is complete (SF-03), since
the mode isn't policy-selectable until then.

## Session Handoff
**Current status**: Implemented; pre-commit gate in progress (2026-07-19). Ready for commit boundary CB-1.
**Next step**: SF-02 (commit-before-reconcile + authorized strip-merge).
**Next step**: After approval, `/dev` for SF-01 (TDD). Then SF-02 (commit-before-reconcile + authorized strip-merge).
