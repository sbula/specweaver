# Implementation Plan: Spec-to-Code Traceability (Artifact Lineage Graph) [SF-1: Lineage Database & Flow Integration]

- **Feature ID**: 3.14
- **Sub-Feature**: SF-1 — Lineage Database & Flow Integration
- **Design Document**: docs/proposals/design/phase_3/feature_3_17_design.md
- **Design Section**: §Sub-Feature Breakdown → SF-1
- **Implementation Plan**: docs/proposals/roadmap/phase_3/feature_3_17_sf1_implementation_plan.md
- **Status**: APPROVED

## Goal
Implement SQLite persistence for the artifact lineage graph and propagate state context so that pipeline handlers can reliably look up parent artifact UUIDs.

## Proposed Changes

### Configuration & Database (CB1 - Complete)
#### [x] `src/specweaver/config/_db_lineage_mixin.py`
- Add `LineageMixin` class with methods:
  - `log_artifact_event(self, artifact_id: str, parent_id: str | None, run_id: str, event_type: str) -> None`
  - `get_artifact_history(self, artifact_id: str) -> list[dict[str, Any]]`
  - `get_children(self, parent_id: str) -> list[dict[str, Any]]`
- Includes proper debug logging.

#### [x] `src/specweaver/config/_schema.py`
- Add `SCHEMA_V11` with proper table DDL and telemetry upgrade:
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

#### [x] `src/specweaver/config/database.py`
- Import `LineageMixin` from `._db_lineage_mixin`.
- Add `LineageMixin` to the `Database` class inheritance parent list.
- Add `SCHEMA_V11` backward-compatible alias (`_SCHEMA_V11 = SCHEMA_V11`).
- Update `_MIGRATIONS` table with `(11, SCHEMA_V11, "artifact_events & usage correlation")`.

---

### Flow Orchestration
#### [MODIFY] `src/specweaver/flow/_base.py`
- Modify `RunContext` to include state tracking required for AD-5 (passing UUID via `PipelineRun` StepRecords):
  ```python
  run_id: str | None = None
  step_records: list[dict[str, Any]] | None = None
  ```

#### [MODIFY] `src/specweaver/flow/runner.py`
- Update `_execute_loop(self, run: PipelineRun)`:
  - Right before invoking `handler.execute(step_def, self._context)`, attach current flow state to the context:
    ```python
    self._context.run_id = run.run_id
    self._context.step_records = [r.model_dump() for r in run.step_records]
    ```
  - This ensures that downstream generation handlers (added in SF-2) can look inside `self._context.step_records` to deterministically find the step that outputted the parent `artifact_uuid`.

---

### Telemetry Sub-System Upgrade
#### [MODIFY] `src/specweaver/llm/models.py`
- In `GenerationConfig`, add `run_id: str = ""` field. This creates a clean bridge for passing the run identity down to the adapter without breaking architectural bounds.

#### [MODIFY] `src/specweaver/llm/telemetry.py`
- In `UsageRecord`, add `run_id: str = ""` field.
- In `create_usage_record()`, pull `run_id` directly from `config.run_id` and apply it to the `UsageRecord`.

#### [x] `src/specweaver/config/_db_telemetry_mixin.py`
- Update `log_usage` INSERT statement to correctly persist `run_id` if present in the record dict.

## Research Notes
- **DB Schema Handling**: The `Database._ensure_schema()` logic smoothly handles numerical schema versioning via the `_MIGRATIONS` table list. V11 hooks straight in without disruption. SQLite's `ALTER TABLE ADD COLUMN` is natively supported.
- **Context Passing**: Passing `step_records` as a list of serialized dictionaries via `model_dump()` guarantees handlers cannot accidentally mutate the runner's internal models, maintaining tight encapsulation.
- **Correlation Power**: By tracking `run_id` uniformly across `artifact_events` (this SF), `llm_usage_log` (telemetry), and `pipeline_runs` (state store), we can perfectly execute the `JOIN` queries needed to see exactly which agents generated the artifact, including the `task_type` (e.g. `research`, `review`, `implement`), addressing committee-generation edge cases flawlessly.

---

## Consistency Check Responses (Phases 4 & 5)

### 5.1 Open questions
**Are there still any unresolved decisions or ambiguities?**
All decisions are resolved and documented inline in the plan. SF-1 solely deals with establishing the database channel and providing the contextual wiring for SF-2 to actually inject UUIDs into code.

### 5.1a Agent Handoff Risk
**If a new agent in a new session were to continue starting only with this document:**
A fresh agent will likely stumble on this critical question: *"How does the `TelemetryCollector` inside the `llm` module know what the current `run_id` is, since `llm` correctly forbids importing `flow/state.py`?"*
**Mitigation:** The plan explicitly dictates adding `run_id` to `GenerationConfig` inside `llm/models.py`. The generation handlers inside `flow/handlers.py` will read `context.run_id` and assign it to `config.run_id` before calling the LLM. The `TelemetryCollector` simply extracts it from the `GenerationConfig`. Doing this preserves the strict one-way dependency rules established in the architecture documentation.

### 5.2 Architecture and future compatibility
**Does the plan respect all context.yaml dependency rules and support upcoming roadmap features?**
- **Import Chains**: `config` does not import `flow` (no cycle). `flow/_base.py` does not import any forbidden modules.
- **Archetypes**: `LineageMixin` represents persistence which fully belongs in `config` layer. We respect the `consumes/forbids` structure smoothly.
- **Roadmap Compatibility**: Adding the lineage table prepares perfect foundation for Feature 3.14a (AI Root-Cause Analysis).

### 5.3 Internal consistency
**Does the plan contradict itself anywhere?**
No contradictions found:
- `[NEW]` and `[MODIFY]` tags strictly applied.
- DB migration is simultaneously present in `_schema.py` and `database.py`.
- No untestable magic.

---

## Verification Plan
### Automated Tests
1. **Migrations**: `pytest tests/unit/config/test_database.py` (Assert schema migrates to 11 and table `artifact_events` exists, plus `run_id` on telemetry).
2. **Persistence**: `pytest tests/unit/config/test_lineage_mixin.py` (Assert `log_artifact_event` handles standard rows and NULL `parent_id` cases).
3. **Context Tracing**: `pytest tests/unit/flow/test_runner.py` (Assert that handlers receive a `RunContext` seeded with valid `run_id` and list of `step_records`).
4. **Telemetry Correlation**: `pytest tests/unit/llm/test_telemetry.py` (Assert `UsageRecord` supports and persists new `run_id` field).
