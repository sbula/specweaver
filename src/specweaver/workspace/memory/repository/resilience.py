"""Agent Memory Bank — Resilience Repository Mixin.

Provides Zombie Reaper, Circuit Breakers, and DAG state propagation.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.workspace.memory.store import (
    ALLOWED_TRANSITIONS,
    Defect,
    StateTransition,
    Task,
    TaskDependency,
    TaskStatus,
    TransitionReason,
)

logger = logging.getLogger(__name__)

CIRCUIT_BREAKER_DEFECT_TITLE = "circuit_breaker: max retries exceeded"


class _CoreMixinProtocol(Protocol):
    session: AsyncSession

    def _task_to_dict(self, task: Task) -> dict[str, object]: ...
    def _build_defect(
        self, task_id: uuid.UUID, title: str, description: str | None = None
    ) -> Defect: ...


class MemoryRepositoryResilienceMixin:
    """Zombie Reaper and DAG state propagation operations."""

    session: AsyncSession

    async def recycle_zombies(
        self: _CoreMixinProtocol,
        project_name: str,
        timeout_minutes: int = 15,
        batch_size: int = 100,
    ) -> list[dict[str, object]]:
        """Scan for zombie tasks and recycle or circuit-break them (FR-5, FR-8)."""
        assert TaskStatus.PENDING in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS], (
            "State matrix no longer allows IN_PROGRESS → PENDING"
        )
        assert TaskStatus.BLOCKED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS], (
            "State matrix no longer allows IN_PROGRESS → BLOCKED"
        )

        threshold = datetime.now(UTC) - timedelta(minutes=timeout_minutes)

        stmt = (
            select(Task)
            .where(
                Task.project_name == project_name,
                Task.status == TaskStatus.IN_PROGRESS,
                or_(
                    Task.last_heartbeat_at < threshold,
                    Task.last_heartbeat_at.is_(None),
                ),
            )
            .limit(batch_size)
        )
        result = await self.session.execute(stmt)
        zombies = result.scalars().all()

        now = datetime.now(UTC)
        processed_zombies: list[tuple[Task, str]] = []

        for zombie in zombies:
            zombie.attempt_count += 1
            zombie.version += 1

            if zombie.attempt_count >= 3:
                zombie.status = TaskStatus.BLOCKED
                zombie.assigned_worker_id = None
                zombie.locked_at = None
                zombie.last_heartbeat_at = None
                zombie.updated_at = now

                transition = StateTransition(
                    task_id=zombie.id,
                    from_status=TaskStatus.IN_PROGRESS,
                    to_status=TaskStatus.BLOCKED,
                    reason=TransitionReason.CIRCUIT_BREAKER,
                    timestamp=now,
                )
                self.session.add(transition)

                defect = self._build_defect(
                    task_id=zombie.id,
                    title=CIRCUIT_BREAKER_DEFECT_TITLE,
                    description=(
                        f"Task {zombie.id} has failed {zombie.attempt_count} times. "
                        "Automatic circuit breaker activated."
                    ),
                )
                self.session.add(defect)

                logger.error(
                    "Circuit breaker activated: task_id=%s, attempt_count=%s, project=%s",
                    zombie.id,
                    zombie.attempt_count,
                    project_name,
                )
                processed_zombies.append((zombie, "CIRCUIT_BREAKER"))
            else:
                zombie.status = TaskStatus.PENDING
                zombie.assigned_worker_id = None
                zombie.locked_at = None
                zombie.last_heartbeat_at = None
                zombie.updated_at = now

                transition = StateTransition(
                    task_id=zombie.id,
                    from_status=TaskStatus.IN_PROGRESS,
                    to_status=TaskStatus.PENDING,
                    reason=TransitionReason.ZOMBIE_TIMEOUT,
                    timestamp=now,
                )
                self.session.add(transition)

                logger.info(
                    "Zombie recycled: task_id=%s, attempt_count=%s, project=%s",
                    zombie.id,
                    zombie.attempt_count,
                    project_name,
                )
                processed_zombies.append((zombie, "RECYCLED"))

        try:
            await self.session.flush()
        except Exception:
            zombie_ids = [str(z.id) for z, _ in processed_zombies]
            logger.error("recycle_zombies batch flush failed for zombies: %s", zombie_ids)
            raise

        return [
            {**self._task_to_dict(zombie), "resilience_action": action}
            for zombie, action in processed_zombies
        ]

    async def _process_blocked_parent(
        self: _CoreMixinProtocol,
        parent_id: uuid.UUID,
        child_id: uuid.UUID,
        now: datetime,
        visited: set[uuid.UUID],
        queue: list[uuid.UUID],
        affected: list[dict[str, object]],
    ) -> None:
        """Helper to process a single parent during propagate_blocked (reduces cyclomatic complexity)."""
        if parent_id in visited:
            return

        parent = await self.session.get(Task, parent_id)
        if parent is None:
            return

        if parent.status != TaskStatus.PENDING:
            if parent.status == TaskStatus.IN_PROGRESS:
                logger.warning(
                    "Skipping propagation: parent task %s is IN_PROGRESS, "
                    "cannot transition to UPSTREAM_BLOCKED per state matrix",
                    parent_id,
                )
            return

        parent.status = TaskStatus.UPSTREAM_BLOCKED
        parent.updated_at = now
        parent.version += 1

        transition = StateTransition(
            task_id=parent_id,
            from_status=TaskStatus.PENDING,
            to_status=TaskStatus.UPSTREAM_BLOCKED,
            reason=TransitionReason.UPSTREAM_BLOCKED,
            timestamp=now,
        )
        self.session.add(transition)

        logger.info("Upstream propagation: parent=%s blocked by child=%s", parent_id, child_id)
        affected.append(self._task_to_dict(parent))

        queue.append(parent_id)

    async def propagate_blocked(
        self: _CoreMixinProtocol, task_id: uuid.UUID
    ) -> list[dict[str, object]]:
        """Cascade UPSTREAM_BLOCKED to all transitive upstream ancestors (FR-9, AD-11)."""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if task.status != TaskStatus.BLOCKED:
            raise ValueError(
                f"Cannot propagate from task {task_id}: "
                f"status is {task.status.value}, expected BLOCKED"
            )

        affected: list[dict[str, object]] = []
        now = datetime.now(UTC)

        queue: list[uuid.UUID] = [task_id]
        visited: set[uuid.UUID] = set()

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            stmt = select(TaskDependency.parent_task_id).where(
                TaskDependency.child_task_id == current_id
            )
            result = await self.session.execute(stmt)
            parent_ids = [row[0] for row in result.fetchall()]

            for parent_id in parent_ids:
                await self._process_blocked_parent(  # type: ignore[attr-defined]
                    parent_id, task_id, now, visited, queue, affected
                )

        await self.session.flush()
        return affected

    async def _process_unblocked_parent(
        self: _CoreMixinProtocol,
        parent_id: uuid.UUID,
        child_id: uuid.UUID,
        now: datetime,
        visited: set[uuid.UUID],
        queue: list[uuid.UUID],
        cleared: list[dict[str, object]],
    ) -> None:
        """Helper to process a single parent during clear_upstream_blocked."""
        if parent_id in visited:
            return

        parent = await self.session.get(Task, parent_id)
        if parent is None or parent.status != TaskStatus.UPSTREAM_BLOCKED:
            return

        blocker_stmt = (
            select(Task.id)
            .join(TaskDependency, TaskDependency.child_task_id == Task.id)
            .where(
                TaskDependency.parent_task_id == parent_id,
                Task.status.in_([TaskStatus.BLOCKED, TaskStatus.UPSTREAM_BLOCKED]),
            )
            .limit(1)
        )
        blocker_result = await self.session.execute(blocker_stmt)
        if blocker_result.scalar_one_or_none() is not None:
            logger.debug("Parent %s still has blocked children, skipping clear", parent_id)
            return

        parent.status = TaskStatus.PENDING
        parent.updated_at = now
        parent.version += 1

        transition = StateTransition(
            task_id=parent_id,
            from_status=TaskStatus.UPSTREAM_BLOCKED,
            to_status=TaskStatus.PENDING,
            reason=TransitionReason.UPSTREAM_CLEARED,
            timestamp=now,
        )
        self.session.add(transition)

        logger.info(
            "Reverse propagation: parent=%s cleared (child=%s unblocked)",
            parent_id,
            child_id,
        )
        cleared.append(self._task_to_dict(parent))

        queue.append(parent_id)

    async def clear_upstream_blocked(
        self: _CoreMixinProtocol, task_id: uuid.UUID
    ) -> list[dict[str, object]]:
        """Reverse-propagate: clear UPSTREAM_BLOCKED on ancestors when blocker resolves (FR-9)."""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if task.status in (TaskStatus.BLOCKED, TaskStatus.UPSTREAM_BLOCKED):
            logger.warning(
                "clear_upstream_blocked called but task %s is still %s",
                task_id,
                task.status.value,
            )
            return []

        cleared: list[dict[str, object]] = []
        now = datetime.now(UTC)

        queue: list[uuid.UUID] = [task_id]
        visited: set[uuid.UUID] = set()

        while queue:
            current_id = queue.pop(0)
            if current_id in visited:
                continue
            visited.add(current_id)

            stmt = select(TaskDependency.parent_task_id).where(
                TaskDependency.child_task_id == current_id
            )
            result = await self.session.execute(stmt)
            parent_ids = [row[0] for row in result.fetchall()]

            for parent_id in parent_ids:
                await self._process_unblocked_parent(  # type: ignore[attr-defined]
                    parent_id, task_id, now, visited, queue, cleared
                )

        await self.session.flush()
        return cleared
