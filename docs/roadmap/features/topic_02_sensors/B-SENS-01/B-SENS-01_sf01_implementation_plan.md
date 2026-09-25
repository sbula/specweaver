# B-SENS-01 SF-01 — Lineage Database & Flow Integration

**Status**: APPROVED · **Feature ID**: 3.14 · **FRs owned**: FR-1, FR-3 · **Depends on**: — ·
Design: [B-SENS-01_design.md](B-SENS-01_design.md) §Sub-features → SF-01

**FRs owned: FR-1, FR-3.** The lineage event store and the parent edge, plus the five fields
every row carries. Recorded 2026-08-17 under `specweaver-dev` §3.2c, from `INT-US-15-SF01-MIG`.
Proof and mutants: `tests/unit/graph/lineage/store/test_lineage_repository.py`.

## Goal

SQLite persistence for the artifact lineage graph, plus run state on the context so handlers can
look up parent artifact UUIDs.

## Where it plugs in

- `Database._ensure_schema()` applies numbered schema versions from the `_MIGRATIONS` list; V11 slots
  in. SQLite supports `ALTER TABLE ADD COLUMN`.
- `llm` may not import `flow/state.py`. So `run_id` travels on `GenerationConfig` (`llm/models.py`):
  the generation handlers in `flow/handlers.py` copy `context.run_id` into `config.run_id` before the
  LLM call, and the `TelemetryCollector` reads it from there. Dependencies stay one-way.

## Changes

**Configuration & database** (CB1 — complete)

1. `[x]` `src/specweaver/config/_db_lineage_mixin.py` — `LineageMixin`, with debug logging:
   - `log_artifact_event(self, artifact_id: str, parent_id: str | None, run_id: str, event_type: str) -> None`
   - `get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]`
   - `get_children(self, parent_id: str) -> list[dict[str, Any]]`
2. `[x]` `src/specweaver/config/_schema.py` — `SCHEMA_V11`:
  ```sql
  CREATE TABLE IF NOT EXISTS artifact_events (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      artifact_id TEXT NOT NULL,
      parent_id   TEXT,
      run_id      TEXT NOT NULL,
      event_type  TEXT NOT NULL,
      timestamp   TEXT NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_lineage_parent ON artifact_events(parent_id);
  CREATE INDEX IF NOT EXISTS idx_lineage_artifact ON artifact_events(artifact_id);
  
  -- Add robust correlation to the LLM telemetry log so we can track the specific models and tasks (research, writing, fixing)
  ALTER TABLE llm_usage_log ADD COLUMN run_id TEXT DEFAULT '';
  ```
3. `[x]` `src/specweaver/config/database.py` — import `LineageMixin` from `._db_lineage_mixin` and add
   it to `Database`'s parents; alias `_SCHEMA_V11 = SCHEMA_V11`; append
   `(11, SCHEMA_V11, "artifact_events & usage correlation")` to `_MIGRATIONS`.

**Flow orchestration**

4. `[MODIFY]` `src/specweaver/flow/_base.py` — `RunContext` gains the AD-5 state (UUID via
   `PipelineRun` StepRecords):
  ```python
  run_id: str | None = None
  step_records: list[dict[str, Any]] | None = None
  ```
5. `[MODIFY]` `src/specweaver/flow/runner.py` — in `_execute_loop(self, run: PipelineRun)`, right
   before `handler.execute(step_def, self._context)`:
    ```python
    self._context.run_id = run.run_id
    self._context.step_records = [r.model_dump() for r in run.step_records]
    ```
   SF-02's generation handlers search `self._context.step_records` for the step that produced the
   parent `artifact_uuid`. Records are `model_dump()` dicts, so handlers cannot mutate the runner's
   models.

**Telemetry**

6. `[MODIFY]` `src/specweaver/llm/models.py` — `GenerationConfig.run_id: str = ""`.
7. `[MODIFY]` `src/specweaver/llm/telemetry.py` — `UsageRecord.run_id: str = ""`;
   `create_usage_record()` copies `config.run_id` into it.
8. `[x]` `src/specweaver/config/_db_telemetry_mixin.py` — `log_usage` INSERT persists `run_id` when
   present.

With `run_id` in `artifact_events` (this SF), `llm_usage_log` (telemetry) and `pipeline_runs` (state
store), a `JOIN` shows which agents generated an artifact, including `task_type` (e.g. `research`,
`review`, `implement`) — which covers committee generation.

## Tests

1. **Migrations**: `pytest tests/unit/config/test_database.py` — schema migrates to 11; `artifact_events`
   exists; `run_id` on telemetry.
2. **Persistence**: `pytest tests/unit/config/test_lineage_mixin.py` — `log_artifact_event` with
   standard rows and NULL `parent_id`.
3. **Context**: `pytest tests/unit/flow/qa_runner.py` — handlers get a `RunContext` with a valid
   `run_id` and `step_records`.
4. **Telemetry**: `pytest tests/unit/llm/test_telemetry.py` — `UsageRecord` carries and persists
   `run_id`.

## Decisions (audit)

- All decisions resolved inline. SF-01 only builds the DB channel and wiring; SF-02 injects UUIDs.
- Imports: `config` does not import `flow` (no cycle); `flow/_base.py` imports nothing forbidden.
  `LineageMixin` is persistence and belongs in `config`; `consumes/forbids` respected.
- The migration appears in both `_schema.py` and `database.py`; `[NEW]`/`[MODIFY]` tags applied.
- The lineage table is the foundation for Feature 3.14a (AI Root-Cause Analysis).
