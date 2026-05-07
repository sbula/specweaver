"""Agent Memory Bank — DAG Repository Mixin.

Provides graph manipulation logic (dependency insertion/removal) with cycle protection.
"""

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.workspace.memory.errors import CyclicDependencyError
from specweaver.workspace.memory.store import Task, TaskDependency

logger = logging.getLogger(__name__)


class MemoryRepositoryDAGMixin:
    """DAG operations and recursive dependency protection."""

    session: AsyncSession

    async def insert_dependency(self, parent_id: uuid.UUID, child_id: uuid.UUID) -> None:
        """Add a task dependency with WITH RECURSIVE cycle detection (AD-7)."""
        if parent_id == child_id:
            raise ValueError("Cannot add self-dependency")

        parent_task = await self.session.get(Task, parent_id)
        if parent_task is None:
            raise ValueError(f"Parent task not found: {parent_id}")
        child_task = await self.session.get(Task, child_id)
        if child_task is None:
            raise ValueError(f"Child task not found: {child_id}")

        cycle_check = text("""
            WITH RECURSIVE ancestors(task_id) AS (
                SELECT :parent_id AS task_id
                UNION ALL
                SELECT d.parent_task_id
                FROM memory_task_dependencies d
                JOIN ancestors a ON d.child_task_id = a.task_id
            )
            SELECT 1 FROM ancestors WHERE task_id = :child_id LIMIT 1
        """)
        try:
            result = await self.session.execute(
                cycle_check, {"parent_id": parent_id.hex, "child_id": child_id.hex}
            )
            if result.fetchone() is not None:
                raise CyclicDependencyError(parent_id, child_id)
        except OperationalError as e:
            if "recursion depth" in str(e).lower():
                raise ValueError(f"DAG depth limit exceeded while checking cycle: {e}") from e
            raise

        dep = TaskDependency(parent_task_id=parent_id, child_task_id=child_id)
        self.session.add(dep)
        try:
            await self.session.flush()
        except IntegrityError:
            raise ValueError("Dependency already exists") from None

        logger.info("Dependency inserted: parent=%s → child=%s", parent_id, child_id)

    async def remove_task_dependency(self, parent_id: uuid.UUID, child_id: uuid.UUID) -> None:
        """Remove a task dependency."""
        stmt = select(TaskDependency).where(
            TaskDependency.parent_task_id == parent_id, TaskDependency.child_task_id == child_id
        )
        res = await self.session.execute(stmt)
        dep = res.scalar_one_or_none()

        if dep is None:
            raise ValueError("Dependency not found")

        await self.session.delete(dep)
        await self.session.flush()
