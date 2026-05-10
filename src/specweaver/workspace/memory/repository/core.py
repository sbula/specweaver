"""Agent Memory Bank — Core Repository Mixin.

Provides base entity translation and core CRUD operations.
"""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.workspace.memory.errors import (
    DefectBlocksCompletionError,
    IllegalStateTransitionError,
    StaleTaskVersionError,
)
from specweaver.workspace.memory.models import HandoverContext
from specweaver.workspace.memory.store import (
    ALLOWED_TRANSITIONS,
    Defect,
    DefectStatus,
    Epic,
    EpicStatus,
    StateTransition,
    Task,
    TaskStatus,
    TransitionReason,
)
from specweaver.workspace.store import Project

logger = logging.getLogger(__name__)

CIRCUIT_BREAKER_DEFECT_TITLE = "circuit_breaker: max retries exceeded"


def _validate_non_empty(field_name: str, value: str) -> None:
    """Raise ValueError if value is empty or whitespace-only."""
    if not value or not value.strip():
        raise ValueError(f"{field_name} cannot be empty or whitespace-only")


class MemoryRepositoryCoreMixin:
    """Core CRUD operations and State Machine enforcement."""

    session: AsyncSession

    @staticmethod
    def _epic_to_dict(epic: Epic) -> dict[str, object]:
        return {
            "id": str(epic.id),
            "project_name": epic.project_name,
            "title": epic.title,
            "description": epic.description,
            "status": epic.status.value,
            "created_at": epic.created_at.isoformat()
            if isinstance(epic.created_at, datetime)
            else epic.created_at,
            "updated_at": epic.updated_at.isoformat()
            if isinstance(epic.updated_at, datetime)
            else epic.updated_at,
        }

    @staticmethod
    def _task_to_dict(task: Task) -> dict[str, object]:
        return {
            "id": str(task.id),
            "project_name": task.project_name,
            "epic_id": str(task.epic_id) if task.epic_id else None,
            "title": task.title,
            "description": task.description,
            "status": task.status.value,
            "assigned_worker_id": task.assigned_worker_id,
            "locked_at": task.locked_at.isoformat() if task.locked_at else None,
            "last_heartbeat_at": task.last_heartbeat_at.isoformat()
            if task.last_heartbeat_at
            else None,
            "handover_context": task.handover_context,
            "version": task.version,
            "attempt_count": task.attempt_count,
            "created_at": task.created_at.isoformat()
            if isinstance(task.created_at, datetime)
            else task.created_at,
            "updated_at": task.updated_at.isoformat()
            if isinstance(task.updated_at, datetime)
            else task.updated_at,
        }

    @staticmethod
    def _defect_to_dict(defect: Defect) -> dict[str, object]:
        return {
            "id": defect.id,
            "task_id": str(defect.task_id),
            "title": defect.title,
            "description": defect.description,
            "status": defect.status.value,
            "created_at": defect.created_at.isoformat()
            if isinstance(defect.created_at, datetime)
            else defect.created_at,
            "resolved_at": defect.resolved_at.isoformat()
            if isinstance(defect.resolved_at, datetime) and defect.resolved_at
            else defect.resolved_at,
        }

    @staticmethod
    def _transition_to_dict(transition: StateTransition) -> dict[str, object]:
        return {
            "id": transition.id,
            "task_id": str(transition.task_id),
            "from_status": transition.from_status.value,
            "to_status": transition.to_status.value,
            "reason": transition.reason.value
            if isinstance(transition.reason, TransitionReason)
            else transition.reason,
            "timestamp": transition.timestamp.isoformat()
            if isinstance(transition.timestamp, datetime)
            else transition.timestamp,
        }

    def _build_defect(
        self, task_id: uuid.UUID, title: str, description: str | None = None
    ) -> Defect:
        """Build a validated Defect instance without flushing (RT2-5)."""
        _validate_non_empty("title", title)
        now = datetime.now(UTC)
        return Defect(
            task_id=task_id,
            title=title,
            description=description,
            status=DefectStatus.OPEN,
            created_at=now,
        )

    async def _ensure_project_exists(self, project_name: str) -> None:
        stmt = select(Project).where(Project.name == project_name)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Project does not exist: {project_name}")

    async def create_epic(
        self, project_name: str, title: str, description: str | None = None
    ) -> dict[str, object]:
        _validate_non_empty("title", title)
        await self._ensure_project_exists(project_name)

        now = datetime.now(UTC)
        epic = Epic(
            project_name=project_name,
            title=title,
            description=description,
            status=EpicStatus.OPEN,
            created_at=now,
            updated_at=now,
        )
        self.session.add(epic)
        await self.session.flush()
        return self._epic_to_dict(epic)

    async def get_epic(self, epic_id: uuid.UUID) -> dict[str, object] | None:
        epic = await self.session.get(Epic, epic_id)
        if epic is None:
            return None
        return self._epic_to_dict(epic)

    async def list_epics(self, project_name: str) -> list[dict[str, object]]:
        stmt = (
            select(Epic).where(Epic.project_name == project_name).order_by(Epic.created_at.desc())
        )
        result = await self.session.execute(stmt)
        epics = result.scalars().all()
        return [self._epic_to_dict(e) for e in epics]

    async def close_epic(self, epic_id: uuid.UUID) -> dict[str, object]:
        epic = await self.session.get(Epic, epic_id)
        if epic is None:
            raise ValueError(f"Epic not found: {epic_id}")

        if epic.status == EpicStatus.CLOSED:
            raise ValueError(f"Epic is already CLOSED: {epic_id}")

        epic.status = EpicStatus.CLOSED
        epic.updated_at = datetime.now(UTC)
        await self.session.flush()
        return self._epic_to_dict(epic)

    async def create_task(
        self,
        project_name: str,
        title: str,
        description: str | None = None,
        epic_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        _validate_non_empty("title", title)
        await self._ensure_project_exists(project_name)

        if epic_id:
            epic = await self.session.get(Epic, epic_id)
            if epic is None:
                raise ValueError(f"Epic not found: {epic_id}")
            if epic.project_name != project_name:
                raise ValueError("Epic belongs to a different project")

        now = datetime.now(UTC)
        task = Task(
            project_name=project_name,
            epic_id=epic_id,
            title=title,
            description=description,
            status=TaskStatus.PENDING,
            version=1,
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )
        self.session.add(task)
        await self.session.flush()
        return self._task_to_dict(task)

    async def get_task(self, task_id: uuid.UUID) -> dict[str, object] | None:
        task = await self.session.get(Task, task_id)
        if task is None:
            return None
        return self._task_to_dict(task)

    async def list_tasks(
        self, project_name: str, *, status: TaskStatus | None = None
    ) -> list[dict[str, object]]:
        stmt = select(Task).where(Task.project_name == project_name)
        if status:
            stmt = stmt.where(Task.status == status)
        stmt = stmt.order_by(Task.created_at.desc())

        result = await self.session.execute(stmt)
        tasks = result.scalars().all()
        return [self._task_to_dict(t) for t in tasks]

    async def update_task(
        self, task_id: uuid.UUID, *, title: str | None = None, description: str | None = None
    ) -> dict[str, object]:
        if title is not None:
            _validate_non_empty("title", title)

        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if title is not None:
            task.title = title
        if description is not None:
            task.description = description

        task.updated_at = datetime.now(UTC)
        await self.session.flush()
        return self._task_to_dict(task)

    async def create_defect(
        self, task_id: uuid.UUID, title: str, description: str | None = None
    ) -> dict[str, object]:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        defect = self._build_defect(task_id, title, description)
        self.session.add(defect)
        await self.session.flush()

        logger.info("Defect created: task_id=%s, defect_id=%s, title=%s", task_id, defect.id, title)
        return self._defect_to_dict(defect)

    async def resolve_defect(self, defect_id: int) -> dict[str, object]:
        defect = await self.session.get(Defect, defect_id)
        if defect is None:
            raise ValueError(f"Defect not found: {defect_id}")

        if defect.status == DefectStatus.RESOLVED:
            raise ValueError(f"Defect is already RESOLVED: {defect_id}")

        defect.status = DefectStatus.RESOLVED
        defect.resolved_at = datetime.now(UTC)
        await self.session.flush()

        logger.info("Defect resolved: defect_id=%s, task_id=%s", defect.id, defect.task_id)
        return self._defect_to_dict(defect)

    async def list_defects(
        self, task_id: uuid.UUID, *, status: DefectStatus | None = None
    ) -> list[dict[str, object]]:
        stmt = select(Defect).where(Defect.task_id == task_id)
        if status:
            stmt = stmt.where(Defect.status == status)

        result = await self.session.execute(stmt)
        defects = result.scalars().all()
        return [self._defect_to_dict(d) for d in defects]

    async def update_handover_context(
        self, task_id: uuid.UUID, context: HandoverContext | None
    ) -> dict[str, object]:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if context is None:
            task.handover_context = None
        else:
            task.handover_context = context.to_json_str()

        task.updated_at = datetime.now(UTC)
        await self.session.flush()

        logger.debug(
            "Handover context updated: task_id=%s, size=%s bytes",
            task_id,
            len(task.handover_context.encode("utf-8")) if task.handover_context else 0,
        )
        return self._task_to_dict(task)

    async def transition_state(
        self, task_id: uuid.UUID, to_status: TaskStatus, reason: TransitionReason | str
    ) -> dict[str, object]:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        from_status = task.status
        if from_status == to_status:
            return self._task_to_dict(task)  # No-op

        # 1. Enforce allowed transitions (AD-15)
        allowed = ALLOWED_TRANSITIONS.get(from_status, set())
        if to_status not in allowed:
            logger.error(
                "Illegal state transition for task %s: %s -> %s", task_id, from_status, to_status
            )
            raise IllegalStateTransitionError(task_id, from_status, to_status)

        # 2. Defect Invariant (AD-8): PENDING -> DONE or IN_PROGRESS -> DONE requires 0 OPEN defects
        if to_status == TaskStatus.DONE:
            stmt = select(Defect).where(
                Defect.task_id == task_id, Defect.status == DefectStatus.OPEN
            )
            res = await self.session.execute(stmt)
            open_defects = res.scalars().all()
            if open_defects:
                raise DefectBlocksCompletionError(task_id, len(open_defects))

        # 3. State Context Mutators
        if to_status == TaskStatus.BLOCKED:
            task.attempt_count += 1
            task.locked_at = None
            task.last_heartbeat_at = None
        elif to_status == TaskStatus.ARCHIVED:
            task.handover_context = None

        # 4. Perform Transition
        task.status = to_status
        task.updated_at = datetime.now(UTC)

        # 5. Audit Trail
        transition_reason = (
            reason if isinstance(reason, TransitionReason) else TransitionReason.MANUAL_UNBLOCK
        )
        transition = StateTransition(
            task_id=task_id,
            from_status=from_status,
            to_status=to_status,
            reason=transition_reason,
            timestamp=task.updated_at,
        )
        self.session.add(transition)
        await self.session.flush()

        if to_status in (TaskStatus.BLOCKED, TaskStatus.UPSTREAM_BLOCKED):
            logger.warning(
                "Task transition: task_id=%s, %s → %s, reason=%s",
                task_id,
                from_status.value,
                to_status.value,
                transition_reason.value,
            )
        else:
            logger.info(
                "Task transition: task_id=%s, %s → %s, reason=%s",
                task_id,
                from_status.value,
                to_status.value,
                transition_reason.value,
            )
        return self._task_to_dict(task)

    async def pulse_heartbeat(self, task_id: uuid.UUID, worker_id: str) -> dict[str, object]:
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if task.status != TaskStatus.IN_PROGRESS:
            raise ValueError(
                f"Cannot pulse heartbeat for task {task_id}: "
                f"status is {task.status.value}, expected IN_PROGRESS"
            )

        if task.assigned_worker_id != worker_id:
            raise ValueError(
                f"Worker {worker_id} does not own task {task_id}: "
                f"assigned to {task.assigned_worker_id}"
            )

        task.last_heartbeat_at = datetime.now(UTC)
        task.updated_at = task.last_heartbeat_at
        await self.session.flush()

        logger.debug(
            "Heartbeat pulse: task_id=%s, worker_id=%s",
            task_id,
            worker_id,
        )
        return self._task_to_dict(task)

    async def get_task_transitions(self, task_id: uuid.UUID) -> list[dict[str, object]]:
        stmt = (
            select(StateTransition)
            .where(StateTransition.task_id == task_id)
            .order_by(StateTransition.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        transitions = result.scalars().all()
        return [self._transition_to_dict(t) for t in transitions]

    async def acquire_task(self, task_id: uuid.UUID, worker_id: str) -> dict[str, object]:
        from sqlalchemy import update

        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if task.status != TaskStatus.PENDING:
            raise IllegalStateTransitionError(task_id, task.status, TaskStatus.IN_PROGRESS)

        expected_version = task.version
        now = datetime.now(UTC)

        stmt = (
            update(Task)
            .where(Task.id == task_id, Task.version == expected_version)
            .values(
                status=TaskStatus.IN_PROGRESS,
                assigned_worker_id=worker_id,
                locked_at=now,
                last_heartbeat_at=now,
                version=expected_version + 1,
                updated_at=now,
            )
        )
        result = await self.session.execute(stmt)
        if isinstance(result, CursorResult) and result.rowcount == 1:
            transition = StateTransition(
                task_id=task_id,
                from_status=TaskStatus.PENDING,
                to_status=TaskStatus.IN_PROGRESS,
                reason=TransitionReason.ACQUIRED,
                worker_id=worker_id,
                timestamp=now,
            )
            self.session.add(transition)
            await self.session.flush()
            await self.session.refresh(task)

            logger.info(
                "Task acquired: task_id=%s, worker_id=%s, version=%s",
                task_id,
                worker_id,
                expected_version + 1,
            )
            return self._task_to_dict(task)

        await self.session.refresh(task)
        logger.warning(
            "OCC collision: task_id=%s, expected_version=%s, actual_version=%s",
            task_id,
            expected_version,
            task.version,
        )
        raise StaleTaskVersionError(task_id, expected_version, task.version)
