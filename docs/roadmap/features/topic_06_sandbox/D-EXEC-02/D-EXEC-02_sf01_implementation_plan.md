# D-EXEC-02 SF-01 — Worktree Sandbox Lifecycle (Atoms)

**Status**: COMPLETED (2026-04-11) · **FRs owned**: FR-1, FR-2, FR-6 (+ NFR-1, NFR-2, NFR-3) ·
**Depends on**: none · Design: [D-EXEC-02_design.md](D-EXEC-02_design.md) §Sub-features → SF-01

## Goal

Atom and executor mechanics to create, symlink and force-tear-down parallel git worktrees.

## Changes

1. **`src/specweaver/flow/models.py`** (FR-2) — add `cache_dirs: list[str] = Field(default_factory=list)`
   to `PipelineDefinition` or `RunContext`, parsed from YAML like `cache_dirs: ["node_modules", ".gradle"]`.
2. **`src/specweaver/loom/commons/filesystem/executor.py`** — `symlink(self, target: str, link_name: str) -> ExecutorResult:`
   on `EngineFileExecutor` only (the flow engine can use it, agents cannot). Uses
   `Path.symlink_to(target, target_is_directory=True)`; both `target` and `link_name` must resolve
   inside the trusted bounds, so path-traversal blocks still hold.
3. **`src/specweaver/loom/atoms/filesystem/atom.py`** — `_intent_symlink(self, context: dict[str, Any]) -> AtomResult`.
   Inputs: `target` (absolute workspace dependency to link from), `link_name` (relative worktree hook
   inside cwd). Calls `self._executor.symlink(target, link_name)`.
4. **`src/specweaver/loom/atoms/git/atom.py`** (FR-1, FR-6, NFR-1) — add `"worktree"` to
   `_ENGINE_WHITELIST`; `_intent_worktree_add(self, context)` runs
   `git worktree add -b <branch> <path> <main>`; `_intent_worktree_remove(self, context)` retries 5
   times on non-zero exit, then falls back to `shutil.rmtree(path, ignore_errors=True)` followed by
   `git worktree prune`.

## Tests

| File | Case |
|---|---|
| `tests/loom/atoms/test_git_atom.py` | `_intent_worktree_remove` survives mocked OS Access Denied failures by falling through to `shutil.rmtree` + prune |
| `test_engine_file_executor_symlink` | path-traversal bounds hold for cache symlinks |

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | How are cache dirs discovered? | A `cache_dirs` array in the pipeline YAML |
| Q2 | Who creates symlinks, keeping domains pure? | Per the Archetypes: `EngineFileExecutor` runs `os.symlink`, orchestrated through `FileSystemAtom` |
| Q3 | Windows locks at teardown? | Aggressive teardown: `git worktree remove --force`, falling back to `shutil.rmtree` and `git worktree prune` |

## As built

**Since moved** (checked 2026-09-25): git atom → `src/specweaver/sandbox/git/core/atom.py`
(`_intent_worktree_teardown`, body in `worktree_ops.py`); symlink →
`src/specweaver/sandbox/filesystem/core/executor.py`; `cache_dirs` → `core/flow/engine/models.py`.
