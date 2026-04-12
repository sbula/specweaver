# Design: Git Worktree Bouncer (Sandbox)

- **Feature ID**: 3.26
- **Phase**: 3
- **Status**: APPROVED
- **Design Doc**: docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_design.md

## Feature Overview

Feature 3.26 adds a Git Worktree Bouncer capability to the pipeline orchestrator. It solves the problem of LLM hallucinations modifying untouchable/forbidden files by cloning the active task to an isolated ephemeral git worktree, and using strict diff striping to block/delete out-of-bounds changes before merging back into the trunk. Based on Trunk-Based Development workflows, it minimizes branch juggling overhead via proactive TDD isolation, continuous micro-rebasing to keep the worktree strictly synced with the master branch, and enforcing a reactive "Main Branch Wins" auto-resolution strategy. It touches the Workflow flow engine (`flow/`) and the Loom git execution atom (`loom/atoms/git/`). Key constraints: must aggressively block out-of-bounds file edits, must handle Windows file-locking cleanly to prevent zombie trees, and must prevent heavy cache duplication.

## Research Findings

### Codebase Patterns
- **Atoms vs. Tools**: As established in the architecture reference, the Flow engine (`specweaver/flow`) forbids consuming `loom/tools/*` because agents interact with tools. Instead, it must directly consume `loom/atoms/git/` to execute powerful, engine-internal git operations like `worktree add`, diffing, and merging.
- **Context Boundaries**: The allowed files for any implementation task are formally declared via `context.yaml` and the `Spec.md` artifact. These existing manifests act as the dictionary parameter for the mathematical diff striping algorithm without requiring a new security protocol.
- **Workflow Pipeline Runner**: Feature 3.26 logically integrates into `src/specweaver/flow/runner.py` or as a distinct Step Handler wrapper (`GitBouncerHandler`) so that `generate+code` actions run wrapped inside the worktree setup/teardown sequence.

### External Tools
| Tool | Version | Key API Surface | Source |
|------|---------|----------------|--------|
| git.exe | >= 2.24 | `git worktree add`, `git worktree remove`, `git parse`, `git diff` | Git SCM manual |
| mklink (OS) | Windows 10+ | Directory symlinking /D for caches | Windows OS |

### Blueprint References
- `flowmanager_legacy_reference.md`
- Codebase Context Specification (CCS) v1.1.0-RFC

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Create worktree | Orchestrator | create a dedicated git worktree in `.worktrees/<task_id>` | The agent executes inside parallel files physically separate from the main workspace. |
| FR-2 | Cache symlinking | Orchestrator | symlink heavy workspace cache folders (like `node_modules`, `.gradle`) into the new worktree | The new worktree compiles without downloading gigabytes of cache dependencies. |
| FR-3 | Commit bounding | Agent | write code and commit changes strictly within the active worktree index | Hallucinations physically never touch the human's main branch files. |
| FR-4 | Diff Striping | Orchestrator | compute a structural diff patch of the worktree against main, stripping any hunks that target paths not listed in `context.yaml` | The final merge pipeline mathematically blocks hallucinated edits to forbidden dependencies. |
| FR-5 | Conflict Auto-Resolution| Orchestrator | apply a "Main-Branch Wins" (`--strategy-option=ours`) merge conflict logic during syncing | Human changes on main immediately override conflicting hallucinated agent changes. |
| FR-6 | Cleanup / Zombie prevention | Orchestrator | execute `git worktree remove --force` upon phase success/failure with strict OS unlock retries | The system is purged of temporary structures without leaving orphaned locked files on Windows. |
| FR-7 | Continuous Micro-Sync | Orchestrator | execute a proactive `git rebase main` on the sub-feature worktree when human edits occur on main | The worktree avoids deep drift over long implementation phases. |
| FR-8 | Isolated Documentation Claims | Agent / Orchestrator | output a localized `doc_updates.md` explicitly bounded within the isolated Component directory before completing its task | Agents can systematically flag required changes to global architecture documents without modifying them concurrently, delegating compilation to a sequential post-merge step. |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Windows File Locking | The teardown hook MUST capture `Access Denied` IO errors and execute at least 3 retry loops with progressive backoff to mitigate Windows Defender or IDE background locks before fully failing. |
| NFR-2 | Disk Footprint | The footprint of spinning up an agent MUST NOT exceed 50 MB independently of the main repository size via strict directory symlinking strategies. |
| NFR-3 | Speed | Worktree setup and cleanup MUST occur in under 2 seconds. |
| NFR-4 | Shared Documentation Protection | Shared global documentation (e.g. `docs/`, `README.md`) MUST be treated as implicitly forbidden during the mathematical diff striping phase. Agents operating in parallel worktrees must be blocked from updating shared architecture docs to prevent overlapping documentation merge conflicts. |

## External Dependencies

| Tool | Min Version | Key API Surface | Compat Confirmed | Notes |
|------|------------|----------------|-----------------|-------|
| Git | 2.24 | `git worktree` | Y | Standard local feature. |

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | Engine utilizes `loom/atoms/git` | The Flow engine cannot bypass atoms to touch Git raw. Consuming atoms conforms to the `consumes` rule stack. | No |
| AD-2 | Overriding MCP vs CLI ADR | Overriding the previous architecture decision that vetoed the worktree approach. Utilizing isolated worktrees is deemed the only way to dictate math-based diff stripping securely. | Yes — approved by User on 2026-04-11 |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| Worktree Lifecycle Troubleshooting | Details on manually pruning zombied worktrees and `.git/worktrees` hooks when Windows locks fail permanently. | ⬜ To be written during Pre-commit |

## Sub-Feature Breakdown

### SF-1: Worktree Sandbox Lifecycle (Atoms)
- **Scope**: Safe operational setup, cache symlinking, and robust OS-level teardown of physical worktrees.
- **FRs**: [FR-1, FR-2, FR-6]
- **Inputs**: Task ID, target Component Path, Project Root Path.
- **Outputs**: Unique, validated `git worktree` branch mapped to an active physical directory.
- **Depends on**: none
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_sf1_implementation_plan.md

### SF-2: Worktree Sync & Conflict Handling (Orchestrator)
- **Scope**: Mathematical diff striping (rejecting forbidden paths), isolated documentation claiming, and strict main-branch-wins sync resolution logic.
- **FRs**: [FR-3, FR-4, FR-5, FR-7, FR-8]
- **Inputs**: Generated code in Worktree Branch, `context.yaml` boundaries manifest, Main Branch HEAD, `doc_updates.md` claims.
- **Outputs**: Purified diff patch applied cleanly to the main branch.
- **Depends on**: SF-1
- **Impl Plan**: docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_sf2_implementation_plan.md

## Execution Order

1. SF-1: Worktree Sandbox Lifecycle (no deps — start immediately)
2. SF-2: Worktree Sync & Conflict Handling (depends on SF-1)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-1 | Worktree Sandbox Lifecycle | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-2 | Worktree Sync & Conflict Handling | SF-1 | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Current status**: SF-2 Implementation Plan APPROVED.
**Next step**: Run:
`/dev docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_sf2_implementation_plan.md`
**If resuming mid-feature**: Read the Progress Tracker above. Find the first ⬜ in any row and resume from there using the appropriate workflow.
