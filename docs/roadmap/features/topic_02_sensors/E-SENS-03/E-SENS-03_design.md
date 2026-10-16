# E-SENS-03 — Workspace Boundaries

**Status**: APPROVED by the user 2026-10-16 — backfilled for a repair; the capability is `🔧` until the
repair is proven and signed off. · **Feature ID**: E-SENS-03 · **DAL**: E (its matrix row) ·
**Epic**: Topic 02 (Sensors)

| | |
|---|---|
| Stories | `US-5` Core |
| Consumes | `D-EXEC-02` / `C-EXEC-06` the task's allowed paths (`core/flow/engine/isolation.py`) · `E-SENS-01` the grant matcher (`sandbox/security.py`) |
| Enables | `C-FLOW-11` an agentic coder's tools · `B-EXEC-02` tiered access · `C-EXEC-02` the script-folder grant |
| Not touched | what an agent may read (`B-FLOW-04` owes it) · wiring the coder's tools (`C-FLOW-11`) · non-Python file names (`TECH-073`) |

## Feature Overview

E-SENS-03 decides what each agent role may do to the files of a project. The roadmap's done-when —
*an agent's grant is built from its task and refuses everything outside it* — was false when this
design was written: no grant was built from a task, and any role without its own rule got FULL
access to the whole project. The reviewer and planner were narrowed to read-only on 2026-10-08
(`edcedf16`). This design limits **writes** to the task: an agent may create and change only its
own task's files, while reading stays project-wide, so a reviewer can still find specs that
contradict each other `[agreed 2026-10-16]`. Narrowing reads is owed by `B-FLOW-04`, after the
graph closure over its candidates (`ADR-006`) `[agreed 2026-10-16]`.

The name was *Context Ledgers & Workspace Boundaries*; nothing in the code or the docs said what a
context ledger is, so it is out of scope and out of the name `[agreed 2026-10-16]`.

## Research Findings

| Fact (2026-10-16) | Where |
|---|---|
| Every grant an agent gets comes from one function, by role; every grant is recursive | `sandbox/dispatcher.py:163-193` `_compute_role_grants` |
| reviewer, planner, arbiter: READ on the project; scenario agent: READ on `specs/`, `contracts/` | `dispatcher.py:23`, `:171-188` |
| Any other role: FULL on every root | `dispatcher.py:190-193` |
| Only the reviewer, planner and scenario agent get a dispatcher; the coder, drafter and lint-fix get none | `handlers/review.py:59`, `handlers/scenario.py:31` |
| The file tool reads only (`b411cdd2`); the code-structure tool keeps write, create and delete intents | `sandbox/code_structure/interfaces/tool.py:247-300` |
| Levels stack: READ reads; WRITE also changes an existing file; FULL also creates and deletes | `sandbox/security.py:22-36` |
| A grant on one file matches that file (`recursive=False`) | `security.py:216-228` `_path_under_grant` |
| `allowed_paths` is filled only when session isolation is on: `[sandbox] session_allowed_paths`, else `src/<stem>.py`, `tests/test_<stem>.py` | `core/flow/engine/isolation.py:40-58`, `:103-148` |
| `GraphContext.workspace_roots` is written by nothing; three readers fall back to the project root | `handlers/run_context.py:124`, `security.py:129`, `review.py:95,348` |

## Paths

| # | Path | Crosses |
|---|---|---|
| P1 | an agent with the coder's role → it creates and changes its task's files | `core.flow.engine.isolation` |
| P2 | the same agent → a write, create or delete outside its task is refused | `sandbox.code_structure` |
| P3 | session isolation on → its allowed paths are the task's files; off → the same paths, from the spec | `D-EXEC-02` / `C-EXEC-06` |
| P4 | a role with no rule → every tool call on a file is refused | `sandbox` |
| P5 | reviewer, planner, scenario agent → their grants stay as they are | `E-SENS-01` |

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | The task's files | Flow engine | SHALL name a task's files as the run's `allowed_paths` when session isolation set them, else as `derive_allowed_paths(spec)` — one rule with isolation on or off `[agreed 2026-10-16]` | the grant and the merge filter agree on what a task may write |
| FR-2 | The coder's grant | Dispatcher | SHALL give the `implementer` role FULL on each of its task's files and READ on the project and the API paths `[agreed 2026-10-16]` | it can start a new module and touch nothing else |
| FR-3 | Writes outside the task are refused | Agent tools | A write, create or delete outside the task's files SHALL be refused by the tool, with the path named | a stray write never reaches the worktree |
| FR-4 | No rule, no grant | Dispatcher | A role with no rule of its own SHALL get no grant, so every file call is refused `[agreed 2026-10-16]` | a new role starts closed, never with FULL access |
| FR-5 | One source of roots | Run context | `GraphContext.workspace_roots` SHALL be removed; boundaries and mention lookup use the project root `[agreed 2026-10-16]` | no field claims a scope nothing sets |

`WRITE` (read and change, never create or delete) has no role today. It stays in the model for
edit-only roles — lint-fix, review fixes — for `C-FLOW-11` to choose when it gives them tools.

## Requirement–Surface Bindings

| FR | Binds to | Verified how |
|---|---|---|
| FR-1 | `RunContext.isolation.allowed_paths`, `derive_allowed_paths(spec_path)` | read `core/flow/engine/isolation.py:40-58,103-148` |
| FR-2, FR-4 | `ToolDispatcher._compute_role_grants(role, boundary)`, `create_standard_set(...)` | read `sandbox/dispatcher.py:110-193` |
| FR-3 | `CodeStructureTool` write/create/delete checks through `grant_mode_for` | read `sandbox/code_structure/interfaces/tool.py:247-300`, `security.py:189-228` |
| FR-5 | `GraphContext`, `WorkspaceBoundary.from_run_context`, `_resolve_mentions` | read `run_context.py:114-125`, `security.py:126-138`, `review.py:95,348,369` |

`sandbox` may not import `core.flow`: the task's files are computed in the flow engine and handed to
the dispatcher as repo-relative paths. The dispatcher joins them to the boundary's root — inside a
session that root is the worktree, so the grant names the worktree's files, never the real tree's.

## Non-Functional Requirements

| # | NFR | Rule |
|---|---|---|
| NFR-1 | Fail closed | No grant, an empty task list, or a grant that cannot be built SHALL refuse writes, never allow them |
| NFR-2 | Paths escape nothing | A task path with `..` or outside the project SHALL be refused when the grant is built |

## Architectural Decisions

| # | Decision | Why | Switch? |
|---|---|---|---|
| AD-1 | Writes are task-scoped; reads stay project-wide `[agreed 2026-10-16]` | a reviewer needs other specs to find contradictions | Yes — the done-when changes to *an agent's write grant is built from its task* |
| AD-2 | One list of task files, shared with the worktree merge `[agreed 2026-10-16]` | two lists drift apart | No |

## Sub-Feature Breakdown

Single feature — no decomposition.

## Execution Order

Single feature — no decomposition. `TECH-073` may land before or after; both read the one list.

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| — | Workspace Boundaries | — | ✅ | ✅ | ⬜ | ⬜ | ⬜ |

## Session Handoff

**Now**: design approved 2026-10-16, from the grilling's Q1–Q8.
**Next**: dev, CB-3 removes `workspace_roots` ([plan](E-SENS-03_implementation_plan.md)).
