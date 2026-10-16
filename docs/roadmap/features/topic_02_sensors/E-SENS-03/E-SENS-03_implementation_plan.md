# Implementation Plan: Workspace Boundaries
- **Feature ID**: E-SENS-03
- **Design Document**: docs/roadmap/features/topic_02_sensors/E-SENS-03/E-SENS-03_design.md
- **Implementation Plan**: docs/roadmap/features/topic_02_sensors/E-SENS-03/E-SENS-03_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-16 · built: CB-1 `9dfe74d7`, CB-2 `81edf348`, CB-3

**FRs owned**: FR-1 … FR-5, NFR-1, NFR-2 · **Depends on**: none · **Paths**: P1 … P5

## Goal

An agent with the coder's role may create and change its own task's files and nothing else; a role
with no rule gets nothing; reads stay project-wide.

## Shape

| Piece | Where | Tag |
|---|---|---|
| the allow-list matcher (`path_allowed`: paths and globs, `*` in one folder, `**` across) moves to one home, used by the merge and the grant | `sandbox/security.py` ← `sandbox/git/core/worktree_ops.py:125-139` | MOVE |
| a task grant: FULL on the paths the merge would keep — the task's entries and any `doc_updates.md`, never `README.md` or `docs/` — one rule shared with the merge | `sandbox/security.py` (`grant_mode_for`) | MODIFY |
| an entry that is absolute or holds `..` stops the grant from being built (NFR-2) | `sandbox/security.py` | NEW |
| `create_standard_set(..., task_files=())` → `_compute_role_grants(role, boundary, task_files)`; the `implementer` rule: READ on roots and API paths, the task grant; any role without a rule: no grant | `sandbox/dispatcher.py:110-193` | MODIFY |
| `task_files(context)`: the run's `allowed_paths` when set, else `derive_allowed_paths(spec_path)` | `core/flow/engine/isolation.py` | NEW |
| `GraphContext.workspace_roots` goes; `from_run_context` and `_resolve_mentions` use the project root | `handlers/run_context.py`, `sandbox/security.py`, `handlers/review.py` | MODIFY |

Order inside one file call: the tool normalises the path → the grant matcher finds the best mode
(READ from the roots, FULL from the task grant) → the tool's own check for the operation (write,
create, delete) refuses below the mode it needs, naming the path.

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the matcher's one home, the task grant, the role rules, NFR-2 | FR-2, FR-3, FR-4, NFR-1, NFR-2 | the implementer may create `README.md` and any file in the project; an unknown role gets FULL — red today |
| CB-2 | `task_files(context)`, from isolation on and off, into the dispatcher | FR-1 | no function gives a task's files with isolation off, so the grant cannot be built from a run — red today |
| CB-3 | `workspace_roots` removed | FR-5 | the field still exists and is read in three places — a test that names it fails once it is gone |

| CB | Tier | Test |
|---|---|---|
| CB-1 | unit + integration | role grants by table; a real `CodeStructureTool` from `create_standard_set("implementer", task_files=[...])` creates `src/greeter.py`, is refused `src/other.py`, `README.md`, `docs/x.md`, a delete outside; a glob entry `src/**` lets `src/a/b.py` through; reviewer, planner and scenario agent unchanged |
| CB-2 | integration | a real `RunContext` with session isolation on (settings list with a glob) and off (derived) → `task_files` → the dispatcher → the tool |
| CB-2 | e2e, `xfail(strict=True)` naming `C-FLOW-11` | `sw run` with an `agentic` generate step: the coder's write to `README.md` is refused, its write to `src/greeter.py` lands — no production path gives the coder tools yet |
| CB-3 | unit | `GraphContext` has no `workspace_roots`; mention lookup still finds files under the project root |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `unknown-role-gets-full` | the no-rule branch returns FULL on the roots | CB-1 |
| `task-grant-everywhere` | the task grant matches every path | CB-1 |
| `readme-writable` | the `README.md` / `docs/` exclusion | CB-1 |
| `glob-not-matched` | the shared matcher compares text, not globs | CB-1 |
| `dotdot-entry-accepted` | the NFR-2 check | CB-1 |
| `isolation-off-no-files` | `task_files` falls back to nothing | CB-2 |
| `settings-list-ignored` | `task_files` always derives | CB-2 |
| `root-not-the-project` | a boundary's root is the spec's folder | CB-3 |

## Research Notes

- `_compute_role_grants(role, boundary)` (`dispatcher.py:163-193`): `scenario_agent` READ on
  `specs/`, `contracts/`; `_READ_ONLY_ROLES` READ on roots and API paths; else FULL on roots.
- `create_standard_set(boundary, role, allowed_tools, analyzer_factory, topology, parsers, search_key)`
  (`dispatcher.py:110`); callers in `src`: `handlers/review.py:59`, `handlers/scenario.py:31`.
- `grant_mode_for(normalized_path, grants, cwd)` returns the most permissive covering grant
  (`security.py:189-213`); `CodeStructureTool` refuses create and delete below FULL
  (`code_structure/interfaces/tool.py:343,365`).
- `path_allowed(path, patterns)` refuses `..` and matches globs (`worktree_ops.py:125-139`); the
  merge also always strips `README.md` and `docs/` (`:155`).
- `apply_session_policy` fills `allowed_paths` only with session isolation on, from
  `[sandbox] session_allowed_paths` (verbatim) or `derive_allowed_paths` (`isolation.py:103-148`).
- `AgentRuntime` / the work unit take a dispatcher (`core/flow/engine/work_unit.py:70-105`); no
  handler in `src` builds one for the coder.
- Tests that rely on the old FULL default: `tests/unit/sandbox/test_read_only_role_grants.py`
  (`test_the_implementer_keeps_full_access`) and any test building a dispatcher for another role;
  they are rewritten to the new rules.

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | The task grant and `README.md` / `docs/`, which the merge always strips | refused, as the merge strips them; `doc_updates.md` allowed, as the merge keeps it `[agreed 2026-10-16]` |
| Q2 | Each project chooses its protected docs, not code | parked for the laptop: one settings line does not cover per-role, per-task or generated-block rules `[agreed 2026-10-16]` |

## Backlog

none
