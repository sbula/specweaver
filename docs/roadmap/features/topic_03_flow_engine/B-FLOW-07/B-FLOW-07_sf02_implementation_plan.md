# Implementation Plan: Spend Limit Matrix (Model × Task × DAL) [SF-02: Step limits]
- **Feature ID**: B-FLOW-07
- **Sub-Feature**: SF-02 — Step limits
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-07/B-FLOW-07_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-02
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-07/B-FLOW-07_sf02_implementation_plan.md
- **Status**: DRAFT

## Scope

FR-4 to FR-9. Paths L1, L2, L5 (`US-04.md`). Builds on SF-01's history.

## Research Notes (cited, read 2026-10-08)

- History rows: `llm_usage_log` (`task_type`, `model`, `dal_level`, `step_name`, `run_id`,
  `total_tokens`, `estimated_cost`, `timestamp`) joined with `llm_step_outcome`
  (`run_id`, `step_name`, `outcome`) — `infrastructure/llm/store.py`.
- `llm_for(context, task_type)` stamps `task_type`, `run_id`, `dal_level`, `step_name` on the
  call's config (`core/flow/handlers/_llm.py`).
- `RoleResolver._scope(server_name, config) -> CallScope` builds the call's limits, in tokens for
  a private server and USD for a hosted one (`infrastructure/llm/resolve.py`).
- `SpendBudget.before_call` asks or stops at any limit; "yes" raises it by its own size
  (`infrastructure/llm/budget.py`).
- `MachineLlmFile` is strict (`extra="forbid"`); `settings_report(files, roles, role_rows)`
  builds `sw config show` (`core/config/llm_settings.py`).

## Findings settled here

1. **The history is read where the limits are built**, in `RoleResolver._scope`, not in
   `llm_for`: the resolver already knows the server's unit, holds the settings, and is built once
   per command. `llm_for` only stamps; the design's AD-1 aim (the brake reads no database per
   call) holds, because the value is cached per run and group.
2. **The resolver gets the database** through `build_router(..., db=...)`. Without one (some
   tests, the REST helpers that pass none) there are no step limits, as with a missing
   `[step_limits]`.
3. **A step's limit key names it for the user**: `step_limits.<task>.<step>`, kept apart per run
   in the budget, so retries share it and sub-runs do not (FR-7).
4. **A step whose calls include an unpriced one is left out of a money history**: its money
   total is not known.

## Commit Boundaries

### CB-1 — The settings (FR-8, FR-9 display; path L5)

Tests first:
- unit: `[step_limits] percentile = 90, min_steps = 10` parses; `percentile = 0`, `101`,
  `min_steps = 0` are refused naming the line; `[llm.step_limits]` in a project file is refused.
- e2e L5: `sw config show` shows both values with their lines; without the section it shows
  "step limits are off — `[step_limits]` is not set".

Mutants: range checks dropped; the "off" row dropped.

### CB-2 — The limit from the history (FR-4, FR-5)

Tests first:
- unit: nearest-rank percentile of known lists.
- integration (real database): 10 passed steps of one group → the 90% value, in tokens and in
  USD; 9 passed steps → none; failed steps, other DALs, other models are ignored; the 10 newest
  are used when there are more.

Mutants: failed steps counted; group key without DAL; oldest instead of newest; `min_steps`
ignored.

### CB-3 — The step limit in the brake (FR-6, FR-7, FR-9 off; paths L1, L2)

Tests first:
- integration: a step whose next call would cross its step limit → the run parks without a
  terminal, naming `step_limits.<task>.<step>`; a retry of the step counts against the same limit.
- e2e L1: `sw implement` with a history of 10 passed steps for its group and a fake model whose
  reply crosses the 90% value → the run stops at the step limit; answered "yes" → it goes on.
- e2e L2: the same with 9 steps in the history → no step limit; the run finishes.

Mutants: step limit not added to the scope; key without the step (retries and steps share);
history read per call instead of cached.

## Out of scope

The footprint, a base per DAL, a time window — cut by the design.
