# Design: Autonomous DAG Execution (Decompose → Orchestrate)

- **Feature ID**: C-FLOW-12
- **Topic**: 03 (Flow Engine)
- **DAL**: C
- **Status**: STUB — not yet run through the `specweaver-design` skill
- **Origin**: INT-US-21 `AD-4` (user mandate, 2026-07-24) — minted at epic closure, 2026-07-28

## Problem Statement

`INT-US-21` delivers the decomposition *journey*: a feature spec becomes a reviewed
`DecompositionPlan`, a durable `<stem>_decomposition.yaml`, and one stub component spec per node.
It deliberately stops there. **Executing** that DAG — building each component — was never built by
anybody, and `AD-4` split it out rather than let the base contract claim capability it did not have.

What is missing:

- **Per-component spec synthesis.** The base writes *stubs*. Something must turn a stub into a real
  component spec before its sub-run can do useful work.
- **Race-hardened fan-out.** `OrchestrateComponentsHandler` hands the **same mutable `RunContext`**
  to every concurrent sub-runner. Latent today because nothing exercises it; `TECH-014` owns the
  fix and **must land first**.
- **`proposed_dal`-driven isolation.** Each component carries a DAL rating that should drive its
  sub-run's execution posture. The base guarantees the *data* contract only; escalation is
  `C-EXEC-07` / `INT-US-09-SF06`.

## Functional Requirements

Added 2026-08-13 (`TECH-046`). `C-INTL-01`'s `FR-3` — *"Component Fan-out: automatically spawns a
sub-pipeline iteration (generate Component Spec) for each approved component; N individual L3
pipelines are launched"* — was descoped there because it was never built and the work belongs here.

**That descope is only honest if the requirement is re-stated at its new owner.** It was not: this
design described the work in prose and declared no requirements, so deleting the row would have
turned a testable claim into a mention. `FR-1` below is that requirement, carried across.

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Component Fan-out | System | Spawn a sub-run per approved component in the `DecompositionPlan` | One sub-run per node, launched from the persisted plan rather than re-derived. |
| FR-2 | Per-component spec synthesis | System | Turn each never-overwritten stub component spec into a real one | A stub becomes a spec its sub-run can act on; a hand-authored spec is left untouched. |
| FR-3 | Race-hardened fan-out | System | Give each concurrent sub-run its own `RunContext` | Concurrent sub-runs cannot corrupt each other's state or mis-attribute telemetry (`TECH-014`'s fix, exercised for the first time). |
| FR-4 | DAL-driven isolation | System | Apply each component's `proposed_dal` to its sub-run's execution posture | A component rated at or above the escalation threshold runs isolated; below it, on host. |

## Seams the base already froze

These are defined and tested as they stand, so this capability builds on them rather than
renegotiating them:

| Seam | Where |
|---|---|
| `context.decomposition` — canonical `DecompositionPlan` JSON, one shared constant `DECOMPOSITION_PLAN_KEY` | `engine/hydration.py` |
| `<stem>_decomposition.yaml` schema, `model_dump(mode="json")`, uuid-tagged | `handlers/decomposition_artifacts.py` |
| Stub component spec paths, never-overwrite, five-bucket report | same |
| `proposed_dal` present on every component | `DecompositionPlan` |
| Approve-on-resume, engine-wide | `engine/approval.py` |

> **"Frozen" means defined and tested as it stands — NOT that the base ships a forward-compatibility
> pin for this consumer.** INT-US-21's `FR-9(a)` attempted exactly that and was descoped on
> 2026-07-26: a regression pin written against an undesigned consumer freezes a guess. **This
> capability writes its own seam pin as its first commit**, against a contract it can actually see.

## Non-Goals (proposed, pending design)

- Not the decomposition journey itself — that is `INT-US-21`, delivered.
- Not DAL escalation policy (`C-EXEC-07`).
- Not the fan-out `RunContext` race (`TECH-014`) — a prerequisite, not scope.

## Sequencing

Behind **`C-EXEC-07`** (per-run isolation posture) and **`TECH-014`** (the shared-context race).
`TECH-020` should also land first if it is going to: this capability touches `runner.py`'s
execution loop, which is at its 600-line threshold with a 360-line method.

## Next Step

Run the `specweaver-design` skill. The integration contract for this capability is
`INT-US-21-SF02`, already minted in `US-21_integration.md` as Pending Design.
