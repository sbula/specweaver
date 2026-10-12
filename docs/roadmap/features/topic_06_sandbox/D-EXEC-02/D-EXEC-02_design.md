# D-EXEC-02 — Git Worktree Bouncer (Sandbox)

**Status**: APPROVED. Built; `🔧` until the user signs off. · **Feature ID**: 3.26 · **Phase**: 3

| | |
|---|---|
| Touches | flow engine (`core/flow/engine/sandboxed_execution.py`) · git atom (`sandbox/git/core/`) |
| Extended by | `C-EXEC-06` — one worktree per multi-step run |

## What it does

Runs one pipeline step in its own git worktree, so a model's mistake cannot touch files outside its
task. When the step passes, its work is committed in the worktree and only the step's own target
files merge back into the current branch; on a conflict the branch's version wins. The worktree is
removed afterwards, also when Windows holds a file lock.

Turned on per step (`use_worktree: true`) or for every step (`[sandbox] enforce_worktree_isolation`).

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| AD-1 | The engine uses the git atom, never raw git | the flow engine may not bypass atoms (`context.yaml`) |
| AD-2 | Worktrees, overriding the earlier veto `[approved 2026-04-11]` | an isolated worktree is the only safe way to strip a diff |

## Functional Requirements

FR-7 (continuous micro-sync) was withdrawn `[agreed 2026-10-08]`: a rebase onto `main` would pull
`main` into whatever branch the user is on.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Create worktree | Orchestrator | create a dedicated git worktree in `.worktrees/<run id>` | the step works on files apart from the user's |
| FR-2 | Cache symlinking | Orchestrator | symlink heavy cache folders (like `node_modules`, `.gradle`) into the worktree | the worktree builds without copying caches |
| FR-3 | Commit bounding | Agent | write and commit changes only inside the worktree | a mistake never touches the user's files directly |
| FR-4 | Diff stripping | Orchestrator | commit the worktree, then merge back only the step's generation targets (`src/<stem>.py`, `tests/test_<stem>.py`), and only when the step passed `[agreed 2026-10-08]` | an edit to any other file never reaches the user's branch |
| FR-5 | Main branch wins | Orchestrator | merge with `-X ours`, so a change committed on the branch while the step ran beats the step's own | the user's changes always win |
| FR-6 | Cleanup | Orchestrator | remove the worktree and its branch after the step, passed or failed | no worktree is left behind |
| FR-8 | Isolated documentation claims | Agent / Orchestrator | write wanted documentation changes to `doc_updates.md`, which merges back whatever the targets | agents propose doc changes without editing shared docs |

## Non-Functional Requirements

NFR-2 (a 50 MB worktree whatever the repository size) was removed `[agreed 2026-10-12]`: a worktree
holds a copy of every tracked file; FR-2 covers the caches.

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Windows file locking | Cleanup retries a locked delete at least 3 times with growing waits before it fails |
| NFR-3 | Speed | Worktree setup and cleanup take under 2 seconds |
| NFR-4 | Shared documentation protection | `README.md` and `docs/` never merge back |

## Live demo

In a git project, a pipeline with one `action: bash`, `use_worktree: true` step whose script writes
`src/<stem>.py`, `docs/guide.md` and `stray.py`: after `sw run`, only `src/<stem>.py` changed, and
no worktree is left. Commit a change to the same line of `src/<stem>.py` while the step runs: yours
stays. The run takes under a second.

## Sub-features

| SF | Does | FRs | Plan | Committed |
|----|------|-----|------|-----------|
| SF-01 | Worktree lifecycle: setup, cache symlinks, cleanup | FR-1, FR-2, FR-6 | [sf01](D-EXEC-02_sf01_implementation_plan.md) | ✅ |
| SF-02 | Commit, diff stripping, main wins, doc claims | FR-3, FR-4, FR-5, FR-8 | [sf02](D-EXEC-02_sf02_implementation_plan.md) | ✅ |
