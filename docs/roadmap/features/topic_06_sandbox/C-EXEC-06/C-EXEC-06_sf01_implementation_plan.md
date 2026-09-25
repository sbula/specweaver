# C-EXEC-06 SF-01 — Session Worktree Lifecycle + Context Rebind

**Status**: APPROVED — approved by Steve Bula on 2026-07-19. Audit Q1–Q4 all resolved to option
**(a)**. Implemented 2026-07-19. · **FRs owned**: FR-1, FR-2, FR-5 (field only), FR-6, FR-7
(park-guard) · **Depends on**: none · Design: [C-EXEC-06_design.md](C-EXEC-06_design.md) §Sub-features → SF-01

## Goal

Create ONE ephemeral worktree when a session-isolated run starts. Rebind the session workspace root
to it for **all** steps. Tear down **once** — worktree **and** branch — in a guaranteed `finally`.
Fail closed if it cannot be created. Add `RunContext.allowed_paths` (unpopulated) and a
`session_isolation` trigger.

**No reconcile yet** — that is SF-02. Under SF-01 the worktree's changes are discarded at teardown,
which proves isolation: the real source root is unmutated.

## Where it plugs in

| Fact | Where |
|---|---|
| `run()` and `resume()` both do `try: async with cqrs_context(): return await self._execute_loop(run) finally: save_handover; flush`. The session lifecycle wraps `_execute_loop`. | `runner.py:130-134`, `:176-181` |
| `_execute_loop` uses `self._context` directly. Per-step dispatch: `if resolve_should_isolate(step_def, self._context): result = execute_in_sandbox(...) else handler.execute(step_def, self._context)` | `runner.py:321-327` |
| `RunContext` has `project_path`, `output_dir` (`:55`), `enforce_isolation` (`:56`, per-step policy), `execution_root` (`:57`). No `allowed_paths`, no session flag. `db` is a live `Database` object (`:65`), not path-derived — rebinding `project_path` does NOT re-open the DB. | `handlers/base.py:30-74` |
| Per-step reference: `worktree_add` → `copy.copy(context)` + rebind `output_dir`/`execution_root` to `wt_path` → `setup_sandbox_caches` → handler → sync/strip_merge → `worktree_teardown` (finally). SF-01 builds the per-run analog, once around the whole loop. | `runner_utils.py:151-221` |
| `worktree_add` = `git worktree add -b <branch> <path> HEAD`. `worktree_teardown` (→ `worktree_ops.handle_worktree_teardown:20-64`) removes the worktree but **NOT the branch**. No branch-delete intent exists. | `git/core/atom.py:385-415`, `:417-425` |
| `enforce_isolation` is set from `sandbox.enforce_worktree_isolation`. SF-03 populates `session_isolation` the same way; SF-01 tests set `context.session_isolation` directly. | `flow/interfaces/cli.py:270-272` |
| GitAtom primitives: `worktree_add` `:385-415`, `worktree_sync` `:427-475`, `strip_merge` `:477-491`; `worktree_teardown` body | `git/core/atom.py`; `worktree_ops.py:20-64` |

Naming fixes Gap 3 structurally: one worktree per run, named from `run_id`
(`.worktrees/session-{run_id}`, branch `sf-session-{run_id}`), so no per-step collision; distinct
`run_id`s keep runs apart. Crash-orphan on a same-`run_id` retry: see Q3.

External deps: git (existing). No new tool, no new module, no DB migration.

## Changes

1. **`RunContext` fields** (FR-5 field) · `handlers/base.py` — add
   `allowed_paths: list[str] = Field(default_factory=list)` and `session_isolation: bool = False`
   (the per-run trigger, independent of per-step `enforce_isolation`).
2. **Branch-aware teardown** (FR-1) · `git/core/worktree_ops.py` — after removing the worktree, if
   `context.get("branch")` is set, run `git branch -D <branch>` (best-effort, logged). No `branch` →
   today's behavior, so per-step teardown is unchanged.
3. **Session lifecycle wrapper** (FR-1, FR-2, FR-6, FR-7) · `runner.py` + `runner_utils.py` —
   `run()`/`resume()` call it instead of `_execute_loop` (planned as `_execute_maybe_session(run)`;
   built as `runner_utils.execute_run`):
   1. `not context.session_isolation` → `return await _execute_loop(run)` (unchanged path).
   2. `worktree_add` at `.worktrees/session-{run_id}`, branch `sf-session-{run_id}`. On failure raise
      an actionable `RuntimeError` (non-git project / stale worktree) and do NOT run the loop (FR-6).
   3. `isolated_context = copy.copy(context)` with `project_path = worktree`,
      `execution_root = worktree`, `output_dir = None` (generate writes to `worktree/src`, run_tests
      cwd = worktree), `enforce_isolation = False`. Then `setup_sandbox_caches(isolated_context, wt_path)` (symlinks `.specweaver`/caches into the
      worktree).
   4. Run the loop against `isolated_context` (swap `self._context`, restore after).
   5. **Park-guard (FR-7):** a run that ends `PARKED` under session isolation raises
      "isolation does not support HITL parking (v1)" — a torn-down worktree loses state.
   6. `finally`: `worktree_teardown` with the `branch`. SF-02 inserts commit + reconcile **before**
      this point.

