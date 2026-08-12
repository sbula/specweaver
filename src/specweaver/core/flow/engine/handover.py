# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
import uuid

from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepStatus
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.workspace.memory.models import HandoverContext
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.memory.store import TaskStatus

logger = logging.getLogger(__name__)



def _skip_reason(context: RunContext, run: PipelineRun) -> str | None:
    """Why this run has no handover to save, or None when it does.

    Four guards that were four early returns inside one 90-line function. Collected here so the
    *reasons* read as a list -- the caller then has one branch instead of four.
    """
    if run.status in (RunStatus.PARKED, RunStatus.NOT_STARTED):
        return f"status is {run.status.value}"
    if run.parent_run_id is not None:
        return "sub-pipeline execution"
    if not run.step_records:
        return "pipeline has 0 steps executed"
    if context.db is None:
        return "database connection is missing"
    return None


def _bounded(values: list[str], *, cap: int, width: int) -> list[str]:
    """De-duplicate, cap the count, truncate each entry.

    Errors and files were bounded by the same three operations written twice. The bounding is not
    cosmetic: it keeps the payload under the 8KB column limit `Task.handover_context` enforces.
    """
    return [v[:width] for v in list(dict.fromkeys(values))[:cap]]


def _failed_step_errors(run: PipelineRun) -> list[str]:
    return [
        str(step.result.error_message)
        for step in run.step_records
        if step.result
        and step.result.status in (StepStatus.FAILED, StepStatus.ERROR)
        and step.result.error_message
    ]


def _files_touched(run: PipelineRun) -> list[str]:
    files: list[str] = []
    for step in run.step_records:
        if step.result and isinstance(step.result.output, dict):
            touched = step.result.output.get("files_touched", [])
            if isinstance(touched, list):
                files.extend(str(f) for f in touched)
    return files


async def _target_task_id(repo: MemoryRepository, context: RunContext) -> uuid.UUID | None:
    """The task the handover attaches to: this run's, else the newest IN_PROGRESS one."""
    if context.run.task_id is not None:
        return uuid.UUID(context.run.task_id)

    active = await repo.list_tasks(
        project_name=context.project_path.name, status=TaskStatus.IN_PROGRESS
    )
    return uuid.UUID(str(active[0]["id"])) if active else None


async def save_handover_context(context: RunContext, run: PipelineRun) -> None:
    """Persist pipeline telemetry to the Agent Memory Bank for handover scenarios.

    **Fail-safe by contract.** Anything that goes wrong -- database unavailable, missing task id,
    serialization error -- is logged and swallowed so pipeline cleanup continues. The runner calls
    this from a `finally:`, so raising here would replace whatever outcome the run actually had.
    """
    try:
        skip = _skip_reason(context, run)
        if skip is not None:
            logger.debug("[run_id=%s] Skipping handover save: %s", run.run_id, skip)
            return

        handover_ctx = HandoverContext(
            summary=(
                f"Pipeline '{run.pipeline_name}' {run.status.value}. "
                f"{len(run.step_records)} steps executed."
            ),
            files_touched=_bounded(_files_touched(run), cap=30, width=150),
            errors_encountered=_bounded(_failed_step_errors(run), cap=10, width=500),
            metadata={
                "run_id": run.run_id,
                "pipeline_name": run.pipeline_name,
                "step_count": len(run.step_records),
                "status": run.status.value,
            },
        )

        async with context.db.async_session_scope() as session:
            repo = MemoryRepository(session)
            target_task_id = await _target_task_id(repo, context)
            if target_task_id is None:
                logger.warning(
                    "[run_id=%s] Skipping handover save: No active task found for persistence.",
                    run.run_id,
                )
                return

            await repo.update_handover_context(target_task_id, handover_ctx)
            logger.info(
                "[run_id=%s] Successfully saved handover context to task %s",
                run.run_id,
                target_task_id,
            )

    except Exception as exc:
        logger.warning(
            "[run_id=%s] Failed to save handover context: %s", run.run_id, str(exc), exc_info=True
        )
