# Implementation Plan: Scenario Testing [SF-E: Memory and coverage apart]
- **Feature ID**: B-FLOW-01
- **Sub-Feature**: SF-E — Memory and coverage apart
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_design.md
- **Design Section**: §Sub-features → SF-E
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-01/B-FLOW-01_sfe_implementation_plan.md
- **Status**: APPROVED by the user 2026-10-15

**FRs owned**: FR-12, FR-13 · **Depends on**: none (SF-D committed) · **Paths**: US-24 P-5, P-6

## Goal

A dual run's memory never reaches a coder prompt, and no coder text reaches the scenario side. The
coder's C09 counts only the coder's tests, and the person sees, per requirement, which side covers it.

## Shape

| Piece | Where |
|---|---|
| the dual handler marks the run that holds it: `RunHandle.dual_side = "parent"` | `core/flow/handlers/dual_pipeline.py` |
| a dual run's handover goes to the scenario store, never to task memory (see Q1) | `core/flow/engine/handover.py` |
| a guard: the scenario generator's prompt has no memory slot | test only |
| C09 counts the project's tests only; the store is outside the project | test only (proven by SF-D's move) |
| per requirement: `both`, `coder`, `scenario`, `none` — from the spec's ids, the project's traces and the store's traces (see Q2 for where it shows) | `core/flow/handlers/validation.py` (the `kind: scenario` step) |

## Commit boundaries

| CB | Does | Proves | Red first |
|---|---|---|---|
| CB-1 | the parent mark; the dual handover to the store; the generator guard | FR-12 | a failed dual run's handover reaches the task memory a coder prompt reads, with `scenario_integration` and arbiter text in it — red today |
| CB-2 | the coverage report; C09 over the project only | FR-13 | the scenario step reports no coverage — red today; a requirement only a scenario test covers is uncovered in the coder's C09 |

## Mutants

| id | Line neutralised | Must kill |
|---|---|---|
| `dual-handover-to-memory` | the branch that sends a dual run's handover to the store | CB-1 |
| `parent-unmarked` | the dual handler's parent mark | CB-1 |
| `coverage-sides-swapped` | which traces count as the coder's | CB-2 |

## Research Notes

- `save_handover_context(context, run)` skips sub-runs (`run.parent_run_id is not None`), so only
  the top-level dual run writes one; its errors carry `"Arbiter assigned: …"` and
  `"Scenario pipeline failed: …"` (`core/flow/engine/handover.py:17-110`).
- Memory enters a prompt through `PromptSlot.AGENT_MEMORY` (`core/flow/handlers/prompting.py:63-80`);
  the scenario generator builds its own prompt without it (`workflows/scenarios/scenario_generator.py`).
- `step_records` reach the CLI display, resume, telemetry and the arbiter, but no coder prompt.
- C09 reads requirement ids from `specs/**/*.md` and traces through
  `extract_test_mapped_requirements(project_root)` (`assurance/validation/rules/code/c09_traceability.py`).

## Decisions (audit)

| # | Question | Chosen |
|---|----------|--------|
| Q1 | Where a dual run's handover goes | one file per run in the scenario store, `<store>/handovers/<run id>.json`; task memory gets nothing from a dual run — even the pipeline's name would tell the coder a scenario side exists `[agreed 2026-10-15]` |
| Q2 | Where the coverage report shows | a short table at the end of `sw run`, and in the run record `[agreed 2026-10-15]` |

## Backlog

none
