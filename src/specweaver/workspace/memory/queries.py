"""Memory Query Service — CQRS read-side for the Agent Memory Bank."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.workspace.memory.store import Defect, DefectStatus, Task, TaskStatus


class MemoryQueryService:
    """Read-side query service for the Memory Bank.

    Provides optimized, reusable query methods for context enrichment.
    Write operations remain in MemoryRepository (CQRS separation).

    Returns ORM model instances (not dicts) because:
    1. Hydrator needs datetime fields for 24h comparison
    2. Future consumers may traverse relationships
    3. Dict serialization is a presentation concern belonging to the consumer
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_tasks(
        self,
        project_name: str,
        *,
        statuses: list[TaskStatus] | None = None,
        order_by: str = "updated_at",
        limit: int | None = None,
    ) -> Sequence[Task]:
        """Get active tasks for a project.

        Args:
            project_name: The name of the project.
            statuses: List of statuses to include. If None, no status filter is applied.
            order_by: Field to sort by ("updated_at" or "created_at"). Defaults to "updated_at".
            limit: Maximum number of tasks to return.

        Returns:
            List of Task ORM instances matching the criteria.

        Raises:
            ValueError: If an invalid order_by field is provided.
        """
        # Validate order_by to prevent SQL injection
        order_map = {
            "updated_at": Task.updated_at.desc(),
            "created_at": Task.created_at.desc(),
        }

        if order_by not in order_map:
            raise ValueError(f"Invalid order_by field: {order_by}")

        stmt = select(Task).where(Task.project_name == project_name)

        if statuses:
            stmt = stmt.where(Task.status.in_(statuses))

        stmt = stmt.order_by(order_map[order_by])

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.scalars(stmt)
        return result.all()

    async def get_recent_done_tasks(
        self,
        project_name: str,
        *,
        max_age_hours: int = 24,
        limit: int = 10,
    ) -> Sequence[Task]:
        """Get recently DONE tasks that have handover context.

        Args:
            project_name: The name of the project.
            max_age_hours: Maximum age in hours for a DONE task to be considered recent.
            limit: Maximum number of tasks to return.

        Returns:
            List of recent DONE tasks with handover context, ordered by updated_at DESC.
        """
        cutoff_time = datetime.now(UTC) - timedelta(hours=max_age_hours)

        stmt = (
            select(Task)
            .where(Task.project_name == project_name)
            .where(Task.status == TaskStatus.DONE)
            .where(Task.handover_context.is_not(None))
            .where(Task.updated_at >= cutoff_time)
            .order_by(Task.updated_at.desc())
            .limit(limit)
        )

        result = await self.session.scalars(stmt)
        return result.all()

    async def get_open_defects_for_tasks(
        self,
        task_ids: Sequence[uuid.UUID],
    ) -> dict[uuid.UUID, list[Defect]]:
        """Get all OPEN defects for a set of tasks.

        Args:
            task_ids: List of task UUIDs to fetch defects for.

        Returns:
            Dictionary mapping task_id to a list of open Defect instances.
        """
        if not task_ids:
            return {}

        stmt = (
            select(Defect)
            .where(Defect.task_id.in_(task_ids))
            .where(Defect.status == DefectStatus.OPEN)
        )

        result = await self.session.scalars(stmt)
        defects = result.all()

        grouped: dict[uuid.UUID, list[Defect]] = {task_id: [] for task_id in task_ids}
        for defect in defects:
            grouped[defect.task_id].append(defect)

        return grouped
