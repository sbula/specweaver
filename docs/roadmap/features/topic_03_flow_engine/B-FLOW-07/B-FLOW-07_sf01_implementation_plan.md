# Implementation Plan: Spend Limit Matrix (Model × Task × DAL) [SF-01: The history]
- **Feature ID**: B-FLOW-07
- **Sub-Feature**: SF-01 — The history
- **Design Document**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-07/B-FLOW-07_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-01
- **Implementation Plan**: docs/roadmap/features/topic_03_flow_engine/B-FLOW-07/B-FLOW-07_sf01_implementation_plan.md
- **Status**: APPROVED `[agreed 2026-10-08]`

## Scope

FR-1, FR-2, FR-3, FR-10, FR-11. Paths L3 and L4 (`US-04.md`). Lean, as agreed: nothing here
computes a limit; SF-02 does.

## Research Notes (cited, read 2026-10-08)

- `llm_for(context: RunContext, task_type: TaskType) -> tuple[Any, GenerationConfig]` stamps
  `task_type` and `run_id` (`core/flow/handlers/_llm.py:46`).
- `RunHandle(run_id, pipeline_runner, task_id, step_records)` is frozen; `execute_step` rebinds
  `context.run` with `run_id`, `pipeline_runner`, `step_records` each step
  (`core/flow/handlers/run_context.py:82`, `core/flow/engine/step_execution.py`). No step name.
- `create_usage_record(config, response, provider, project, duration_ms, facts) -> UsageRecord`
  copies `config.run_id` (`infrastructure/llm/telemetry.py:85`); `LlmRepository.log_usage(record)`
  maps the dict to `LlmUsageLog` (`infrastructure/llm/store.py:46`).
- One `TelemetryCollector` per server, built in `RoleResolver._adapter(server_name)`
  (`infrastructure/llm/resolve.py:176`), so the collector knows its server's name.
- `TelemetryCollector.flush(db) -> int` writes through `run_sync` (`collector.py:248`); the runner
  flushes in `_finalize(run)`, where `run.step_records` holds each step's status.
- Sub-runs share the parent's router, so one run's flush may write a sibling's records too.
- `seed_dal_level(context)` resolves the run's DAL from `context.yaml` only
  (`core/flow/engine/isolation.py`). Validation falls back to the project's `default_dal`, looked up
  **by the folder's name** (`core/flow/handlers/validation.py:40`) — not by the registered project.
- `workspace_projects.default_dal` defaults to `"DAL_A"`; `root_path` is unique
  (`workspace/store.py:34-48`). No command sets `default_dal`.
- `bootstrap_database` runs `create_all`, then repairs `llm_usage_log` in place
  (`core/config/bootstrap/db_bootstrap.py:57`).
- `sw costs` sums this month's spend per model (`infrastructure/llm/interfaces/cli.py`
  `_month_spend`).

## Findings settled here (not decisions of the user)

1. **The project's default DAL is found by its root path**, not by the folder's name. Validation
   looked it up by name, which misses a project registered under another name. One helper serves
   both validation and the run (FR-3: "the same rule").
2. **Outcomes are written per run, after its records.** At a run's end the runner flushes, then
   sets `step_outcome` on its own rows (`run_id`, `step_name`). A sibling's rows get theirs when
   that sibling ends. A parked run's rows stay empty until its resume ends.
3. **`DAL_A` → `DAL_C` runs once**, in the same bootstrap step that adds the new columns. Run on
   every start, it would undo a `DAL_A` someone later sets on purpose.
4. **`RunHandle` gains `step_name`**, set by `execute_step` like `run_id`.
5. **The outcome is a row per step, not a column per call** (found at CB-1, 2026-10-08): an
   outcome belongs to a step, and a 16th column broke the class-size rule. `llm_step_outcome`
   (`run_id`, `step_name`, `outcome`) is created with the other tables; the history joins it.

## Commit Boundaries

### CB-1 — Every target has a DAL (FR-3, FR-10 part)

Tests first:
- unit: the default-DAL helper finds a project by root path; unknown path → `None`.
- integration (seam `workspace` → `core.flow`): a run on a project with no `context.yaml` DAL
  gets the project's default; validation of that target uses the same DAL.
  Red: today `seed_dal_level` returns `None`.
- integration (bootstrap): a database with projects at `DAL_A` and without the new columns →
  projects at `DAL_C` after one start; a second start keeps a `DAL_A` set in between.

Steps:
1. A helper reading `default_dal` by `root_path` (sync, `Database.connect()`).
2. `seed_dal_level`: `context.yaml` first, then the helper; validation uses the helper.
3. `Project.default_dal` column default → `"DAL_C"`.
4. Bootstrap: if `llm_usage_log` lacks the new columns, add them and set existing
   projects' `default_dal` to `DAL_C` (once).

Mutants: helper by folder name; fallback removed; the one-time update run every start.

### CB-2 — Each call says where it ran and for what (FR-1, FR-10 rest)

Tests first:
- integration (seam `core.flow` → `infrastructure.llm` → database): a one-step pipeline over a
  fake HTTP server → its `llm_usage_log` row holds the server's name, the run's DAL and the step's
  name. Red: the columns do not exist.
- unit: an old database row without the columns reads as unknown.

Steps:
1. `RunHandle.step_name`; `execute_step` sets it.
2. `GenerationConfig` gains `dal_level` and `step_name`; `llm_for` stamps them.
3. `TelemetryCollector` takes its server's name; `UsageRecord` and `LlmUsageLog` gain
   `server`, `dal_level`, `step_name` (all nullable); an index on
   (`task_type`, `model`, `dal_level`) for SF-02's query.

Mutants: each stamped field dropped; the collector's server not passed.

### CB-3 — Outcomes, and spend by server (FR-2, FR-11; paths L3, L4)

Tests first:
- e2e L3: `sw run` of a two-step pipeline, one step passing and one failing, fake HTTP → rows of
  the passed step say `passed`, the other `failed`; `sw costs` shows the model once per server.
  Red: no outcome is written; `sw costs` groups by model.
- e2e L4: the same run on a project with no DAL in `context.yaml` → its rows say `DAL_C`.
- integration: a parked run's rows stay empty; after `sw resume` completes they say `passed`.

Steps:
1. After the flush in `_finalize`, write a `llm_step_outcome` row for each of the run's steps.
2. `_month_spend` and `sw costs` group by model and server.

Mutants: outcome update skipped; outcome taken from the wrong run; `sw costs` by model only.

## Out of scope

The step limit, `[step_limits]`, `sw config show` rows — SF-02.
