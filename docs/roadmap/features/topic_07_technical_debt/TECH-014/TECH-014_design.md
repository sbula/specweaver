# Design: Fan-Out RunContext Isolation (Concurrent Sub-Run State Corruption)

- **Feature ID**: TECH-014
- **Epic**: Topic 07 (Technical Debt)
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: Found during INT-US-21 SF-01 CB-2's pre-commit Phase-2 HITL gate (2026-07-25).

## Problem Statement

`OrchestrateComponentsHandler` hands **the same `RunContext` object** to every concurrent
sub-runner (`core/flow/handlers/decompose.py`, `context=context.pipeline_runner._context`), while
`PipelineRunner._execute_loop` writes `run_id`, `step_records` and `pipeline_runner` onto that
context on **every step** (`core/flow/engine/runner.py`, the context-injection block before handler
execution).

With N sub-runs executing concurrently those writes interleave, so a sub-run can observe another
sub-run's `run_id`. **Lineage and telemetry events are therefore attributable to the wrong sub-run
today**, and `step_records` (consumed by handover persistence) is likewise corruptible.

This is a defect in **shipped** code — `C-FLOW-03` (Multi-Spec Fan-Out) is ✅ delivered — not a
missing capability. It is live now, independent of INT-US-21.

## What INT-US-21 did and did not do

INT-US-21 FR-2 added a runner hook that writes `context.plan` / `context.decomposition` at the same
shared object, which **widened the blast radius** to the plan fields. It did **not** create the
defect: `run_id` / `step_records` / `pipeline_runner` were already racing before FR-2 existed.

## Why this is NOT deferred to `C-FLOW-12` / `INT-US-21-SF02`

Considered and explicitly rejected during INT-US-21's CB-2 pre-commit (user decision, 2026-07-25):

1. The add-on is about autonomous DAG *execution* and per-component DAL isolation. Basic context
   hygiene is something it should be able to **assume**, not own.
2. `C-FLOW-12` is unbuilt and sequenced behind `C-EXEC-07`, so gating a live shipped-code defect on
   it would leave corrupt telemetry in place indefinitely.
3. Per the finished-stories-immutable rule, a defect in a delivered story becomes a new story or a
   TECH ticket — never an edit to the delivered entry.

**Should land before `C-FLOW-12`.**

## Candidate Approaches (not yet designed)

1. **Derived per-sub-run context** — give each sub-runner its own context (a copy with sub-run
   identity applied) at the fan-out boundary. Cheapest to reason about; needs care over which
   fields are legitimately shared (settings, adapters) versus per-run (identity, records).
2. **Thread run-scoped state through the call instead of the context** — stop writing `run_id` /
   `step_records` onto `RunContext` at all; pass them as explicit arguments to the handler call.
   Architecturally cleaner and removes the shared-mutable-state class of bug outright, but touches
   every handler signature. Overlaps `TECH-007`'s RunContext god-object finding.
3. **Make the shared identity fields immutable per run** — freeze them after construction so an
   interleaved write fails loudly instead of silently corrupting. A detection mechanism rather than
   a fix; possibly a useful first step.

## Non-Goals (proposed, pending design)

- Redesigning fan-out concurrency or its loop/error bounds (a documented DMZ — see
  `pipeline_engine_guide.md`).
- Per-component DAL-scoped isolation — that is `C-FLOW-12` / `C-EXEC-07` territory.

## Verification the design must specify

A concurrency test asserting **per-sub-run `run_id` attribution** in emitted lineage/telemetry
events. The current defect is invisible to every existing test because nothing runs two sub-runs
concurrently and then checks which run each event was recorded against.

## Next Step

Run the `specweaver-design` skill against this stub before any implementation.
