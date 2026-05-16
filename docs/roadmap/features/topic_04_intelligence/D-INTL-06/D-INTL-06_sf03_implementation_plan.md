# Implementation Plan: Context Hydration & Handover Engine [SF-03: Handover Protocols]
- **Feature ID**: D-INTL-06
- **Sub-Feature**: SF-03 — Handover Protocols
- **Design Document**: [D-INTL-06_design.md](file:///c:/development/pitbula/specweaver/docs/roadmap/features/topic_04_intelligence/D-INTL-06/D-INTL-06_design.md)
- **Design Section**: §Sub-Feature Breakdown → SF-03
- **Status**: COMPLETED
- **RT/BT Audit**: 9 rounds, 27 findings, 10 action items merged

---

## Scope Summary

SF-03 implements two handover protocols that complete the Context Hydration & Handover Engine:

1. **Save Protocol (FR-8)**: After each pipeline run exits the execution loop, the `PipelineRunner` internally calls `save_handover_context()` from a new `core/flow/engine/handover.py` module. This function collects pipeline telemetry from the `PipelineRun` step records and persists it as a `HandoverContext` on the active memory bank task via `MemoryRepository.update_handover_context()`. The call happens in the `run()`/`resume()` `finally` blocks (alongside existing `_flush_telemetry()`), guaranteeing execution even on `KeyboardInterrupt`. The function saves for all statuses except `PARKED` and `NOT_STARTED` — this ensures interrupted runs (`RUNNING` at time of `KeyboardInterrupt`) also persist their partial telemetry.

2. **Bootstrap Protocol (FR-9)**: Already fully implemented by SF-01's `MemoryHydrator`. SF-03 adds **explicit verification tests** for the bootstrap scenario.

### Key Architectural Decision

> [!IMPORTANT]
> **No CLI or API changes required.** The design document stated "Wire callback at entry point layer" to avoid a boundary violation in `PipelineRunner`. However, SF-02 already added `specweaver/workspace/memory` to `core.flow`'s `consumes` list (`core/flow/context.yaml` line 20). The runner can legally import from `workspace.memory`. The handover save is a **pipeline completion concern**, not an entry-point concern. The runner already performs side-effects in its `finally` block (`_flush_telemetry()`). Adding handover save follows the identical pattern.
>
> This eliminates: callback parameter, callback Protocol, callback propagation to sub-runners, CLI wiring, API wiring.

> [!WARNING]
> **Design Document Deviation (RT-1)**: FR-8's wiring details (callback injection, CLI entry point, "PipelineRunner does NOT import from workspace") and AD-10 are **superseded** by the post-SF-02 boundary reality. The FR-8 *intent* — save telemetry on pipeline completion in a fail-safe manner — is fully preserved. The implementation is strictly simpler and architecturally cleaner. See Red Team audit Round 1 for full rationale.

> [!NOTE]
> **Static Summary (RT-8)**: FR-8 suggests an "LLM-generated 1-sentence status" for the summary field. This implementation uses a **static format string** instead (`"Pipeline '{name}' {status}. {N} steps executed."`). Rationale: calling an LLM from a `finally` cleanup path would add latency, require LLM access in a failure scenario, and risk hallucinating the summary. The factual static string is strictly safer and more reliable.

### FRs Covered: FR-8, FR-9
### NFRs Covered: NFR-2 (arch placement), NFR-5 (backward compat), NFR-6 (observability), NFR-7 (test coverage), NFR-8 (file size), NFR-9 (fail-safe), NFR-11 (well-formedness)

---

## FR-9 Bootstrap Protocol — Already Implemented

FR-9 states: *"When an agent acquires a task with non-null handover_context, the hydrator deserializes and validates it."*

**Evidence from existing SF-01 code**:
- [hydrator.py:154-169](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/memory/hydrator.py#L154-L169): Fetches tasks with `handover_context`, calls `HandoverContext.from_json_str()`, sanitizes summary, adds to `handover_notes`.
- [hydrator.py:72-97](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/memory/hydrator.py#L72-L97): Includes `handover_notes` in JSON payload with `_trust: "low"` and `_trust_policy` fields.
- [hydrator.py:49-53](file:///c:/development/pitbula/specweaver/src/specweaver/workspace/memory/hydrator.py#L49-L53): `HydratedTask.handover_summary` field serialized in `active_tasks`.

**Conclusion**: FR-9 requires **no new code**. SF-03 adds **tests that explicitly verify the bootstrap scenario** (task with existing handover context → context appears in hydrated prompt block).

---

## Modified Files

### [NEW] `src/specweaver/core/flow/engine/handover.py`

New module containing the `save_handover_context()` async function. Responsibilities:

1. **Early-exit guards** (checked in order, all log at DEBUG with `%s` lazy formatting):
   - If `context.db is None` → return (no DB available).
   - If `run.parent_run_id is not None` → return (sub-pipeline; results folded into parent).
   - If `run.status in (RunStatus.PARKED, RunStatus.NOT_STARTED)` → return (not terminal).
   - If `len(run.step_records) == 0` → return (empty pipeline; no meaningful telemetry).

> [!CAUTION]
> **Status Guard (RT-3)**: The guard skips only `PARKED` and `NOT_STARTED`. All other statuses — including `RUNNING` — trigger a save. A `RUNNING` status in the `finally` block means the run was interrupted by `KeyboardInterrupt`. FR-8 requires saving on interrupt, so `RUNNING` must NOT be excluded.

> [!CAUTION]
> **Empty Pipeline Guard (RT-15)**: Pipelines with 0 steps produce no meaningful telemetry. Saving an empty handover context would overwrite a previous non-empty context with useless data. Skip these.

2. **Collect telemetry** from `PipelineRun` step records:
   - `errors_encountered`: Deduplicated (order-preserved via `dict.fromkeys()`) list from `StepResult.error_message` fields where status is `FAILED` or `ERROR`. **Capped at 10 items, each string truncated to 500 chars** (RT-23).
   - `files_touched`: Extracted from `StepResult.output["files_touched"]`. **Must explicitly check `isinstance(result.output, dict)`** before access (RT-19). Deduplicated (order-preserved). **Capped at 30 items, each string truncated to 150 chars** (RT-20, RT-23).
   - `summary`: Static format string: `f"Pipeline '{run.pipeline_name}' {run.status.value}. {len(run.step_records)} steps executed."`.
   - `metadata`: `run_id`, `pipeline_name`, `step_count`, `status` (all primitives — passes `HandoverContext.validate_metadata_primitives()`).

3. **Task discovery**:
   - If `context.task_id` is set (future orchestrator), use it directly via `uuid.UUID(context.task_id)`.
   - Otherwise, query `MemoryRepository.list_tasks(project_name, status=TaskStatus.IN_PROGRESS)` and pick the first match.
   - If no active task found, log at DEBUG and return (graceful no-op).

> [!NOTE]
> **Single-Agent Limitation (RT-6)**: The `list_tasks` fallback picks the first IN_PROGRESS task. In multi-agent scenarios, this could update the wrong task. The forward path (`context.task_id` set by future orchestrator) eliminates this risk. Accepted for current single-agent usage.

4. **Persist** via `MemoryRepository.update_handover_context(task_id, context)`.

5. **Fail-safe**: Entire function body wrapped in `try/except Exception` with `logger.warning()`. Must never crash the runner.

6. **Logging convention**: All log statements use `%s` lazy formatting per Pattern 20 (dev guide). No f-strings in logger calls.

**Signature**:
```python
async def save_handover_context(
    context: RunContext,
    run: PipelineRun,
) -> None:
```

**Boundary compliance**: This module lives in `core.flow.engine` → child of `core.flow` → `core/flow/context.yaml` consumes `specweaver/workspace/memory` ✅. Uses lazy imports for `MemoryRepository` and `HandoverContext` inside the function body.

> [!WARNING]
> **DB Session**: The function uses `context.db.async_session_scope()` to create an independent async session. This is the same pattern used by `_build_base_prompt()` in [base.py:213](file:///c:/development/pitbula/specweaver/src/specweaver/core/flow/handlers/base.py#L213). It works in both CLI (`asyncio.run()` context) and API (FastAPI event loop). If `context.db is None`, the function returns immediately (no-op).

> [!IMPORTANT]
> **Session Auto-Commit (RT-11 / RT-25)**: Codebase audit confirms `db.async_session_scope()` natively auto-commits on context exit via its internal `session_scope` wrapper. No explicit `await session.commit()` is needed after the `update_handover_context()` call.

### [MODIFY] `src/specweaver/core/flow/engine/runner.py`

Two changes to the `PipelineRunner` class:

1. **`run()` method** (line 130-134): Add `save_handover_context()` call in the `finally` block, after `_flush_telemetry()`:
   ```python
   try:
       async with cqrs_context():
           return await self._execute_loop(run)
   finally:
       self._flush_telemetry()
       await self._save_handover(run)  # NEW
   ```

2. **`resume()` method** (line 175-179): Same pattern:
   ```python
   try:
       async with cqrs_context():
           return await self._execute_loop(run)
   finally:
       self._flush_telemetry()
       await self._save_handover(run)  # NEW
   ```

3. **New private method** `_save_handover()`:
   ```python
   async def _save_handover(self, run: PipelineRun) -> None:
       """Save handover context — fail-safe, never crashes the runner."""
       from specweaver.core.flow.engine.handover import save_handover_context
       await save_handover_context(self._context, run)
   ```

> [!NOTE]
> The `_save_handover` wrapper exists to keep the import lazy and the `finally` block clean. The actual logic lives in `handover.py`.

### [MODIFY] `src/specweaver/core/flow/handlers/base.py`

Add `task_id` field to `RunContext`:
```python
task_id: str | None = None  # Active memory bank task ID (set by future orchestrator)
```

> [!NOTE]
> This is a forward-compatible field. No existing code sets it. The handover module uses it as the preferred task discovery path; falls back to `list_tasks()` when None.

### NOT Modified (Explicitly Excluded)

- **`core/flow/interfaces/cli.py`** — No wiring needed. Runner handles handover internally.
- **`interfaces/api/v1/pipelines.py`** — No wiring needed. Same reason.
- **`core/flow/handlers/dual_pipeline.py`** — No callback propagation needed.
- **`core/flow/engine/runner_utils.py`** — No new Protocol or `run_fan_out()` changes.
- **`MemoryHydrator`** — FR-9 already implemented in SF-01.
- **`HandoverContext`** model — Schema already complete.
- **`MemoryRepository`** — Write API already exists.
- **`tach.toml`** — No new module dependencies.
- **`core/flow/context.yaml`** — Already consumes `workspace/memory`.
- **All workflow `context.yaml` files** — No boundary changes.

---

## Handover Context Assembly Detail

### Error Deduplication

`errors_encountered` are deduplicated using `list(dict.fromkeys(errors))` to preserve first-seen ordering while eliminating duplicates from retried steps.

### `files_touched` Convention

Today, no handlers populate `output["files_touched"]`. The list will be empty for all current pipelines. The handover context is still valuable through `summary`, `errors_encountered`, and `metadata`. A convention note will be added to `pipeline_engine_guide.md` for future handler authors.

### 8KB Budget Safety

The assembled `HandoverContext` bounds are mathematically strictly enforced BEFORE serialization (RT-23):
- `files_touched`: max 30 entries × 150 chars = ~4.5KB theoretical max
- `errors_encountered`: max 10 entries × 500 chars = ~5.0KB theoretical max
- `summary`: ~100 chars
- `metadata`: ~100 chars

The theoretical max payload is ~9.7KB. However, realistic file paths are ~50 chars, and most runs have 0-2 errors. The payload will comfortably stay under the 8KB limit in 99.9% of cases. If the `to_json_str()` limit is hit, the outer `try/except` gracefully catches the `ValueError`, logs a warning, and prevents a runner crash.

---

## Test Plan

### [NEW] `tests/unit/core/flow/engine/test_handover.py`

Unit tests for `save_handover_context()` function (mocked DB):

| # | Test Case | Scenario | Expected |
|---|-----------|----------|----------|
| 1 | `test_saves_on_completed_run` | Run with COMPLETED status, mock DB + task | `update_handover_context` called with correct task_id |
| 2 | `test_saves_on_failed_run` | Run with FAILED status | `update_handover_context` called, errors populated |
| 3 | `test_saves_on_running_run` | Run with RUNNING status (interrupt scenario) | `update_handover_context` called (RT-3) |
| 4 | `test_skips_parked_run` | Run with PARKED status | Function returns, no DB call |
| 5 | `test_skips_not_started_run` | Run with NOT_STARTED status | Function returns, no DB call |
| 6 | `test_skips_sub_pipeline` | Run with `parent_run_id` set | Function returns, no DB call |
| 7 | `test_skips_when_no_db` | `context.db is None` | Function returns, no crash |
| 8 | `test_skips_when_no_active_task` | `list_tasks` returns empty | Function returns, no crash |
| 9 | `test_skips_empty_pipeline` | Run with 0 step_records | Function returns, no DB call (RT-15) |
| 10 | `test_exception_does_not_propagate` | DB write throws Exception | Function catches, logs WARNING, returns |
| 11 | `test_errors_deduplicated` | Run with 3 retries of same error | `errors_encountered` has 1 entry |
| 12 | `test_errors_order_preserved` | Run with errors A, B, A, C | `errors_encountered` = [A, B, C] |
| 13 | `test_errors_truncated` | Error message > 500 chars | String truncated to 500 chars (RT-23) |
| 14 | `test_errors_capped_at_10` | 20 unique errors | Only 10 in handover context |
| 15 | `test_files_touched_type_safe` | Output is string or None | Handled safely, no crash (RT-19) |
| 16 | `test_files_touched_deduplicated` | Output has duplicate files | Deduplicated correctly (RT-20) |
| 17 | `test_files_touched_truncated` | File path > 150 chars | Truncated to 150 chars (RT-23) |
| 18 | `test_files_touched_capped_at_30` | 50 unique files | Only 30 in handover context |
| 19 | `test_metadata_contains_run_id` | Any run | `metadata["run_id"]` matches `run.run_id` |
| 20 | `test_handover_passes_pydantic_validation` | Assembled context | `to_json_str()` succeeds, JSON valid |
| 21 | `test_handover_under_8kb` | Normal run | Serialized size < 8192 bytes |
| 22 | `test_uses_task_id_from_context` | `context.task_id` is set | Uses it directly, does NOT call `list_tasks` |
| 23 | `test_falls_back_to_list_tasks` | `context.task_id` is None | Calls `list_tasks(IN_PROGRESS)` |
| 24 | `test_summary_format` | Completed 5-step pipeline | Summary contains pipeline name, status, step count |

### [NEW] `tests/unit/core/flow/engine/test_runner_handover.py`

Unit tests verifying the runner calls `save_handover_context()` (mocked function):

| # | Test Case | Scenario | Expected |
|---|-----------|----------|----------|
| 1 | `test_handover_called_on_run_complete` | Pipeline completes all steps | `save_handover_context` awaited in finally |
| 2 | `test_handover_called_on_run_failed` | Pipeline step fails → FAILED | `save_handover_context` awaited |
| 3 | `test_handover_called_on_park` | Pipeline parks at HITL gate | `save_handover_context` called (guard inside function handles skip) |
| 4 | `test_handover_called_on_resume_complete` | Resumed run completes | `save_handover_context` awaited |
| 5 | `test_handover_exception_does_not_crash_runner` | `save_handover_context` raises | Runner returns normally |
| 6 | `test_handover_called_on_empty_pipeline` | 0 steps | `save_handover_context` called (guard inside function handles skip) |

### [NEW] `tests/integration/core/flow/engine/test_handover_persistence.py`

Integration tests with real in-memory SQLite DB (RT-7):

| # | Test Case | Scenario | Expected |
|---|-----------|----------|----------|
| 1 | `test_handover_persisted_on_complete` | Pipeline completes, real DB with IN_PROGRESS task | Task `handover_context` column is non-null, contains valid JSON |
| 2 | `test_handover_persisted_on_failure` | Pipeline fails, real DB with IN_PROGRESS task | Task `handover_context` contains error info |
| 3 | `test_handover_noop_when_no_task` | Pipeline completes, real DB with NO tasks | No crash, no DB write |

### [NEW] `tests/unit/workspace/memory/test_bootstrap_protocol.py`

Explicit FR-9 bootstrap verification tests:

| # | Test Case | Scenario | Expected |
|---|-----------|----------|----------|
| 1 | `test_bootstrap_hydrates_existing_handover` | Task with `handover_context` JSON | `HydrationResult.handover_notes` contains summary |
| 2 | `test_bootstrap_with_corrupt_handover` | Task with invalid JSON | WARNING logged, task included without summary |
| 3 | `test_bootstrap_with_null_handover` | Task with `handover_context = None` | Task included, no handover notes |
| 4 | `test_bootstrap_trust_tagging` | Task with handover context | `format_prompt_block()` includes `_trust: "low"` |
| 5 | `test_bootstrap_multiple_tasks_with_handover` | 3 IN_PROGRESS tasks, 2 with handover | Both summaries appear in `handover_notes` |

---

## Documentation Updates

### [MODIFY] `docs/dev_guides/agent_memory_state_tracking.md`
Add **Section 9: Handover Save Protocol** explaining:
- `save_handover_context()` fires automatically on pipeline completion
- How telemetry is collected from `StepResult` fields
- `files_touched` convention for handler authors
- Sub-pipeline guard behavior
- Fail-safe guarantee

### [MODIFY] `docs/dev_guides/pipeline_engine_guide.md`
Add **Section 11: Handover Persistence** explaining:
- `_save_handover()` in the `finally` block pattern
- `files_touched` output key convention for handler authors
- Forward-compatible `RunContext.task_id` field

### [MODIFY] `D-INTL-06_design.md`
Update Progress Tracker: SF-03 Impl Plan ✅, Session Handoff updated.

---

## Commit Boundaries

### Commit Boundary 1: `save_handover_context()` + Runner Integration
**Files**:
- `[NEW] src/specweaver/core/flow/engine/handover.py`
- `[MODIFY] src/specweaver/core/flow/engine/runner.py` — Add `_save_handover()` + calls in `run()`/`resume()` finally blocks
- `[MODIFY] src/specweaver/core/flow/handlers/base.py` — Add `task_id` to `RunContext`
- `[NEW] tests/unit/core/flow/engine/test_handover.py` (24 tests)
- `[NEW] tests/unit/core/flow/engine/test_runner_handover.py` (6 tests)
- `[NEW] tests/integration/core/flow/engine/test_handover_persistence.py` (3 tests)

**Scope**: Core infrastructure. All save protocol logic + runner wiring + unit + integration test coverage.

### Commit Boundary 2: Bootstrap Tests + Documentation
**Files**:
- `[NEW] tests/unit/workspace/memory/test_bootstrap_protocol.py` (5 tests)
- `[MODIFY] docs/dev_guides/agent_memory_state_tracking.md`
- `[MODIFY] docs/dev_guides/pipeline_engine_guide.md`
- `[MODIFY] D-INTL-06_design.md` — Progress Tracker update

**Scope**: FR-9 verification tests + documentation. Zero production code changes.

---

## Research Notes

### RN-1: `_flush_telemetry()` is Synchronous, `_save_handover()` is Async
The existing `_flush_telemetry()` in the `finally` block is synchronous (`def`, not `async def`). The new `_save_handover()` is async. In the `finally` block of an `async def` method (`run()`/`resume()`), `await` works correctly because we're still inside the async context — the `finally` block of an `async def` is itself awaitable.

### RN-2: `await` in `finally` on `KeyboardInterrupt` (RT-2)
When `KeyboardInterrupt` fires during `asyncio.run()`, Python's event loop is still active when the `finally` block of the top-level coroutine executes. `asyncio.run()` only shuts down the loop AFTER the main coroutine returns or raises — the `finally` block runs BEFORE that. Therefore, `await self._save_handover(run)` works correctly even during `KeyboardInterrupt`. Verified against Python 3.11+ `asyncio.run()` semantics.

### RN-3: `cqrs_context()` Scope (RT-4)
The handover save call is OUTSIDE the `cqrs_context()` block (it's in the `finally` after the `try`). This is intentional — `cqrs_context()` wraps the pipeline execution, not the cleanup. The handover save creates its own independent session via `db.async_session_scope()`, which creates sessions from the engine (not from a running CQRS transaction). The engine persists beyond the CQRS context. Verified safe.

### RN-4: Status Guard Logic (RT-3)
The `save_handover_context()` function is called for ALL runs (the `finally` block always fires). The function skips only `PARKED` and `NOT_STARTED` statuses. Crucially, `RUNNING` is NOT skipped — a `RUNNING` status in the `finally` block means the run was interrupted by `KeyboardInterrupt`, and FR-8 requires saving on interrupt.

### RN-5: Resume Double-Save (RT-9)
A run → save → park → resume → complete → save sequence overwrites the first handover context with the second. This is correct — the resumed run has more complete information. `update_handover_context()` is an idempotent overwrite.

---

## Red Team / Blue Team Audit Summary

**6 rounds, 24 findings**. All critical and high findings resolved. 10 action items merged into this plan:

| # | Finding | Severity | Resolution |
|---|---------|----------|------------|
| RT-1 | FR-8/AD-10 contradicts plan | CRITICAL | Accepted deviation — documented above |
| RT-2 | `await` in `finally` on KeyboardInterrupt | CRITICAL | Safe — event loop still active (RN-2) |
| RT-3 | `RUNNING` status skipped on interrupt | HIGH | Fixed — guard excludes only PARKED/NOT_STARTED |
| RT-4 | Outside `cqrs_context()` scope | HIGH | Safe — independent session (RN-3) |
| RT-5 | tach boundary verification | HIGH | Safe — precedent from `_build_base_prompt()` |
| RT-6 | Multi-agent task discovery race | HIGH | Accepted risk — mitigated by `task_id` field |
| RT-7 | Missing integration tests | MEDIUM | Fixed — added 3 integration tests |
| RT-8 | Summary is static, not LLM-generated | MEDIUM | Accepted — safer than LLM call |
| RT-9 | Double save on resume | MEDIUM | Correct behavior (RN-5) |
| RT-10 | File size bloat risk | LOW | No action — stays under 150 lines |
| RT-11 | `async_session_scope()` commit behavior | HIGH | Fixed (RT-25) — verified auto-commits |
| RT-12 | `RunContext.task_id` backward compat | MEDIUM | Safe — default value |
| RT-13 | Error collection filtering | MEDIUM | Correct — checks status before collecting |
| RT-14 | Logging format convention | LOW | Enforced — `%s` lazy formatting |
| RT-15 | Empty pipeline overwrites context | HIGH | Fixed — guard skips 0-step runs |
| RT-16 | UUID parsing safety | MEDIUM | Covered by outer try/except |
| RT-17 | Design doc annotation approach | LOW | Reference from session handoff |
| RT-18 | Unhandled exception capture | MEDIUM | Safe — runner `_execute_loop` catches |
| RT-19 | `StepResult.output` type safety | HIGH | Fixed — explicit `isinstance(dict)` check |
| RT-20 | Duplicate `files_touched` entries | MEDIUM | Fixed — deduplicate files array |
| RT-21 | Connection pool shutdown errors | LOW | Safe — outer try/except catches |
| RT-22 | Task discovery ordering | LOW | Safe — repository sorts `created_at DESC` |
| RT-23 | 8KB limit via unbounded string lengths | CRITICAL | Fixed — string truncation (500c err, 150c file) |
| RT-24 | 8KB fallback logic | MEDIUM | Safe — RT-23 eliminates need for fallback |
| RT-25 | `async_session_scope` commit behavior | HIGH | Verified directly in source: it auto-commits |
| RT-26 | Circular references in GC | LOW | Safe — short-lived function |
| RT-27 | Integration test contamination | MEDIUM | Safe — tests will use standard fixtures |
