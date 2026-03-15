# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Pipeline runner — sequential step execution with state persistence.

Walks through a ``PipelineDefinition`` step-by-step, dispatching each
step to the appropriate handler via the ``StepHandlerRegistry``. State
is persisted to SQLite after each step so interrupted runs can resume.

Supports gates (AUTO/HITL), retry on failure, loop-back to earlier
steps, and feedback injection into the RunContext for prompt enrichment.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

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
    from specweaver.flow.models import PipelineDefinition
    from specweaver.flow.store import StateStore


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
    """

    def __init__(
        self,
        pipeline: PipelineDefinition,
        context: RunContext,
        *,
        registry: StepHandlerRegistry | None = None,
        store: StateStore | None = None,
    ) -> None:
        self._pipeline = pipeline
        self._context = context
        self._registry = registry or StepHandlerRegistry()
        self._store = store
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
        return await self._execute_loop(run)

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
            raise ValueError(msg)

        run = self._store.load_run(run_id)
        if run is None:
            msg = f"Run '{run_id}' not found"
            raise ValueError(msg)

        # Reset from terminal/parked state to running
        run.status = RunStatus.RUNNING
        return await self._execute_loop(run)

    # ------------------------------------------------------------------
    # Core execution loop
    # ------------------------------------------------------------------

    async def _execute_loop(self, run: PipelineRun) -> PipelineRun:  # noqa: C901
        """Walk through steps starting from current_step."""
        # Empty pipeline → immediately complete
        if not run.step_records:
            run.status = RunStatus.COMPLETED
            self._persist(run)
            self._log(run, "run_completed")
            return run

        run.status = RunStatus.RUNNING
        self._persist(run)
        self._log(run, "run_started")

        # Per-step attempt counters for retry tracking
        attempts: dict[int, int] = {}

        while run.current_step < len(run.step_records):
            step_idx = run.current_step
            step_def = self._pipeline.steps[step_idx]
            attempts.setdefault(step_idx, 0)

            # Look up handler
            handler = self._registry.get(step_def.action, step_def.target)
            if handler is None:
                error_result = StepResult(
                    status=StepStatus.ERROR,
                    error_message=(
                        f"No handler registered for {step_def.action.value}+{step_def.target.value}"
                    ),
                    started_at=_now_iso(),
                    completed_at=_now_iso(),
                )
                run.fail_current_step(error_result)
                self._persist(run)
                self._log(run, "step_failed", step_def.name)
                return run

            # Execute step
            run.mark_step_running()
            self._persist(run)
            self._log(run, "step_started", step_def.name)

            try:
                result = await handler.execute(step_def, self._context)
            except Exception as exc:
                result = StepResult(
                    status=StepStatus.ERROR,
                    error_message=str(exc),
                    started_at=_now_iso(),
                    completed_at=_now_iso(),
                )

            # Process result: WAITING_FOR_INPUT always parks
            if result.status == StepStatus.WAITING_FOR_INPUT:
                run.park_current_step(result)
                self._persist(run)
                self._log(run, "run_parked", step_def.name)
                return run

            # Gate evaluation ------------------------------------------------
            gate = step_def.gate
            if gate is not None:
                # Inject feedback for loop-back before evaluating
                verdict = self._gate_evaluator.evaluate(
                    gate, result, step_def, run, attempts,
                )
                # Handle side effects (persistence, logging, feedback)
                if verdict == "park":
                    self._persist(run)
                    self._log(run, "gate_hitl_park", step_def.name)
                    return run
                if verdict == "stop":
                    self._persist(run)
                    self._log(run, "step_failed", step_def.name)
                    return run
                if verdict == "retry":
                    self._persist(run)
                    self._log(run, "step_retry", step_def.name)
                    continue  # re-execute same step
                if verdict == "loop_back":
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
                    run.fail_current_step(result)
                    self._persist(run)
                    self._log(run, "step_failed", step_def.name)
                    return run

            # Success — advance
            run.complete_current_step(result)
            run.updated_at = _now_iso()
            self._persist(run)
            self._log(run, "step_completed", step_def.name)

        # All steps done
        self._log(run, "run_completed")
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
