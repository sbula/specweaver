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

from specweaver.core.flow.engine.gates import GateEvaluator
from specweaver.core.flow.engine.hydration import rehydrate_from_records
from specweaver.core.flow.engine.runner_utils import (
    RunnerEventCallback,
    _now_iso,
    execute_run,
    isolate_sub_run_context,
    resolve_should_isolate,
    seed_dal_level,
    setup_sandbox_caches,
    verify_vault_security,
)
from specweaver.core.flow.engine.state import (
    PipelineRun,
    RunStatus,
    StepRecord,
)
from specweaver.core.flow.engine.step_execution import (
    LoopAction,
    LoopState,
    run_one_step,
)
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.core.flow.handlers.base import RunContext

logger = logging.getLogger(__name__)

#: `resolve_should_isolate` is re-exported, not used here — `TECH-020` moved its only call site
#: into `step_execution.execute_step`, but existing tests import it from this module and the
#: refactor's contract is that they pass untouched. Explicit so the next `ruff --fix` does not
#: quietly delete it again, which is exactly how it broke mid-refactor.
__all__ = ["PipelineRunner", "resolve_should_isolate"]


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
        self._context = isolate_sub_run_context(self._context, parent_run_id)
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

    async def _execute_loop(
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

        state = LoopState.for_run(run, approve_parked=approve_parked)

        while run.current_step < len(run.step_records):
            step_idx = run.current_step
            step_def = self._pipeline.steps[step_idx]
            state.attempts.setdefault(step_idx, 0)

            if await run_one_step(self, run, state, step_def, step_idx, total) is LoopAction.RETURN:
                return run

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
