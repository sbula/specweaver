# Design: Spend Limit Matrix (Model × Task × DAL)

- **Feature ID**: B-FLOW-07
- **Phase**: Topic 03 (Flow Engine) · DAL-B (High-Assurance)
- **Status**: APPROVED `[agreed 2026-10-08]` — the capability stays `🔜` until it is built and proven
- **Design Doc**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-07/B-FLOW-07_design.md
- **Story**: `US-4` add-on *Security Defenses* — paths in [US-04.md](../../../stories/US-04.md#step-limits-b-flow-07)
- **Decisions**: [limits_matrix_grilling_2026-10-08.md](../../../../analysis/limits_matrix_grilling_2026-10-08.md);
  research: [effort_indicators_2026-10-08.md](../../../../analysis/effort_indicators_2026-10-08.md)

## Feature Overview

`B-FLOW-07` adds a **step limit** to the spend brake: the most one step may spend, taken from what
similar steps really cost before. Similar means the same kind of task, the same model and the same
DAL `[agreed 2026-10-08]`, because a higher DAL demands more work — DO-178C asks 71 objectives at
level A and 26 at level D.

It solves a step that costs far more than its kind usually does, caught before the run limit would
catch it. It does not replace any limit: the run limit (`[brake]`), the model limit and the task
limit (`roles.<task>`) stay as they are `[agreed 2026-10-08]`.

It does **not** read the task's text: a vague task must not look easy `[agreed 2026-10-08]`. The
research found history the strongest indicator that text cannot move; the model's own forecast of
its cost is weak and always too low.

The design is deliberately lean `[agreed 2026-10-08]`: no base per DAL, no time window, no
footprint. Each can be added later if the history shows it is needed.

## Research Findings

### Codebase Patterns

- **Usage history exists.** `llm_usage_log` (`infrastructure/llm/store.py:20`) stores per call:
  project, `task_type`, model, `provider` (the server's kind), tokens, `estimated_cost` (USD,
  `None` when unpriced), duration, `run_id`. Missing for this feature: the server's name, the DAL,
  the step, and the step's outcome.
- **The run id reaches each call.** `llm_for(context, task_type)` (`core/flow/handlers/_llm.py:46`)
  stamps `task_type` and `run_id` on the call's `GenerationConfig`; the record copies `run_id`
  (`infrastructure/llm/telemetry.py:105`).
- **Records are written once, at the end of a run.** `flush_telemetry(context, logger)`
  (`core/flow/engine/telemetry.py`) runs from the runner's `_finalize`, when every step's outcome is
  known from `run.step_records`.
- **The schema is kept by the bootstrap, not by Alembic, for this table.** `bootstrap_database`
  (`core/config/bootstrap/db_bootstrap.py`) runs `create_all` and then repairs `llm_usage_log` in
  place (`_allow_unknown_cost`); new columns go there.
- **The run's DAL.** `seed_dal_level(context)` (`core/flow/engine/isolation.py`) resolves it from
  `context.yaml` through `DALResolver.resolve(target_path) -> DALLevel | None`, and stays `None`
  when nothing declares one. Validation instead falls back to the project's `default_dal`
  (`core/flow/handlers/validation.py:40`), stored per project with the column default `"DAL_A"`
  (`workspace/store.py:48`). No command sets it, so every project holds `DAL_A` only by default.
- **The brake.** A call's limits are a `CallScope` built by `RoleResolver._scope(server, config)`
  (`infrastructure/llm/resolve.py:186`): `Limit(key, unit, value)` for the run, the model and the
  task; `SpendBudget.before_call` asks or stops at any of them.
- **A sync database read exists.** `Database.connect() -> sqlite3.Connection`
  (`core/config/database.py:275`), so the history is read without entering the event loop.

### External Tools

None.

## Functional Requirements

| # | FR | Actor | Action | Outcome |
|---|-----|-------|--------|---------|
| FR-1 | Each call says where it ran and for what | Telemetry | SHALL store, with every call, the server's name, the run's DAL and the step's name — passed from the run through `llm_for` (**seam**: `core.flow` → `infrastructure.llm`) | the history can group by task, model and DAL, and spend splits by server |
| FR-2 | Each call knows how its step ended | Runner, telemetry | SHALL store, when a run's records are written, each step's outcome — `passed` or `failed`, none while unfinished — from the run's step records, one row per step that its calls join (**seam**: runner → telemetry) | only finished work counts as history |
| FR-3 | Every target has a DAL | Runner, validation | SHALL take the run's DAL from the nearest `context.yaml`, else from the project's default DAL, the same rule validation uses; a project's default DAL is `DAL_C` `[agreed 2026-10-08]` (**seam**: workspace project store) | the history and validation agree on a target's DAL |
| FR-4 | A step limit from history | Brake | SHALL set a step's limit, before its first call, to the `[step_limits] percentile` value (`[agreed 2026-10-08]`: 90) of the totals of the last `min_steps` (`[agreed 2026-10-08]`: 10) **passed** steps with the same kind of task, model and DAL, across all projects on the machine `[agreed 2026-10-08]`, each total counting all the step's attempts `[agreed 2026-10-08]` — money for a hosted server, tokens for a private one; the percentile by nearest rank | a step that costs far more than its kind usually does is stopped early |
| FR-5 | No history, no step limit | Brake | SHALL set no step limit while a group has fewer than `min_steps` passed steps; the run, model and task limits still apply `[agreed 2026-10-08]` | a new kind of work is never stopped by a guess |
| FR-6 | The step limit behaves like every limit | Brake, runner | SHALL treat the step limit as one more limit of the call, checked against what the step has really spent, not against the next call's worst case `[agreed 2026-10-08]`: once a step has spent its limit, its next call pauses and asks; "yes" raises it by its own size; "no" or no terminal parks the run `[agreed 2026-10-08]` | one behaviour for all limits, built in `B-FLOW-05` |
| FR-7 | One step, one limit | Brake | SHALL count every attempt of a step against the same step limit, and give each sub-run its own | a retry cannot reset the limit; sub-runs do not share one |
| FR-8 | Settings in the machine file | Settings | SHALL read `[step_limits] percentile` (1–100) and `min_steps` (≥ 1) from the machine `settings.toml` only, with no value in code; a project file that sets them is refused `[agreed 2026-10-08]` | a cloned repository cannot change the user's limits |
| FR-9 | Off when not set | Settings, brake | SHALL apply no step limits when `[step_limits]` is missing, and `sw config show` SHALL say so and why; when set, it shows each value with its line `[agreed 2026-10-08]` | the feature is opt-in and visible |
| FR-10 | The database keeps its data | Bootstrap | SHALL add the new columns to an existing database without converting or deleting a row; a row without them is "unknown" and never part of the history; existing projects' default DAL becomes `DAL_C` `[agreed 2026-10-08]` | no user data is lost |
| FR-11 | Spend by server | `sw costs` | SHALL show this month's spend per model **and server** (`C-FLOW-13` audit #18) | the same model on the GB10 and on DashScope is no longer mixed |

## Requirement–Surface Bindings

| FR | Data needed | Provider · surface | Verified how |
|---|---|---|---|
| FR-1 | server, DAL, step per call | `core.flow` · `llm_for(context, task_type) -> (adapter, GenerationConfig)` stamps the config; `TelemetryCollector._capture` builds the record | read `core/flow/handlers/_llm.py:46`, `infrastructure/llm/telemetry.py:85-110` |
| FR-2 | step outcomes | `D-FLOW-01` · `PipelineRun.step_records[*].status`, available in `_finalize` before `flush_telemetry` | read `core/flow/engine/runner.py` `_finalize`, `core/flow/engine/telemetry.py` |
| FR-3 | a target's DAL | `C-VAL-03` · `DALResolver.resolve(target_path) -> DALLevel \| None`; `workspace` · `WorkspaceRepository.get_default_dal(project_name) -> str` | read `core/config/dal_resolver.py:31`, `workspace/store.py:292` |
| FR-4, FR-5 | past step totals | `C-FLOW-01` · `llm_usage_log`, read through `Database.connect()` | read `infrastructure/llm/store.py:20`, `core/config/database.py:275` |
| FR-6, FR-7 | a step's limit in the call's scope | `B-FLOW-05` · `RoleResolver._scope(server, config) -> CallScope`; `SpendBudget.before_call` | read `infrastructure/llm/resolve.py:186`, `infrastructure/llm/budget.py` |
| FR-8, FR-9 | `[step_limits]` | `C-FLOW-13` · `MachineLlmFile`, `settings_report(files, roles, role_rows)` | read `core/config/llm_settings.py` |
| FR-10 | the schema | `bootstrap_database(db_path)` | read `core/config/bootstrap/db_bootstrap.py:57` |

## Non-Functional Requirements

| # | NFR | Threshold / Constraint |
|---|-----|----------------------|
| NFR-1 | Cheap | The history is read once per step, not once per call; one indexed query |
| NFR-2 | No limit in code | No percentile, count or amount in `src/` `[agreed 2026-10-03]` |
| NFR-3 | Not gameable | No input to the step limit comes from the task's text `[agreed 2026-10-08]` |

## External Dependencies

None.

## Architectural Decisions

| # | Decision | Rationale | Architectural Switch? |
|---|----------|-----------|----------------------|
| AD-1 | The step limit is worked out in `RoleResolver._scope`, from the step and DAL `llm_for` stamps on the call's config, and cached per run and group (changed at SF-02 planning, 2026-10-08: the resolver already knows the unit and holds the settings) | `llm_for` is where a step meets its model and already stamps run and task; the brake stays free of database access | No |
| AD-2 | The history is read with `Database.connect()` (sync sqlite) | `llm_for` is sync and runs inside the event loop; the async session would have to re-enter it | No |
| AD-3 | The new columns are added by `bootstrap_database`, like `_allow_unknown_cost`; `projects.default_dal` changes from `DAL_A` to `DAL_C` in the same place | this table's schema already lives there; no user holds a deliberately set DAL, since no command sets one | No |
| AD-4 | The step's limit key carries the run and the step, so retries share it and sub-runs do not | FR-7 | No |

## ROI Analysis

### Investment Cost
| Item | Effort | Risk |
|------|--------|------|
| Columns, outcome at flush, the DAL fallback | low | low |
| The history query and the step limit in the scope | medium | low — the brake's ask and park are reused |
| Settings, `sw config show`, `sw costs` by server | low | low |

### Returns
| Beneficiary | Benefit | Magnitude |
|-------------|---------|-----------|
| The user | a runaway step is stopped near what its kind usually costs, not only at the run limit | medium |
| `A-FLOW-01` | a cost history by task, model and DAL to compare models with | high |

### Risk Assessment
| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Early history is small and noisy | high | low | no limit below 10 steps; a "yes" raises the limit; the 90% value |
| A cheap simple task and a costly hard one share a group | medium | low | the limit is the 90% value of the group; the footprint (cut for now) is the known fix |
| Validation gets less strict for projects without a DAL (`DAL_A` → `DAL_C`) | certain | low | agreed `[2026-10-08]`; a project sets its own DAL in `context.yaml` |
| The DAL fallback changes session isolation for `sw implement` | low | low | it escalates at `DAL_B` and above; the fallback `DAL_C` is below it, as `None` was |
| Over REST nobody can answer, so a run parked at a step limit parks again on each REST resume | medium | low | the park message says to resume it from a terminal (`sw resume`) or change `[step_limits]`; a REST way to say yes is not built |

## Developer Guides Required

| Guide Topic | Description | Status |
|-------------|-------------|--------|
| `pipeline_engine_guide.md` | a handler gets its model through `llm_for`, which carries the step and DAL | ✅ Written 2026-10-08 |

## Non-Goals

- A footprint from the graph, a base per DAL, a time window — cut for now `[agreed 2026-10-08]`.
- Exact tiered prices — the highest-price rule stays (`C-FLOW-13` #22) `[agreed 2026-10-08]`.
- Choosing or comparing models — `A-FLOW-01`.
- Loop detection — `B-FLOW-06`.
- Reading anything from the task's text `[agreed 2026-10-08]`.

## Sub-Feature Breakdown

### SF-01: The history
- **Scope**: every call is stored with server, DAL, step and outcome; every target has a DAL;
  `sw costs` splits by server.
- **FRs**: [FR-1, FR-2, FR-3, FR-10, FR-11]
- **Inputs**: the run's context and step records; the project's default DAL
- **Outputs**: history rows that can be grouped by task, model and DAL
- **Depends on**: none
- **Impl Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-07/B-FLOW-07_sf01_implementation_plan.md

### SF-02: Step limits
- **Scope**: the step limit from the history, in the brake, with its settings.
- **FRs**: [FR-4, FR-5, FR-6, FR-7, FR-8, FR-9]
- **Inputs**: the history from SF-01; `[step_limits]`
- **Outputs**: a step limit in each call's scope; `sw config show` rows
- **Depends on**: SF-01
- **Impl Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-07/B-FLOW-07_sf02_implementation_plan.md

## Execution Order

1. SF-01 (no deps)
2. SF-02 (depends on SF-01)

## Progress Tracker

| SF | Name | Depends On | Design | Impl Plan | Dev | Pre-Commit | Committed |
|----|------|-----------|--------|-----------|-----|------------|-----------|
| SF-01 | The history | — | ✅ | ✅ | ✅ | ✅ | ✅ |
| SF-02 | Step limits | SF-01 | ✅ | ✅ | ✅ | ✅ | ✅ |

## Session Handoff

Approved 2026-10-08. SF-01 and SF-02 built and committed 2026-10-08. The capability stays `🔜` until the user signs it off. Read the grilling record before changing
a decision.
