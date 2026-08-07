# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pipeline runner — sequential step execution with state persistence.

Walks through a ``PipelineDefinition`` step-by-step, dispatching each
step to the appropriate handler via the ``StepHandlerRegistry``. State
is persisted to SQLite after each step so interrupted runs can resume.

Supports gates (AUTO/HITL), retry on failure, loop-back to earlier
steps, and feedback injection into the RunContext for prompt enrichment.

Progress reporting is done via an optional ``on_event`` callback,
allowing the CLI layer to display step-by-step progress without
coupling the runner to any UI framework.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.approval import try_approve_parked_step
from specweaver.core.flow.engine.gates import GateEvaluator
from specweaver.core.flow.engine.hydration import hydrate_plan_context, rehydrate_from_records
from specweaver.core.flow.engine.routers import resolve_route_target
from specweaver.core.flow.engine.runner_utils import (
    RunnerEventCallback,
    _now_iso,
    execute_run,
    resolve_should_isolate,
    seed_dal_level,
    setup_sandbox_caches,
    verify_vault_security,
)
from specweaver.core.flow.engine.staleness import try_staleness_bypass
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.core.flow.handlers.base import RunContext

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Executes a pipeline definition step by step.

    Args:
        pipeline: The pipeline to execute.
        context: Run context with project paths, LLM, settings, etc.
        registry: Handler registry (default: all built-in handlers).
        store: Optional state store for persistence and resume.
        on_event: Optional callback for progress reporting. Called with
            event name and keyword arguments describing the event.
    """

    def __init__(
        self,
        pipeline: PipelineDefinition,
        context: RunContext,
        *,
        registry: StepHandlerRegistry | None = None,
        store: StateStore | None = None,
        on_event: RunnerEventCallback | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._context = context
        self._registry = registry or StepHandlerRegistry()
        self._store = store
        self._on_event = on_event
        self._gate_evaluator = GateEvaluator(pipeline, context)

        # INT-US-21 SF-03 CB-2 (R-13) — see `current_run_id`.
        self._current_run_id: str | None = None

        from specweaver.core.flow.engine.routers import RouterEvaluator

        self._router_evaluator = RouterEvaluator()

        # SF-2 (FR-3): Intrinsically load the DALLevel of the execution target
        seed_dal_level(self._context)

    def _setup_sandbox_caches(self, wt_dir: str) -> None:
        setup_sandbox_caches(self._context, wt_dir, logger)

    @property
    def current_run_id(self) -> str | None:
        """Id of the run in progress (or the last one); None before any run starts.

        ``run()`` builds its ``PipelineRun`` as a local, so an interrupt took the id down with the
        frame and the CLI could only print ``sw run --resume`` with nothing to resume. The
        ``finally:`` block already persists the run, so the id IS resumable — it just was not
        reachable. Survives an exception escaping ``run()``/``resume()``, which is the whole point.
        """
        return self._current_run_id

    async def run(self, parent_run_id: str | None = None) -> PipelineRun:
        """Execute the pipeline from the beginning.

        Args:
            parent_run_id: Optional ID of the parent pipeline run spawning this run.

        Returns:
            The final PipelineRun state (COMPLETED, FAILED, or PARKED).
        """
        verify_vault_security(self._context)
        now = _now_iso()

        run = PipelineRun(
            run_id=str(uuid.uuid4()),
            parent_run_id=parent_run_id,
            pipeline_name=self._pipeline.name,
            project_name=self._context.project_path.name,
            spec_path=str(self._context.spec_path),
            status=RunStatus.NOT_STARTED,
            current_step=0,
            step_records=[StepRecord(step_name=step.name) for step in self._pipeline.steps],
            started_at=now,
            updated_at=now,
        )
        logger.info(
            "Starting pipeline '%s' run_id=%s (%d steps, project=%s, spec=%s)",
            self._pipeline.name,
            run.run_id,
            len(run.step_records),
            self._context.project_path.name,
            self._context.spec_path.name,
        )
        self._current_run_id = run.run_id

        from specweaver.core.config.database import cqrs_context

        try:
            async with cqrs_context():
                return await execute_run(self, run, logger)
        finally:
            await self._save_handover(run)
            self._flush_telemetry()

    async def resume(self, run_id: str) -> PipelineRun:
        """Resume a previously interrupted run.

        Loads the run from the store and continues from the current step.

        Args:
            run_id: The run ID to resume.

        Returns:
            The final PipelineRun state.

        Raises:
            ValueError: If the run is not found in the store.
        """
        if self._store is None:
            msg = "Cannot resume: no store configured"
            logger.error(msg)
            raise ValueError(msg)

        self._current_run_id = run_id
        verify_vault_security(self._context)

        run = self._store.load_run(run_id)
        if run is None:
            msg = f"Run '{run_id}' not found"
            logger.error(msg)
            raise ValueError(msg)

        logger.info(
            "Resuming run_id=%s pipeline='%s' from step %d/%d",
            run_id,
            run.pipeline_name,
            run.current_step,
            len(run.step_records),
        )
        # Reset from terminal/parked state to running
        run.status = RunStatus.RUNNING

        # INT-US-21 FR-3: the plan context lives in memory and died with the previous session.
        # Rebuild it from persisted step records BEFORE the loop starts, so the first resumed
        # handler sees the same context a same-session handler would have.
        rehydrate_from_records(self._pipeline, run, self._context)

        from specweaver.core.config.database import cqrs_context

        try:
            async with cqrs_context():
                # INT-US-21 FR-4: the human chose to resume, which IS the approval of a
                # reviewed HITL gate-park. One-shot — consumed on the first loop iteration.
                return await execute_run(self, run, logger, approve_parked=True)
        finally:
            await self._save_handover(run)
            self._flush_telemetry()

    # ------------------------------------------------------------------
    # Core execution loop
    # ------------------------------------------------------------------

    async def _execute_loop(  # noqa: C901
        self,
        run: PipelineRun,
        *,
        approve_parked: bool = False,
    ) -> PipelineRun:
        """Walk through steps starting from current_step."""
        total = len(run.step_records)

        # Empty pipeline → immediately complete
        if not run.step_records:
            logger.warning(
                "Pipeline '%s' run_id=%s has no steps — completing immediately",
                run.pipeline_name,
                run.run_id,
            )
            run.status = RunStatus.COMPLETED
            self._persist(run)
            self._log(run, "run_completed")
            self._emit("run_completed", run=run)
            return run

        run.status = RunStatus.RUNNING
        self._persist(run)
        self._log(run, "run_started")
        self._emit("run_started", run=run, total_steps=total)

        # Per-step attempt counters for retry tracking
        attempts: dict[int, int] = {}
        route_jumps: int = 0

        while run.current_step < len(run.step_records):
            step_idx = run.current_step
            step_def = self._pipeline.steps[step_idx]
            attempts.setdefault(step_idx, 0)

            # INT-US-21 FR-4 — MUST stay at the very top of the loop body. Two later blocks
            # would otherwise destroy the evidence this decision reads:
            #   * the staleness bypass below can complete the step as SKIPPED and `continue`,
            #     discarding the human's approval and the stored result;
            #   * mark_step_running() overwrites record.status WAITING_FOR_INPUT -> RUNNING.
            # One-shot: consumed on the first iteration whether or not it approves, so a stale
            # WAITING_FOR_INPUT record further down the pipeline can never be auto-approved.
            if approve_parked:
                approve_parked = False  # one-shot, consumed whether or not it approves
                if try_approve_parked_step(self, run, step_def, step_idx, total):
                    continue

            # Look up handler
            handler = self._registry.get(step_def.action, step_def.target)
            if handler is None:
                error_msg = (
                    f"No handler registered for {step_def.action.value}+{step_def.target.value}"
                )
                logger.error(
                    "[run_id=%s] Step %d/%d '%s': %s",
                    run.run_id,
                    step_idx + 1,
                    total,
                    step_def.name,
                    error_msg,
                )
                error_result = StepResult(
                    status=StepStatus.ERROR,
                    error_message=error_msg,
                    started_at=_now_iso(),
                    completed_at=_now_iso(),
                )
                run.fail_current_step(error_result)
                self._persist(run)
                self._log(run, "step_failed", step_def.name)
                self._emit(
                    "step_failed",
                    step_idx=step_idx,
                    step_name=step_def.name,
                    step_def=step_def,
                    total_steps=total,
                    result=error_result,
                )
                self._emit("run_failed", run=run)
                return run

            # Execute step

            if try_staleness_bypass(self, run, step_def, step_idx, total):
                continue

            run.mark_step_running()
            self._persist(run)
            self._log(run, "step_started", step_def.name)
            logger.info(
                "[run_id=%s] Step %d/%d '%s' (%s+%s) — executing via %s",
                run.run_id,
                step_idx + 1,
                total,
                step_def.name,
                step_def.action.value,
                step_def.target.value,
                type(handler).__name__,
            )
            self._emit(
                "step_started",
                step_idx=step_idx,
                step_name=step_def.name,
                step_def=step_def,
                total_steps=total,
            )

            try:
                # Inject flow state for downstream tracking
                self._context.run_id = run.run_id
                self._context.step_records = [r.model_dump() for r in run.step_records]
                self._context.pipeline_runner = self

                # INT-US-09: tri-state isolation gate (see resolve_should_isolate).
                # C-EXEC-06: inside an active session, ALL steps already run in the one session
                # worktree — unconditionally bypass per-step isolation (even explicit
                # use_worktree=True) so no nested worktree is created.
                if not getattr(self, "_session_active", False) and resolve_should_isolate(
                    step_def, self._context
                ):
                    from specweaver.core.flow.engine.runner_utils import execute_in_sandbox

                    result = await execute_in_sandbox(self, handler, step_def, run, logger)
                else:
                    result = await handler.execute(step_def, self._context)
            except Exception as exc:
                logger.exception(
                    "[run_id=%s] Step '%s' raised unhandled exception",
                    run.run_id,
                    step_def.name,
                )
                result = StepResult(
                    status=StepStatus.ERROR,
                    error_message=str(exc),
                    started_at=_now_iso(),
                    completed_at=_now_iso(),
                )

            # Process result: WAITING_FOR_INPUT always parks
            if result.status == StepStatus.WAITING_FOR_INPUT:
                logger.info(
                    "[run_id=%s] Step '%s' waiting for user input — parking run",
                    run.run_id,
                    step_def.name,
                )
                run.park_current_step(result)
                self._persist(run)
                self._log(run, "run_parked", step_def.name)
                self._emit(
                    "step_parked",
                    step_idx=step_idx,
                    step_name=step_def.name,
                    step_def=step_def,
                    total_steps=total,
                    result=result,
                )
                self._emit("run_parked", run=run, step_name=step_def.name)
                return run

            # Gate evaluation ------------------------------------------------
            gate = step_def.gate
            if gate is not None:
                logger.debug(
                    "[run_id=%s] Evaluating gate on step '%s' (type=%s, condition=%s)",
                    run.run_id,
                    step_def.name,
                    gate.type.value,
                    gate.condition.value,
                )
                verdict = self._gate_evaluator.evaluate(
                    gate,
                    result,
                    step_def,
                    run,
                    attempts,
                )
                logger.info(
                    "[run_id=%s] Gate verdict for step '%s': %s (result_status=%s)",
                    run.run_id,
                    step_def.name,
                    verdict,
                    result.status.value,
                )
                self._emit(
                    "gate_result",
                    step_idx=step_idx,
                    step_name=step_def.name,
                    step_def=step_def,
                    total_steps=total,
                    result=result,
                    verdict=verdict,
                )
                # Handle side effects (persistence, logging, feedback)
                if verdict == "park":
                    logger.info(
                        "[run_id=%s] HITL gate on '%s' — parking for human review",
                        run.run_id,
                        step_def.name,
                    )
                    self._persist(run)
                    self._log(run, "gate_hitl_park", step_def.name)
                    self._emit("run_parked", run=run, step_name=step_def.name)
                    return run
                if verdict == "stop":
                    logger.error(
                        "[run_id=%s] Gate on '%s' failed — stopping pipeline",
                        run.run_id,
                        step_def.name,
                    )
                    self._persist(run)
                    self._log(run, "step_failed", step_def.name)
                    self._emit(
                        "step_failed",
                        step_idx=step_idx,
                        step_name=step_def.name,
                        step_def=step_def,
                        total_steps=total,
                        result=result,
                    )
                    self._emit("run_failed", run=run)
                    return run
                if verdict == "retry":
                    logger.info(
                        "[run_id=%s] Retrying step '%s' (attempt %d)",
                        run.run_id,
                        step_def.name,
                        attempts.get(run.current_step, 0),
                    )
                    self._persist(run)
                    self._log(run, "step_retry", step_def.name)
                    continue  # re-execute same step
                if verdict == "loop_back":
                    logger.info(
                        "[run_id=%s] Looping back from '%s' to '%s'",
                        run.run_id,
                        step_def.name,
                        gate.loop_target or "?",
                    )
                    # Inject feedback into context
                    self._gate_evaluator.inject_feedback(
                        self._context,
                        step_def.name,
                        gate.loop_target or "",
                        result,
                    )
                    self._persist(run)
                    self._log(run, "step_loop_back", step_def.name)
                    continue  # current_step was moved
                # verdict == "advance" → fall through
                self._log(run, "gate_passed", step_def.name)
            else:
                # No gate: fail on error/failure (backwards compat)
                if result.status in (StepStatus.FAILED, StepStatus.ERROR):
                    logger.error(
                        "[run_id=%s] Step '%s' %s: %s",
                        run.run_id,
                        step_def.name,
                        result.status.value,
                        result.error_message or "no error message",
                    )
                    run.fail_current_step(result)
                    self._persist(run)
                    self._log(run, "step_failed", step_def.name)
                    self._emit(
                        "step_failed",
                        step_idx=step_idx,
                        step_name=step_def.name,
                        step_def=step_def,
                        total_steps=total,
                        result=result,
                    )
                    self._emit("run_failed", run=run)
                    return run

            # Success — advance.
            # INT-US-21 FR-2: this is the join point BOTH advance paths reach — the gate's
            # "advance" fall-through above and the no-gate else-branch. Hydrating inside the
            # gate block would silently skip every gateless plan/decompose step.
            hydrate_plan_context(step_def, result, self._context)

            logger.debug(
                "[run_id=%s] Step '%s' completed with status=%s",
                run.run_id,
                step_def.name,
                result.status.value,
            )

            router = step_def.router
            if router is not None:
                target_idx, route_error, route_jumps = resolve_route_target(
                    self._router_evaluator,
                    router,
                    result.output,
                    self._pipeline,
                    run.current_step,
                    route_jumps,
                )
                if route_error is not None or target_idx is None:
                    error_msg = route_error or "Router resolution failed"
                    logger.error("[run_id=%s] %s", run.run_id, error_msg)
                    run.fail_current_step(
                        StepResult(
                            status=StepStatus.ERROR,
                            error_message=error_msg,
                            started_at=_now_iso(),
                            completed_at=_now_iso(),
                        )
                    )
                    self._persist(run)
                    self._emit("run_failed", run=run)
                    return run

                target_step_name = self._pipeline.steps[target_idx].name
                logger.info(
                    "[run_id=%s] Router resolved target '%s' (index %d). Routing.",
                    run.run_id,
                    target_step_name,
                    target_idx,
                )
                self._emit(
                    "step_routed",
                    step_idx=step_idx,
                    step_name=step_def.name,
                    target_step=target_step_name,
                    target_idx=target_idx,
                    run=run,
                )
                self._log(run, "step_routed", step_def.name)
                run.route_to_step(result, target_idx)
            else:
                run.complete_current_step(result)

            run.updated_at = _now_iso()
            self._persist(run)
            if router is None:
                self._log(run, "step_completed", step_def.name)
            self._emit(
                "step_completed",
                step_idx=step_idx,
                step_name=step_def.name,
                step_def=step_def,
                total_steps=total,
                result=result,
            )

        # All steps done
        logger.info(
            "Pipeline '%s' run_id=%s completed successfully (%d steps)",
            run.pipeline_name,
            run.run_id,
            total,
        )
        self._log(run, "run_completed")
        self._emit("run_completed", run=run)
        return run

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist(self, run: PipelineRun) -> None:
        if self._store is not None:
            run.updated_at = _now_iso()
            self._store.save_run(run)

    def _log(self, run: PipelineRun, event: str, step_name: str | None = None) -> None:
        if self._store is not None:
            self._store.log_event(run.run_id, event, step_name=step_name)

    def _emit(self, event: str, **kwargs: Any) -> None:
        if self._on_event is not None:
            self._on_event(event, **kwargs)

    def _flush_telemetry(self) -> None:
        from specweaver.core.flow.engine.runner_utils import flush_telemetry

        flush_telemetry(self._context, logger)

    async def _save_handover(self, run: PipelineRun) -> None:
        try:
            from specweaver.core.flow.engine.handover import save_handover_context

            await save_handover_context(self._context, run)
        except Exception as exc:
            logger.warning("Failed to save handover context from runner: %s", exc)
