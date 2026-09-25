# C-INTL-01 SF-01 — Hierarchical Orchestration Engine Support

**Status**: APPROVED · **FRs owned**: FR-1 (recorded 2026-08-17 under `specweaver-dev` §3.2c, from
`INT-US-21-SUB-MIG`; before that `check_fr_coverage.py` read it as unplanned) · **Depends on**: none ·
Design: [C-INTL-01_design.md](C-INTL-01_design.md) §Sub-features → SF-01

## Goal

Steps such as `DecomposeHandler` can start parallel sub-pipelines with a `fan_out` strategy.
`parent_run_id` on pipeline records in `pipeline_state.db` keeps nested telemetry traceable.

Preconditions (both Option A): execution uses synchronous `asyncio.gather`; the SQLite schema moves
through the existing `state_schema_version` mechanism (explicit migration V1 -> V2).

## Changes

1. **`src/specweaver/flow/state.py`** [DONE] — `parent_run_id: str | None = None` on the `PipelineRun`
   Pydantic model. `child_run_ids` goes into the generic `StepResult.output` dict, not the model (per
   architectural review); telemetry on it decides a later move to Option B.
2. **`src/specweaver/flow/store.py`** [DONE]:
   - `_ensure_schema()`: read `state_schema_version`; if `version == 1`, run
     `ALTER TABLE pipeline_runs ADD COLUMN parent_run_id TEXT REFERENCES pipeline_runs(run_id);`, then
     `UPDATE state_schema_version SET version=2`.
   - The fresh-DB `CREATE TABLE` script (`_STATE_SCHEMA_V2`) includes `parent_run_id`.
   - `save_run()`: add it to the `INSERT OR REPLACE` parameters. `_row_to_run()`: read it back.
3. **`src/specweaver/flow/runner.py`** [x] — `fan_out()` runs `asyncio.gather` over N spawned
   `PipelineRunner` executors.

> [!CAUTION]
> The parallel run blocks inside the action handler. If `sw status` needs live child status, this
> must switch to a non-blocking `StepStatus.YIELD_TO_CHILDREN`.

## Tests

| Status | Case |
|---|---|
| [x] | ephemeral `StateStore` on a simulated V1 `pipeline_runs` table: `StateStore(db_path)` runs the `ALTER TABLE`, and `parent_run_id` saves without integrity errors |
| [ ] | mocked `asyncio.sleep` pipeline: fan out 3, `asyncio.gather` returns 3 `RunStatus.COMPLETED` |
| manual | `sw pipeline run feature_decomposition` — flat pipeline definitions still work |

Proof and mutants:

| Test | FR | Kills |
|---|---|---|
| `tests/unit/core/flow/handlers/test_decompose.py` | FR-1 | emptying `plan.component_changes` fails 28 tests |
| same | FR-4 | stripping `validate_spec` from the per-component template |
| `tests/e2e/capabilities/workflows/test_feature_decomposition_e2e.py` | FR-2 | the decompose gate flipped from `hitl` to `auto` (only an e2e notices) |

The FR-4 test was new: the per-component battery exists only because fan-out spawns
`new_feature.yaml`, and nothing asserted that template still carries `validate_spec`.

## As built

**Since moved** (checked 2026-09-25): fan-out is `run_fan_out` in
`src/specweaver/core/flow/engine/fan_out.py`; the table is `flow_pipeline_runs` in
`core/flow/engine/store.py`.
