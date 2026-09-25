# D-INTL-06 SF-03 — Handover Protocols

**Status**: COMPLETED · **FRs owned**: FR-8, FR-9 · **NFRs**: NFR-2 (arch placement), NFR-5
(backward compat), NFR-6 (observability), NFR-7 (test coverage), NFR-8 (file size), NFR-9
(fail-safe), NFR-11 (well-formedness) · **Depends on**: SF-01, SF-02 · Design:
[D-INTL-06_design.md](D-INTL-06_design.md) §Sub-features → SF-03 · **RT/BT Audit**: 9 rounds, 27
findings, 10 action items merged

**Since moved** (2026-08-14, `07de1836`): `run()` and `resume()` share one `_finalize()` in their
`finally`; it saves the handover **before** `_flush_telemetry()`, because the flush may drain the
step records `save_handover_context` reads. `_save_handover()` wraps the call in its own
`try/except`. Line refs below are as of the plan's date.

## Goal

1. **Save protocol (FR-8):** when a run leaves the execution loop, `PipelineRunner` calls
   `save_handover_context()` from a new `core/flow/engine/handover.py`. It collects telemetry from
   the `PipelineRun` step records and persists it as a `HandoverContext` on the active memory bank
   task via `MemoryRepository.update_handover_context()`. The call sits in the `run()`/`resume()`
   `finally` blocks (with `_flush_telemetry()`), so it runs even on `KeyboardInterrupt`. It saves
   for every status except `PARKED` and `NOT_STARTED`, so an interrupted run (`RUNNING`) keeps its
   partial telemetry.
2. **Bootstrap protocol (FR-9):** already implemented by SF-01's `MemoryHydrator`; SF-03 adds
   **explicit verification tests**.

**No CLI or API changes.** SF-02 put `specweaver/workspace/memory` in `core.flow`'s `consumes`
(`core/flow/context.yaml` line 20), so the runner may import it. Handover save is a **pipeline
completion concern**, like `_flush_telemetry()` in the same `finally`. This drops the callback
parameter, callback Protocol, propagation to sub-runners, CLI wiring and API wiring. It supersedes
FR-8's wiring (callback injection, CLI entry point, "PipelineRunner does NOT import from
workspace") and AD-10 (RT-1); FR-8's intent — save telemetry on completion, fail-safe — is
unchanged.

## Where it plugs in

FR-9 is already covered by SF-01 code:

- `hydrator.py:154-169` — fetches tasks with `handover_context`, calls
  `HandoverContext.from_json_str()`, sanitizes the summary, adds to `handover_notes`.
- `hydrator.py:72-97` — `handover_notes` in the JSON payload with `_trust: "low"` and
  `_trust_policy`.
- `hydrator.py:49-53` — `HydratedTask.handover_summary` serialized in `active_tasks`.

| Fact | Consequence |
|---|---|
| `_flush_telemetry()` is sync; `_save_handover()` is async. The `finally` of an `async def` (`run()`/`resume()`) can `await`. (RN-1) | No wrapper thread or loop needed. |
| On `KeyboardInterrupt` under `asyncio.run()`, the loop is still active while the top-level coroutine's `finally` runs; it shuts down only after the coroutine returns or raises. Verified against Python 3.11+ semantics. (RN-2, RT-2) | `await self._save_handover(run)` works on interrupt. |
| The save is outside `cqrs_context()` (it wraps execution, not cleanup) and opens its own session via `db.async_session_scope()` from the engine, which outlives the CQRS context. (RN-3, RT-4) | Safe. |
| `db.async_session_scope()` auto-commits on exit through its internal `session_scope` wrapper — verified in source. (RT-11 / RT-25) | No explicit `await session.commit()` after `update_handover_context()`. |
| Same session pattern as `_build_base_prompt()` in `base.py:213`; works under CLI (`asyncio.run()`) and API (FastAPI event loop). | — |
| Run → save → park → resume → complete → save overwrites the first context with the second; `update_handover_context()` is an idempotent overwrite. (RN-5, RT-9) | Correct: the resumed run knows more. |
| No handler populates `output["files_touched"]` today, so the list is empty for all current pipelines; `summary`, `errors_encountered` and `metadata` still carry value. | A convention note for handler authors goes into `pipeline_engine_guide.md`. |

## Changes

1. **NEW `src/specweaver/core/flow/engine/handover.py`** — `save_handover_context()`:

