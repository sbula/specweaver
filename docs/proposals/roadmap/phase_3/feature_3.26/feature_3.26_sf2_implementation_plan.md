# Implementation Plan: Git Worktree Bouncer (Sandbox) [SF-2: Worktree Sync & Conflict Handling]
- **Feature ID**: 3.26
- **Sub-Feature**: SF-2 — Worktree Sync & Conflict Handling (Orchestrator)
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_sf2_implementation_plan.md
- **Status**: COMPLETED

## Scope
Implements mathematical diff striping against `context.yaml`, dictatorial "Main Branch Wins" sync resolution, proactive micro-syncs (`git rebase main`), and isolated documentation claims for the orchestrator layer.

## Research Notes
- `PipelineRunner` (`src/specweaver/flow/runner.py`) uses a `StepHandlerRegistry` (in `src/specweaver/flow/handlers.py`) to execute pipeline steps.
- We must wrap `generate+code` internally, either by injecting logic into `PipelineRunner._execute_loop`, creating a new `GitBouncerHandler` decorator in the registry, or updating `GenerateCodeHandler` to spin up its operations inside the `GitAtom` using `_intent_worktree_add` and `_intent_worktree_teardown`.

## Architectural Decisions & HITL Approvals

1. **Orchestrator Integration Seam**: We will use **Option B**. `PipelineRunner._execute_loop` will dynamically detect if a step requires isolated worktrees (e.g. `StepTarget.CODE` under Generation/Tests if a pipeline flag `use_worktree` is present). It will spin up the Worktree using `GitAtom._intent_worktree_add`, wrap the inner runner execution (by pushing context down), apply the patch mathematically, and tear down strictly using `GitAtom._intent_worktree_teardown`. 
2. **Diff Striping Strategy**: We will use **Option B**. The pipeline mathematical striping will discard any hunks targeting paths not present in `context.yaml`, merge the *allowed* hunks cleanly to the trunk, and emit a warning log. This natively rejects hallucinations without destroying valid work.
3. **Ephemeral Sandbox Context Passing**: We will use **Option A**. The Flow Runner will temporarily override `RunContext.output_dir` dynamically, injecting the absolute path of the ephemeral worktree so that downstream tools cleanly limit operations to the cloned space naturally.

## Sub-Feature Implementation Details

### 1. Model Updates (`src/specweaver/flow/models.py`)
- **[MODIFY]**: Add `use_worktree: bool = False` to `PipelineStep`. By explicitly providing this flag in the Pipeline Definition yaml parsing layer, we enable the orchestrator to decide exactly when to use the Git Bouncer per step.

### 2. Sandbox Integration (`src/specweaver/flow/runner.py`)
- **[MODIFY]**: In `PipelineRunner._execute_loop`, intercept steps that have `step_def.use_worktree = True`.
- **Implementation Logic**:
  1. Generate unique worktree branch name (`sf-<task_id>-temp`).
  2. Call `GitAtom._intent_worktree_add` to instantiate the physical Sandbox directory.
  3. Symlink `cache_dirs` utilizing `EngineFileExecutor.symlink` via mapping paths on `FileSystemAtom`.
  4. Create a cloned `RunContext` setting `output_dir = worktree_path`.
  5. `await handler.execute(step_def, isolated_context)`.
     *(FR-8: If handler generates documentation claims, capture them purely in a localized `doc_updates.md` to prevent shared architecture mutation).*
  6. **(FR-7)**: Execute `GitAtom._intent_worktree_sync` (`git rebase main`) on the active worktree to proactively absorb any human changes on trunk.
  7. Perform mathematical Diff Striping on the worktree index utilizing `loom/atoms/git/atom.py` diffing boundaries.
  8. Commit and merge back using `--strategy-option=ours` **(FR-5)**.
  9. Enforce teardown unconditionally (`finally:` block) utilizing `GitAtom._intent_worktree_teardown`.

> [!CAUTION]
> Ensure any `RunContext` mutations are cloned tightly within the inner loop scope to prevent bleeding the ephemeral directory path into the next sequential pipeline iterations!

### 3. Diff Striping Math (`src/specweaver/loom/atoms/git/atom.py` or `EngineGitExecutor`)
- **[MODIFY]**: Expose `_intent_strip_merge` or similar diff-patching utility leveraging native core `.diff` features and string analysis of the `context.yaml` allowed boundaries.
- **[NFR-4 constraint]**: Actively rip out disallowed file hunks before finalizing the internal git commit. Hardcode absolute exclusion paths for shared docs (`README.md`, `docs/*`) regardless of agent attempts to manipulate them.

## Verification Plan
1. **Automated Tests**: Write tests in `tests/integration/flow/test_runner_sandbox.py` that trigger a mocked handler which hallucinates edits to a `README.md` and authorized edit to `src/foo.py`, verifying that the striping correctly discards `README.md`.
2. **Unit Tests**: Ensure `PipelineStep.use_worktree` correctly initializes.
