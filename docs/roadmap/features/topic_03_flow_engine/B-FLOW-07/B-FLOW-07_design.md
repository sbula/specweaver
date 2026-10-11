# Design: Step Limits from History

- **Feature ID**: B-FLOW-07
- **Phase**: Topic 03 (Flow Engine) · DAL-B (High-Assurance)
- **Status**: ✅ Finished — signed off by the user 2026-10-11. Proven live every night.
- **Story**: `US-4` add-on *Security Defenses* — paths in [US-04.md](../../../stories/US-04.md#step-limits-b-flow-07)
- **Decisions**: [limits_matrix_grilling_2026-10-08.md](../../../../analysis/limits_matrix_grilling_2026-10-08.md);
  research: [effort_indicators_2026-10-08.md](../../../../analysis/effort_indicators_2026-10-08.md)
- **Plans**: [SF-01](B-FLOW-07_sf01_implementation_plan.md), [SF-02](B-FLOW-07_sf02_implementation_plan.md)

## Feature Overview

`B-FLOW-07` adds a **step limit** to the spend brake (`B-FLOW-05`): the most one step may spend,
taken from what similar steps really cost before. Similar means the same kind of task, the same
model and the same DAL `[agreed 2026-10-08]`, because a higher DAL demands more work — DO-178C asks
71 objectives at level A and 26 at level D. The run and model limits stay as they are.

It does **not** read the task's text: a vague task must not look easy `[agreed 2026-10-08]`. History
is the strongest indicator text cannot move; a model's own forecast of its cost is weak and low.

It is deliberately lean `[agreed 2026-10-08]`: no base per DAL, no time window, no footprint.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Each call says where it ran and for what | Telemetry | SHALL store, with every call, the server's name, the run's DAL and the step's name — passed from the run through `llm_for` (**seam**: `core.flow` → `infrastructure.llm`) | the history can group by task, model and DAL, and spend splits by server |
| FR-2 | Each call knows how its step ended | Runner, telemetry | SHALL store, when a run's records are written, each step's outcome — `passed` or `failed`, none while unfinished — from the run's step records; a review that returned its verdict, accepted or denied, is `passed` `[agreed 2026-10-11]`; one row per step that its calls join (**seam**: runner → telemetry) | only finished work counts as history |
| FR-3 | Every target has a DAL | Runner, validation | SHALL take the run's DAL from the nearest `context.yaml`, else from the project's default DAL, else `DAL_C` for a folder outside every project `[agreed 2026-10-11]` — the same rule validation uses; a project's default DAL is `DAL_C` `[agreed 2026-10-08]` (**seam**: workspace project store) | the history and validation agree on a target's DAL |
| FR-4 | A step limit from history | Brake | SHALL set a step's limit, before its first call, to the `[step_limits] percentile` value of the totals of the last `min_steps` **passed** steps with the same kind of task, model and DAL, across all projects on the machine `[agreed 2026-10-08]`, each total counting all the step's attempts — money for a hosted server, tokens for a private one; the percentile by nearest rank. A step with an unpriced call is left out of a money history; a total of 0 gives no limit; without a database there are no step limits | a step that costs far more than its kind usually does is stopped early |
| FR-5 | No history, no step limit | Brake | SHALL set no step limit while a group has fewer than `min_steps` passed steps; the run and model limits still apply `[agreed 2026-10-08]` | a new kind of work is never stopped by a guess |
| FR-6 | The step limit behaves like every limit | Brake, runner | SHALL treat the step limit as one more limit of the call, checked against what the step has really spent, not against the next call's worst case `[agreed 2026-10-08]`: once a step has spent its limit, its next call pauses and asks; "yes" raises it by its own size; "no" or no terminal parks the run | one behaviour for all limits |
| FR-7 | One step, one limit | Brake | SHALL count every attempt of a step against the same step limit, and give each sub-run its own | a retry cannot reset the limit; sub-runs do not share one |
| FR-8 | Settings in the machine file | Settings | SHALL read `[step_limits] percentile` (1–100) and `min_steps` (≥ 1) from the machine `settings.toml` only, with no value in code; a project file that sets them is refused `[agreed 2026-10-08]` | a cloned repository cannot change the user's limits |
| FR-9 | Off when not set | Settings, brake | SHALL apply no step limits when `[step_limits]` is missing, and `sw config show` SHALL say so; when set, it shows each value with its line `[agreed 2026-10-08]` | the feature is opt-in and visible |
| FR-10 | The database keeps its data | Bootstrap | SHALL add the new columns to an existing database without converting or deleting a row; a row without them is "unknown" and never part of the history; existing projects' default DAL becomes `DAL_C` once `[agreed 2026-10-08]` | no user data is lost |
| FR-11 | Spend by server | `sw costs` | SHALL show this month's spend per model **and server** | the same model on the GB10 and on DashScope is no longer mixed |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface |
|---|---|---|
| FR-1 | server, DAL, step per call | `llm_for(context, task_type)` stamps the config; `TelemetryCollector` builds the record |
| FR-2 | step outcomes | `step_outcomes(run)` → `record_step_outcomes(db, run_id, outcomes)` at the run's flush |
| FR-3 | a target's DAL | `target_dal(context, path)`: `DALResolver.resolve`, `default_dal_at(db, root)`, `DEFAULT_DAL` |
| FR-4, FR-5 | past step totals | `step_history_limit(db, task_type, model, dal_level, unit, steps, percentile)` |
| FR-6, FR-7 | a step's limit in the call's scope | `RoleResolver._step_limit` → `Limit(..., on_spent=True)`; `SpendBudget.before_call` |
| FR-8, FR-9 | `[step_limits]` | `StepLimits` in `MachineLlmFile`; `settings_report` |
| FR-10 | the schema | `bootstrap_database` (`_add_history_columns`, `_move_default_dal_once`) |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Cheap | The history is read once per run and group, not once per call; one indexed query |
| NFR-2 | No limit in code | No percentile, count or amount in `src/` `[agreed 2026-10-03]` |
| NFR-3 | Not gameable | No input to the step limit comes from the task's text `[agreed 2026-10-08]` |

## Live demo

With `[step_limits] percentile = 90` and `min_steps = 2` and a real Gemini server: run `sw review
<spec>` twice; the database then holds both calls with server, DAL and step, and both steps
`passed`; the next review of the same task, model and DAL gets a step limit from their real costs.
The nightly live run (`scripts/live.py`) checks exactly this.

## Architectural Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| AD-1 | The step limit is worked out in `RoleResolver._step_limit`, from the step and DAL `llm_for` stamps on the call's config, cached per run and group | the resolver knows the unit and holds the settings; the brake stays free of database access |
| AD-2 | The history is read with `Database.connect()` (sync sqlite) | `llm_for` is sync and runs inside the event loop |
| AD-3 | The new columns are added by `bootstrap_database`; `projects.default_dal` moves from `DAL_A` to `DAL_C` once, guarded by a marker | this table's schema lives there; no user held a deliberately set DAL |
| AD-4 | The step's limit key carries the run and the step, so retries share it and sub-runs do not | FR-7 |

## Accepted limits

- Validation is less strict for projects that declare no DAL (`DAL_A` → `DAL_C`) `[agreed 2026-10-08]`.
- Over REST nobody can answer, so a run parked at a step limit parks again on each REST resume; the
  park message says to resume it from a terminal or change `[step_limits]`.

## Non-Goals

- A footprint from the graph, a base per DAL, a time window — cut for now `[agreed 2026-10-08]`.
- Exact tiered prices — the highest-price rule stays `[agreed 2026-10-08]`.
- Choosing or comparing models — `A-FLOW-01`.
- Loop detection — `B-FLOW-06`.
- Reading anything from the task's text `[agreed 2026-10-08]`.

## Sub-Features

| SF | Scope | FRs | Plan | Committed |
|----|-------|-----|------|-----------|
| SF-01 | The history: server, DAL, step and outcome per call; every target has a DAL; `sw costs` by server | FR-1, FR-2, FR-3, FR-10, FR-11 | [sf01](B-FLOW-07_sf01_implementation_plan.md) | ✅ |
| SF-02 | Step limits from the history, in the brake, with their settings | FR-4, FR-5, FR-6, FR-7, FR-8, FR-9 | [sf02](B-FLOW-07_sf02_implementation_plan.md) | ✅ |
