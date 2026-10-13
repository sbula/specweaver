# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The memory task a run works: one per spec, opened at the start, given its end state at the end.

Without it nothing creates a task, so the handover has nowhere to land and every agent's memory
is empty [agreed 2026-10-13]. A memory failure never fails the run.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from specweaver.core.flow.engine.naming import registered_name
from specweaver.core.flow.engine.state import RunStatus
from specweaver.workspace.memory.store import TaskStatus, TransitionReason

if TYPE_CHECKING:
    from specweaver.core.flow.engine.state import PipelineRun
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.workspace.memory.repository import MemoryRepository

logger = logging.getLogger(__name__)

#: Statuses a run's task can be reopened from, and the steps the state machine needs to get there.
_REOPEN: dict[TaskStatus, tuple[TaskStatus, ...]] = {
    TaskStatus.PENDING: (TaskStatus.IN_PROGRESS,),
    TaskStatus.DONE: (TaskStatus.IN_PROGRESS,),
    TaskStatus.BLOCKED: (TaskStatus.PENDING, TaskStatus.IN_PROGRESS),
    TaskStatus.UPSTREAM_BLOCKED: (TaskStatus.PENDING, TaskStatus.IN_PROGRESS),
    TaskStatus.IN_PROGRESS: (),
}

#: The audit-trail reason for moving a task into each state.
_REASON: dict[TaskStatus, TransitionReason] = {
    TaskStatus.IN_PROGRESS: TransitionReason.ACQUIRED,
    TaskStatus.PENDING: TransitionReason.RELEASED,
    TaskStatus.DONE: TransitionReason.COMPLETED,
    TaskStatus.BLOCKED: TransitionReason.AGENT_FAILURE,
}

#: The task's state once a run has ended; a parked run keeps its task open for the resume.
_END: dict[RunStatus, TaskStatus] = {
    RunStatus.COMPLETED: TaskStatus.DONE,
    RunStatus.FAILED: TaskStatus.BLOCKED,
    RunStatus.ABORTED: TaskStatus.BLOCKED,
}


def _title(context: RunContext) -> str:
    """The spec's path inside the project, which names its task."""
    spec = context.spec_path.resolve()
    try:
        return spec.relative_to(context.project_path.resolve()).as_posix()
    except ValueError:
        return spec.as_posix()


def _applies(context: RunContext, run: PipelineRun) -> bool:
    return run.parent_run_id is None and getattr(context, "db", None) is not None


async def open_task(context: RunContext, run: PipelineRun) -> str | None:
    """The id of the spec's task, created if new and moved to IN_PROGRESS; None when skipped."""
    if not _applies(context, run):
        return None
    from specweaver.workspace.memory.repository import MemoryRepository

    try:
        async with context.db.async_session_scope() as session:
            repo = MemoryRepository(session)
            task = await _find_or_create(repo, registered_name(context), _title(context))
            for step in _REOPEN.get(TaskStatus(task["status"]), ()):
                await repo.transition_state(uuid.UUID(str(task["id"])), step, _REASON[step])
            return str(task["id"])
    except Exception:
        logger.warning(
            "[run_id=%s] Could not open the run's memory task", run.run_id, exc_info=True
        )
        return None


async def close_task(context: RunContext, run: PipelineRun, task_id: str | None) -> None:
    """Give the task the state the run ended in: DONE, BLOCKED, or left open when parked."""
    end = _END.get(run.status)
    if task_id is None or end is None:
        return
    from specweaver.workspace.memory.repository import MemoryRepository

    try:
        async with context.db.async_session_scope() as session:
            await MemoryRepository(session).transition_state(uuid.UUID(task_id), end, _REASON[end])
    except Exception:
        logger.warning(
            "[run_id=%s] Could not close the run's memory task", run.run_id, exc_info=True
        )


async def _find_or_create(repo: MemoryRepository, project: str, title: str) -> dict[str, object]:
    for task in await repo.list_tasks(project_name=project):
        if task["title"] == title and task["status"] != TaskStatus.ARCHIVED.value:
            return task
    return await repo.create_task(project, title, description=f"Runs of {title}")