```python
async def save_handover_context(
    context: RunContext,
    run: PipelineRun,
) -> None:
```

   1. **Early-exit guards**, in order, each logging at DEBUG with `%s` lazy formatting:
      `context.db is None` → return (no DB); `run.parent_run_id is not None` → return
      (sub-pipeline; results folded into parent); `run.status in (RunStatus.PARKED, RunStatus.NOT_STARTED)`
      → return (not terminal); `len(run.step_records) == 0` → return (empty pipeline).
      - **Status guard (RT-3):** only `PARKED` and `NOT_STARTED` are skipped. `RUNNING` in the
        `finally` means a `KeyboardInterrupt`, and FR-8 requires saving then.
      - **Empty pipeline guard (RT-15):** a 0-step run would overwrite a previous non-empty context
        with nothing.
   2. **Collect telemetry** from `PipelineRun` step records:
      - `errors_encountered`: from `StepResult.error_message` where status is `FAILED` or `ERROR`;
        deduplicated in order via `dict.fromkeys()` (`list(dict.fromkeys(errors))`) (retried steps repeat errors);
        **capped at 10 items, each truncated to 500 chars** (RT-23).
      - `files_touched`: from `StepResult.output["files_touched"]`, **only after
        `isinstance(result.output, dict)`** (RT-19); deduplicated in order; **capped at 30 items,
        each truncated to 150 chars** (RT-20, RT-23).
      - `summary`: `f"Pipeline '{run.pipeline_name}' {run.status.value}. {len(run.step_records)} steps executed."`.
      - `metadata`: `run_id`, `pipeline_name`, `step_count`, `status` — all primitives, so it passes
        `HandoverContext.validate_metadata_primitives()`.
   3. **Task discovery:** `context.task_id` set (future orchestrator) → `uuid.UUID(context.task_id)`.
      Else `MemoryRepository.list_tasks(project_name, status=TaskStatus.IN_PROGRESS)`, first match.
      None found → DEBUG, return.
   4. **Persist** via `MemoryRepository.update_handover_context(task_id, context)`.
   5. **Fail-safe:** the whole body in `try/except Exception` with `logger.warning()`; never crashes
      the runner.
   6. **Logging:** `%s` lazy formatting everywhere (Pattern 20, dev guide); no f-strings in logger
      calls.

   Boundary: `core.flow.engine` is a child of `core.flow`, whose `core/flow/context.yaml` consumes
   `specweaver/workspace/memory` ✅. `MemoryRepository` and `HandoverContext` are imported lazily
   inside the function.

2. **`src/specweaver/core/flow/engine/runner.py`** — `run()` (line 130-134) and `resume()`
   (line 175-179) call it in the `finally` after `_flush_telemetry()`:

   ```python
   try:
       async with cqrs_context():
           return await self._execute_loop(run)
   finally:
       self._flush_telemetry()
       await self._save_handover(run)  # NEW
   ```

   plus a private wrapper that keeps the import lazy and the `finally` clean (logic stays in
   `handover.py`):

   ```python
   async def _save_handover(self, run: PipelineRun) -> None:
       """Save handover context — fail-safe, never crashes the runner."""
       from specweaver.core.flow.engine.handover import save_handover_context
       await save_handover_context(self._context, run)
   ```

3. **`src/specweaver/core/flow/handlers/base.py`** — `RunContext` gains a forward-compatible field
   no code sets yet; the handover module prefers it and falls back to `list_tasks()` when None:

```python
task_id: str | None = None  # Active memory bank task ID (set by future orchestrator)
```

**8KB budget (RT-23).** Bounds are enforced before serialization: `files_touched` 30 × 150 chars =
~4.5KB; `errors_encountered` 10 × 500 chars = ~5.0KB; `summary` ~100 chars; `metadata` ~100 chars.
Theoretical max ~9.7KB; with realistic ~50-char paths and 0-2 errors per run it stays under 8KB in
99.9% of cases. If `to_json_str()` hits the limit, the outer `try/except` catches the `ValueError`,
logs a warning, and the runner does not crash.

**Single-agent limitation (RT-6).** The `list_tasks` fallback takes the first IN_PROGRESS task; with
several agents it could update the wrong one. `context.task_id` (set by a future orchestrator)
removes the risk. Accepted for single-agent use.

**NOT modified:**

- **`core/flow/interfaces/cli.py`**, **`interfaces/api/v1/pipelines.py`** — the runner handles
  handover itself.
- **`core/flow/handlers/dual_pipeline.py`** — no callback propagation.
- **`core/flow/engine/runner_utils.py`** — no new Protocol or `run_fan_out()` changes.
- **`MemoryHydrator`** (FR-9 done in SF-01), **`HandoverContext`** model (schema complete),
  **`MemoryRepository`** (write API exists).
- **`tach.toml`** (no new module dependencies), **`core/flow/context.yaml`** (already consumes
  `workspace/memory`), **all workflow `context.yaml` files**.