| File | Change | FR |
|------|--------|-----|
| `src/specweaver/core/flow/handlers/base.py` | add `allowed_paths` + `session_isolation` fields | FR-5, FR-7 |
| `src/specweaver/sandbox/git/core/worktree_ops.py` | branch-delete in `handle_worktree_teardown` | FR-1 |
| `src/specweaver/core/flow/engine/runner.py` (+ `runner_utils.py`) | session lifecycle wrapper; call from `run()`/`resume()`; park-guard | FR-1, FR-2, FR-6, FR-7 |
| `tests/unit|integration/...` | see Tests | all |

> [!CAUTION]
> **The per-step bypass is mandatory** (Red/Blue correction). Inside an active session the runner
> MUST unconditionally skip the per-step `execute_in_sandbox` dispatch (`runner.py:321-327`). Setting
> `enforce_isolation=False` is not enough: a step with an explicit `use_worktree=True` would still
> `resolve_should_isolate → True` and nest a per-step worktree inside the session one. Test it: a
> `use_worktree=True` step inside a session runs in the SESSION worktree.

The `finally` must restore `self._context` AND tear down, both even on a mid-loop exception. The
park-guard error comes after teardown (v1 unrecoverable by design).

## Tests

| Tier | Bucket | Case |
|---|---|---|
| Unit — `RunContext` | Happy | new fields default: `allowed_paths == []`, `session_isolation is False` |
| Unit — teardown | Happy | `branch` passed → worktree removed + `git branch -D` invoked |
| | Boundary | no `branch` → branch untouched (backward-compat) |
| | Degradation | branch-delete failure logged, not raised |
| Integration — real git, skip clean if no git | Happy | 2-step pipeline, `session_isolation=True`: step 1 writes a file, step 2 reads it → the file **persisted across steps in one worktree** (the per-step model cannot do this). The probe's `cwd` is inside `.worktrees/session-...` |
| | Boundary | real source root **unmutated** after the run; `.worktrees/` and the `sf-session-*` branch **gone** after teardown |
| | Degradation | `session_isolation=True` on a **non-git** project → fail-closed `RuntimeError`; the loop did NOT run against the real root (FR-6) |
| | Hostile | a step returning `WAITING_FOR_INPUT` under session isolation → park-guard error (FR-7) |
| | Control | `session_isolation=False` → byte-identical to today (NFR-2) |

## Decisions (audit)

| # | Question | Options | Chosen | Severity |
|---|----------|---------|--------|----------|
| Q1 | Rebind for the loop: swap `self._context`, or thread a context param into `_execute_loop`? | (a) swap + restore; (b) refactor `_execute_loop(run, context)` | **(a)** — smaller blast radius on the core loop; restore in `finally` | MEDIUM |
| Q2 | `session_isolation` bool, or an `isolation_mode` enum folded with `enforce_isolation`? | (a) new bool; (b) enum refactor of the per-step flag | **(a)** — additive, zero risk to INT-US-09's per-step path; the enum is a separate cleanup | MEDIUM |
| Q3 | A hard kill skips `finally` and leaves `.worktrees/session-{run_id}` + branch; a same-`run_id` retry collides on `worktree_add`. | (a) idempotent create — prune/delete a stale same-named worktree+branch before add; (b) per-attempt random suffix; (c) accept + document | **(a)** — robust, cheap, keeps names deterministic | HIGH |
| Q4 | With `output_dir = None`, does any handler hard-code the real `project_path` for writes? | (a) rely on the `project_path` rebind; (b) also set `output_dir` explicitly | **(a)** — verified: generate uses `context.output_dir or project_path/src`; tests assert files land in the worktree | MEDIUM |

Architecture check: two Pydantic fields (pure data); one extra git call in an existing
`sandbox.git.core` helper; the lifecycle uses `GitAtom`, `copy.copy` and `setup_sandbox_caches`. The
`core.flow.engine → sandbox.git` edge already exists (INT-US-09's `execute_in_sandbox`). No new
cross-layer dependency, no new import edge; `tach`/`ruff`/`mypy --strict` must stay green. The per-run lifecycle is a deliberate sibling of
per-step `execute_in_sandbox` (AD-5), not a duplicate. Coverage: FR-1/2/5-field/6/7; NFR-2, NFR-3
(Q3 + guaranteed teardown), NFR-5 (Windows teardown reuse), NFR-7; AD-1/3/4/5.

## As built (2026-07-19)

| Where | What |
|---|---|
| `handlers/base.py` | `session_isolation` + `allowed_paths` fields |
| `sandbox/git/core/worktree_ops.py` | branch-delete in `handle_worktree_teardown` + `_delete_branch_if_present`, best-effort on both the clean and the rmtree-fallback path |
| `sandbox/git/core/atom.py` | `branch` added to `_ENGINE_WHITELIST` (it was missing; whitelist-pin test updated) |
| `runner_utils.execute_run(runner, run, logger)` | the session lifecycle, called by `run()`/`resume()`. Lives in `runner_utils`, which also kept `runner.py` under the 600-line limit (658 → 598) |

- Q1: `runner._context` is restored even when the session raises (park-guard test).
- Q3: a `worktree_teardown` (prune) runs before `worktree_add`; proven by a fixed-`run_id`
  orphan-recovery integration test.
- Per-step bypass: `runner._session_active` short-circuits per-step dispatch, so a
  `use_worktree=True` step shares the ONE session worktree.
- Deferred: reconcile → SF-02 (inserted at the marked point in `execute_run`). The
  `pipeline_engine_guide.md §7` session-mode guide waits for SF-03, when the mode becomes
  policy-selectable.

Commit boundary: CB-1. Next: SF-02.
