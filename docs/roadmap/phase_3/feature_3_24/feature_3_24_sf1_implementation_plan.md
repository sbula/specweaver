# Implementation Plan: Automated iterative decomposition (multi-level) [SF-1: Hierarchical Orchestration Engine Support]

- **Feature ID**: 3.24
- **Sub-Feature**: SF-1 — Hierarchical Orchestration Engine Support
- **Design Document**: docs/roadmap/phase_3/feature_3_24/feature_3_24_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/roadmap/phase_3/feature_3_24/feature_3_24_sf1_implementation_plan.md
- **Status**: APPROVED

## Goal
Implement a hierarchical architecture that allows Steps (like `DecomposeHandler`) to dynamically trigger parallel sub-pipelines using a `fan_out` execution strategy. Add `parent_run_id` to pipeline records in `pipeline_state.db` to ensure safe, deeply nested telemetry.

## Pre-conditions & Scope
- Pipeline Execution layer relies on synchronous `asyncio.gather` (Option A).
- SQLite Schema versioning must be handled cleanly via existing `state_schema_version` mechanisms (Option A: Explicit migration V1 -> V2).

## Proposed Changes

### `src/specweaver/flow/state.py`
#### [MODIFY] [DONE]
- Add `parent_run_id: str | None = None` to the `PipelineRun` Pydantic model. 
> [!NOTE]
> Per architectural review, `child_run_ids` array is embedded into the generic `StepResult.output` dictionary instead of creating native model pollution. We will natively trace telemetry on this element to inform a future shift to Option B if statistical usage necessitates it.

### `src/specweaver/flow/store.py`
#### [MODIFY] [DONE]
- Add logic inside `_ensure_schema()`: Query `state_schema_version`; if `version == 1`, execute `ALTER TABLE pipeline_runs ADD COLUMN parent_run_id TEXT REFERENCES pipeline_runs(run_id);`, then `UPDATE state_schema_version SET version=2`. 
- Upgrade the primary `CREATE TABLE` injection script (`_STATE_SCHEMA_V2`) to include `parent_run_id` for fresh databases.
- Update `save_run()` SQLite parameters inside the `INSERT OR REPLACE` string.
- Update `_row_to_run()` to safely unmap `parent_run_id`.

#### [MODIFY] `src/specweaver/flow/runner.py`
- [x] Establish a mechanism (`fan_out()`) to orchestrate `asyncio.gather` across N spawned `PipelineRunner` executors.
> [!CAUTION]
> The architectural design isolates this parallel execution directly in the action handler flow (Blocking). Be structurally prepared for a future where `sw status` requires switching this out for `StepStatus.YIELD_TO_CHILDREN` non-blocking architecture.

## Verification Plan

### Automated Tests
- [x] Spawn an ephemeral `StateStore`. Simulate a V1 `pipeline_runs` table, then pass it to `StateStore(db_path)` and assert that the `ALTER TABLE` successfully elevates the schema and allows `parent_run_id` saves without throwing integrity crashes.
- [ ] Mock an `asyncio.sleep` atomic pipeline. Fan out 3 pipelines and verify `asyncio.gather` returns 3 `RunStatus.COMPLETED` nodes.

### Manual Verification
- Execute `sw pipeline run feature_decomposition` to verify no breaking backward compatibility issues occur across normal flat pipeline definitions.
