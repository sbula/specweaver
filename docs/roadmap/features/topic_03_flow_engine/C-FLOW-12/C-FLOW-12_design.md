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
