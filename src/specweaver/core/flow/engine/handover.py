# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import logging
import uuid
from typing import Any

from specweaver.core.flow.engine.state import PipelineRun, RunStatus, StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.workspace.memory.models import HandoverContext
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.memory.store import TaskStatus

logger = logging.getLogger(__name__)


async def save_handover_context(context: RunContext, run: PipelineRun) -> None:  # noqa: C901
    """
    Persists pipeline telemetry to the Agent Memory Bank for handover scenarios.

    This function is fail-safe. If anything goes wrong (e.g., database unavailable,
    missing task IDs, serialization errors), it gracefully catches the exception, logs
    a warning, and allows the pipeline cleanup to continue uninterrupted.

    Args:
        context: The execution context (provides database connection and task targeting).
        run: The current state of the pipeline run.
    """
    try:
        # 1. Status and Integrity Guards
        if run.status in (RunStatus.PARKED, RunStatus.NOT_STARTED):
            logger.debug(
                "[run_id=%s] Skipping handover save for status: %s", run.run_id, run.status.value
            )
            return

        if run.parent_run_id is not None:
            logger.debug("[run_id=%s] Skipping handover save: Sub-pipeline execution.", run.run_id)
            return

        if not run.step_records:
            logger.debug(
                "[run_id=%s] Skipping handover save: Pipeline has 0 steps executed.", run.run_id
            )
            return

        if context.db is None:
            logger.warning(
                "[run_id=%s] Skipping handover save: Database connection is missing.", run.run_id
            )
            return

        # 2. Telemetry Collection & Mathematical Bounding
        # We strictly truncate strings to prevent theoretical 8KB payload bounds exceptions.

        errors: list[str] = []
        for step in run.step_records:
            if (
                step.result
                and step.result.status in (StepStatus.FAILED, StepStatus.ERROR)
                and step.result.error_message
            ):
                errors.append(str(step.result.error_message))

        # Deduplicate, cap at 10 items, truncate to 500 chars
        unique_errors = list(dict.fromkeys(errors))[:10]
        truncated_errors = [err[:500] for err in unique_errors]

        files: list[str] = []
        for step in run.step_records:
            if step.result and isinstance(step.result.output, dict):
                files_touched = step.result.output.get("files_touched", [])
                if isinstance(files_touched, list):
                    files.extend(str(f) for f in files_touched)

        # Deduplicate, cap at 30 items, truncate to 150 chars
        unique_files = list(dict.fromkeys(files))[:30]
        truncated_files = [f[:150] for f in unique_files]

        summary = f"Pipeline '{run.pipeline_name}' {run.status.value}. {len(run.step_records)} steps executed."

        metadata: dict[str, Any] = {
            "run_id": run.run_id,
            "pipeline_name": run.pipeline_name,
            "step_count": len(run.step_records),
            "status": run.status.value,
        }

        handover_ctx = HandoverContext(
            summary=summary,
            files_touched=truncated_files,
            errors_encountered=truncated_errors,
            metadata=metadata,
        )

        # 3. Persistence
        async with context.db.async_session_scope() as session:
            repo = MemoryRepository(session)

            # Task Discovery
            target_task_id: uuid.UUID | None = None
            if context.task_id is not None:
                target_task_id = uuid.UUID(context.task_id)
            else:
                # Fallback to the most recently created IN_PROGRESS task
                active_tasks = await repo.list_tasks(
                    project_name=context.project_path.name, status=TaskStatus.IN_PROGRESS
                )
                if active_tasks and len(active_tasks) > 0:
                    target_task_id = uuid.UUID(str(active_tasks[0]["id"]))

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
