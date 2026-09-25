# D-EXEC-02 SF-02 — Worktree Sync & Conflict Handling (Orchestrator)

**Status**: COMPLETED · **FRs owned**: FR-3, FR-4, FR-5, FR-7, FR-8 · **Depends on**: SF-01 ·
Design: [D-EXEC-02_design.md](D-EXEC-02_design.md) §Sub-features → SF-02

## Goal

In the orchestrator: diff stripping against `context.yaml`, "Main Branch Wins" sync resolution,
proactive micro-syncs (`git rebase main`), and isolated documentation claims.

## Where it plugs in

- `PipelineRunner` (`src/specweaver/flow/runner.py`) runs steps through a `StepHandlerRegistry`
  (`src/specweaver/flow/handlers.py`).
- `generate+code` must be wrapped: in `PipelineRunner._execute_loop`, in a new `GitBouncerHandler`
  decorator in the registry, or in `GenerateCodeHandler` via `GitAtom`'s `_intent_worktree_add` and
  `_intent_worktree_teardown`. Q1 picks the first.

## Changes

1. **`src/specweaver/flow/models.py`** [MODIFY] — `use_worktree: bool = False` on `PipelineStep`. Set
   in the pipeline YAML, it tells the orchestrator which steps use the Git Bouncer.
2. **`src/specweaver/flow/runner.py`** [MODIFY] — `PipelineRunner._execute_loop` intercepts steps with
   `step_def.use_worktree = True`:
   1. Unique branch name `sf-<task_id>-temp`.
   2. `GitAtom._intent_worktree_add` creates the sandbox directory.
   3. Symlink `cache_dirs` via `EngineFileExecutor.symlink`, mapped through `FileSystemAtom`.
   4. Clone `RunContext` with `output_dir = worktree_path`.
   5. `await handler.execute(step_def, isolated_context)`. **FR-8:** documentation claims go only to a
      local `doc_updates.md`, never into shared architecture docs.
   6. **FR-7:** `GitAtom._intent_worktree_sync` (`git rebase main`) absorbs human changes on trunk.
   7. Diff stripping on the worktree index, using the diff support in `loom/atoms/git/atom.py`.
   8. Commit and merge back with `--strategy-option=ours` (**FR-5**).
   9. Teardown always, in `finally:`, via `GitAtom._intent_worktree_teardown`.
3. **`src/specweaver/loom/atoms/git/atom.py` or `EngineGitExecutor`** [MODIFY] — `_intent_strip_merge`
   (or similar): uses git's `.diff` and the `context.yaml` allowed paths. **NFR-4:** remove disallowed
   hunks before the internal commit; shared docs (`README.md`, `docs/*`) are always excluded, whatever
   the agent does.

> [!CAUTION]
> Clone `RunContext` inside the loop scope, so the ephemeral worktree path never leaks into the next
> pipeline iteration.

## Tests

| Tier | File | Case |
|---|---|---|
| Integration | `tests/integration/flow/test_runner_sandbox.py` | mocked handler edits `README.md` (hallucinated) and `src/foo.py` (authorized) → `README.md` discarded |
| Unit | — | `PipelineStep.use_worktree` initializes correctly |

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Integration seam | **Option B** — `PipelineRunner._execute_loop` detects steps needing a worktree (e.g. `StepTarget.CODE` under Generation/Tests when the pipeline flag `use_worktree` is set), sets it up via `GitAtom._intent_worktree_add`, runs the step with the context pushed down, applies the patch, tears down via `GitAtom._intent_worktree_teardown` |
| Q2 | Diff stripping | **Option B** — drop hunks for paths not in `context.yaml`, merge the *allowed* hunks to trunk, log a warning. Rejects hallucinations without destroying valid work |
| Q3 | Sandbox context passing | **Option A** — the runner temporarily overrides `RunContext.output_dir` with the worktree's absolute path, so downstream tools stay in the clone |

## As built

**Since changed** (checked 2026-09-25): `use_worktree` is `bool | None` in
`core/flow/engine/models.py`, resolved with the `[sandbox] enforce_worktree_isolation` policy in
`core/flow/engine/isolation.py`; the git intents live in `src/specweaver/sandbox/git/core/atom.py`.
Multi-step runs use `C-EXEC-06`'s per-run worktree instead.
