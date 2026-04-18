# Implementation Plan: Git Worktree Bouncer (Sandbox) [SF-1: Worktree Sandbox Lifecycle (Atoms)]
- **Feature ID**: 3.26
- **Sub-Feature**: SF-1 — Worktree Sandbox Lifecycle (Atoms)
- **Design Document**: docs/roadmap/phase_3/feature_3.26/feature_3.26_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3.26/feature_3.26_sf1_implementation_plan.md
- **Status**: COMPLETED
- **Completed On**: 2026-04-11

## Scope & Dependencies
This implementation plan covers the core Atom and Executor mechanics to safely create, symlink, and forcefully tear down parallel git worktrees. This handles FR-1, FR-2, FR-6, NFR-1, NFR-2, and NFR-3.

## Architectural Approvals & Constraints
1. **Cache Symlinking Discovery (Q1):** Approved to add `cache_dirs` configuration array to pipeline YAML.
2. **File System Bounds (Q2):** Approved strictly adhering to Archetypes. Domain purity will be protected: `os.symlink` will be executed by `EngineFileExecutor`, heavily orchestrating `FileSystemAtom`.
3. **Windows Safety Hook (Q3):** Approved aggressive teardown to prevent Windows locks. We will use a mixed `git worktree remove --force` fallback pipeline combining `shutil.rmtree` and `git worktree prune`.

## File Modifications

### 1. `src/specweaver/flow/models.py`
- **Objective:** Support declarative caching (FR-2).
- **Changes:**
  - Add `cache_dirs: list[str] = Field(default_factory=list)` to `PipelineDefinition` or `RunContext` so it natively parses YAML definitions like `cache_dirs: ["node_modules", ".gradle"]`.

### 2. `src/specweaver/loom/commons/filesystem/executor.py`
- **Objective:** Enable symlinking logic without compromising path traversal blocks.
- **Changes:**
  - Introduce `symlink(self, target: str, link_name: str) -> ExecutorResult:` strictly bounded inside `EngineFileExecutor` (agents cannot use this, only the Flow Engine).
  - Use `Path.symlink_to(target, target_is_directory=True)` ensuring both the `target` and the `link_name` are fully resolved within the trusted context bounds.

### 3. `src/specweaver/loom/atoms/filesystem/atom.py`
- **Objective:** Export symlink functionality to the flow orchestrator.
- **Changes:**
  - Create `_intent_symlink(self, context: dict[str, Any]) -> AtomResult`. Expected inputs: `target` (absolute workspace dependency to link from) and `link_name` (relative worktree hook inside cwd). 
  - Call `self._executor.symlink(target, link_name)`.

### 4. `src/specweaver/loom/atoms/git/atom.py`
- **Objective:** Setup and safely teardown the physical worktrees (FR-1, FR-6, NFR-1).
- **Changes:**
  - Define `_ENGINE_WHITELIST` additions to include `"worktree"`.
  - Add `_intent_worktree_add(self, context)` executing `git worktree add -b <branch> <path> <main>`.
  - Add `_intent_worktree_remove(self, context)`.
  - **[NFR-1 / Q3 Teardown Logic]:** Wrap in a 5-iteration retry loop checking for non-zero exit codes. Under failure, implement explicit `shutil.rmtree(path, ignore_errors=True)` followed by `git worktree prune`.

## Verification & Testing Strategy
- **Unit Testing**: Add explicit test cases in `tests/loom/atoms/test_git_atom.py` asserting `_intent_worktree_remove` successfully survives mock simulated OS Access Denied failures by routing successfully into the `shutil.rmtree` + prune hook.
- **Unit Testing**: Add `test_engine_file_executor_symlink` to verify path traversal bounding logic is correctly enforced on cache symlinks.
