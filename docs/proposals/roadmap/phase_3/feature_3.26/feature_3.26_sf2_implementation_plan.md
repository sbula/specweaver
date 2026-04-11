# Implementation Plan: Git Worktree Bouncer (Sandbox) [SF-2: Worktree Sync & Conflict Handling]
- **Feature ID**: 3.26
- **Sub-Feature**: SF-2 — Worktree Sync & Conflict Handling (Orchestrator)
- **Design Document**: docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-2
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3.26/feature_3.26_sf2_implementation_plan.md
- **Status**: DRAFT

## Scope
Implements mathematical diff striping against `context.yaml`, dictatorial "Main Branch Wins" sync resolution, proactive micro-syncs (`git rebase main`), and isolated documentation claims for the orchestrator layer.

## Research Notes
- `PipelineRunner` (`src/specweaver/flow/runner.py`) uses a `StepHandlerRegistry` (in `src/specweaver/flow/handlers.py`) to execute pipeline steps.
- We must wrap `generate+code` internally, either by injecting logic into `PipelineRunner._execute_loop`, creating a new `GitBouncerHandler` decorator in the registry, or updating `GenerateCodeHandler` to spin up its operations inside the `GitAtom` using `_intent_worktree_add` and `_intent_worktree_teardown`.

## Sub-Feature Implementation Details (Draft)
*To be filled out after resolving the Phase 4 Audit Qs.*