| CB | Files | Scope |
|---|---|---|
| CB-1 | `[NEW] src/specweaver/core/flow/engine/handover.py`; `[MODIFY] src/specweaver/core/flow/engine/runner.py` — `_save_handover()` + calls in `run()`/`resume()` finally blocks; `[MODIFY] src/specweaver/core/flow/handlers/base.py` — `task_id` on `RunContext`; `[NEW] tests/unit/core/flow/engine/test_handover.py` (24 tests); `[NEW] tests/unit/core/flow/engine/test_runner_handover.py` (6 tests); `[NEW] tests/integration/core/flow/engine/test_handover_persistence.py` (3 tests) | Save protocol + runner wiring + unit and integration tests |
| CB-2 | `[NEW] tests/unit/workspace/memory/test_bootstrap_protocol.py` (5 tests); `[MODIFY] docs/dev_guides/agent_memory_state_tracking.md`; `[MODIFY] docs/dev_guides/pipeline_engine_guide.md`; `[MODIFY] D-INTL-06_design.md` — Progress Tracker update | FR-9 verification tests + docs; zero production code |

Docs:

- `docs/dev_guides/agent_memory_state_tracking.md` — **Section 9: Handover Save Protocol**:
  `save_handover_context()` fires automatically on pipeline completion; how telemetry is collected
  from `StepResult` fields; the `files_touched` convention for handler authors; sub-pipeline guard;
  fail-safe guarantee.
- `docs/dev_guides/pipeline_engine_guide.md` — **Section 11: Handover Persistence**:
  `_save_handover()` in the `finally` block; the `files_touched` output key convention; the
  forward-compatible `RunContext.task_id` field.
- `D-INTL-06_design.md` — Progress Tracker (SF-03 Impl Plan ✅) and session status.

## Tests

`tests/unit/core/flow/engine/test_handover.py` — `save_handover_context()` with a mocked DB:

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

`tests/unit/core/flow/engine/test_runner_handover.py` — the runner calls `save_handover_context()`
(mocked):

| # | Test Case | Scenario | Expected |
|---|-----------|----------|----------|
| 1 | `test_handover_called_on_run_complete` | Pipeline completes all steps | `save_handover_context` awaited in finally |
| 2 | `test_handover_called_on_run_failed` | Pipeline step fails → FAILED | `save_handover_context` awaited |
| 3 | `test_handover_called_on_park` | Pipeline parks at HITL gate | `save_handover_context` called (guard inside function handles skip) |
| 4 | `test_handover_called_on_resume_complete` | Resumed run completes | `save_handover_context` awaited |
| 5 | `test_handover_exception_does_not_crash_runner` | `save_handover_context` raises | Runner returns normally |
| 6 | `test_handover_called_on_empty_pipeline` | 0 steps | `save_handover_context` called (guard inside function handles skip) |

`tests/integration/core/flow/engine/test_handover_persistence.py` — real in-memory SQLite (RT-7):

| # | Test Case | Scenario | Expected |
|---|-----------|----------|----------|
| 1 | `test_handover_persisted_on_complete` | Pipeline completes, real DB with IN_PROGRESS task | Task `handover_context` column is non-null, contains valid JSON |
| 2 | `test_handover_persisted_on_failure` | Pipeline fails, real DB with IN_PROGRESS task | Task `handover_context` contains error info |
| 3 | `test_handover_noop_when_no_task` | Pipeline completes, real DB with NO tasks | No crash, no DB write |

`tests/unit/workspace/memory/test_bootstrap_protocol.py` — explicit FR-9 bootstrap tests:

| # | Test Case | Scenario | Expected |
|---|-----------|----------|----------|
| 1 | `test_bootstrap_hydrates_existing_handover` | Task with `handover_context` JSON | `HydrationResult.handover_notes` contains summary |
| 2 | `test_bootstrap_with_corrupt_handover` | Task with invalid JSON | WARNING logged, task included without summary |
| 3 | `test_bootstrap_with_null_handover` | Task with `handover_context = None` | Task included, no handover notes |
| 4 | `test_bootstrap_trust_tagging` | Task with handover context | `format_prompt_block()` includes `_trust: "low"` |
| 5 | `test_bootstrap_multiple_tasks_with_handover` | 3 IN_PROGRESS tasks, 2 with handover | Both summaries appear in `handover_notes` |

## Decisions (audit)

**Static summary (RT-8).** FR-8 suggests an "LLM-generated 1-sentence status". The summary is the
static string `"Pipeline '{name}' {status}. {N} steps executed."` instead: an LLM call in a
`finally` cleanup path adds latency, needs LLM access in a failure scenario, and can hallucinate.

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
