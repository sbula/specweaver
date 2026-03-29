# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

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
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from specweaver.flow.gates import GateEvaluator
from specweaver.flow.handlers import RunContext, StepHandlerRegistry
from specweaver.flow.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
    StepResult,
    StepStatus,
)

if TYPE_CHECKING:
    from specweaver.flow.models import PipelineDefinition, PipelineStep
    from specweaver.flow.store import StateStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event callback protocol (prepared for future typed emitter)
# ---------------------------------------------------------------------------


@runtime_checkable
class RunnerEventCallback(Protocol):
    """Protocol for runner event callbacks.

    Prepared for future upgrade to a typed event emitter class.
    For now, the simple ``on_event`` callable satisfies this protocol.
    """

    def __call__(
        self,
        event: str,
        *,
        step_idx: int | None = None,
        step_name: str | None = None,
        step_def: PipelineStep | None = None,
        total_steps: int | None = None,
        result: StepResult | None = None,
        run: PipelineRun | None = None,
        verdict: str | None = None,
        **kwargs: Any,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ---------------------------------------------------------------------------
# Pipeline runner
# ---------------------------------------------------------------------------


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
        self._gate_evaluator = GateEvaluator(pipeline)

    async def run(self) -> PipelineRun:
        """Execute the pipeline from the beginning.

        Returns:
            The final PipelineRun state (COMPLETED, FAILED, or PARKED).
        """
        now = _now_iso()
        run = PipelineRun(
            run_id=str(uuid.uuid4()),
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
        try:
            return await self._execute_loop(run)
        finally:
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
        try:
            return await self._execute_loop(run)
        finally:
            self._flush_telemetry()

    # ------------------------------------------------------------------
    # Core execution loop
    # ------------------------------------------------------------------

    async def _execute_loop(self, run: PipelineRun) -> PipelineRun:  # noqa: C901
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

        while run.current_step < len(run.step_records):
            step_idx = run.current_step
            step_def = self._pipeline.steps[step_idx]
            attempts.setdefault(step_idx, 0)

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

            # Success — advance
            logger.debug(
                "[run_id=%s] Step '%s' completed with status=%s",
                run.run_id,
                step_def.name,
                result.status.value,
            )
            run.complete_current_step(result)
            run.updated_at = _now_iso()
            self._persist(run)
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
        """Save state if a store is configured."""
        if self._store is not None:
            run.updated_at = _now_iso()
            self._store.save_run(run)

    def _log(
        self,
        run: PipelineRun,
        event: str,
        step_name: str | None = None,
    ) -> None:
        """Log an audit event if a store is configured."""
        if self._store is not None:
            self._store.log_event(
                run.run_id,
                event,
                step_name=step_name,
            )

    def _emit(self, event: str, **kwargs: Any) -> None:
        """Fire a progress event to the callback, if configured."""
        if self._on_event is not None:
            self._on_event(event, **kwargs)

    def _flush_telemetry(self) -> None:
        """Flush telemetry if context.llm is a TelemetryCollector.

        Uses ``context.db`` (Database) — NOT ``self._store`` (PipelineRunStore).
        """
        from specweaver.llm.collector import TelemetryCollector

        llm = getattr(self._context, "llm", None)
        if not isinstance(llm, TelemetryCollector):
            return

        db = getattr(self._context, "db", None)
        if db is None:
            logger.warning("Cannot flush telemetry: no db on RunContext")
            return

        try:
            llm.flush(db)
        except Exception:
            logger.warning("Failed to flush telemetry", exc_info=True)
