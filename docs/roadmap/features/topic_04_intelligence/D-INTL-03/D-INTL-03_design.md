# D-INTL-03 — Explicit Plan Phase

**Status**: ✅ Finished — signed off by the user 2026-10-13. · **Phase**: 3 (Feature 3.6)

| | |
|---|---|
| Touches | `workflows/pipelines/new_feature.yaml` · `core/flow/handlers/generation.py` (`PlanSpecHandler`) · `workflows/planning/` |
| Plan | [as built](D-INTL-03_implementation_plan.md) |

## What it does

Before any code is written, the model decides the file layout, stack, constraints and tasks for
the spec, and SpecWeaver saves that as `<spec>_plan.yaml` beside the spec. The code and test steps
then get the plan in their prompt. `new_feature` runs it after the spec review `[agreed 2026-10-13]`,
without stopping for approval: the plan is on the record, and the path is in the run's output
`[agreed 2026-10-13]`.

UI mockups (Google Stitch) are not part of this: the old code returned a placeholder link and made
no call, so it is removed `[agreed 2026-10-13]`. Real Stitch, with its key in `keys.env`, is a later
item.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Plan before code | `new_feature` pipeline | SHALL run the plan step after the spec review and before every code step | no code is written without a decided plan |
| FR-2 | Plan on the record | Plan step, code step | SHALL save the plan as `<spec>_plan.yaml` beside the spec, and give its file layout to the code prompt | the code follows a plan a person can read |
| FR-3 | No plan, no code | Plan step | SHALL fail the step, writing no plan file, when the model returns no valid plan after its retries | a run never writes code against a guess |

## Live demo

`tests/e2e/capabilities/workflows/test_plan_before_code_e2e.py`, real `sw run`: a plan-then-code
pipeline saves `greeter_spec_plan.yaml`, and the code prompt carries its file layout; with no valid
plan the run fails and no code prompt is sent.
