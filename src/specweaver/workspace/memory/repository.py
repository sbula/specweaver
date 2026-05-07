"""Agent Memory Bank — Repository.

Provides core CRUD operations, formal State Transition Matrix enforcement,
defect invariants, and context cleanup for task lifecycle management.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from specweaver.workspace.memory.errors import (
    CyclicDependencyError,
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
    TaskDependency,
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


class MemoryRepository:
    """Repository for the Agent Memory Bank (US-28).

    Provides core CRUD operations, formal State Transition Matrix enforcement,
    defect invariants, and context cleanup for task lifecycle management.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def _ensure_project_exists(self, project_name: str) -> None:
        """Helper to check if project exists, else raise ValueError."""
        stmt = select(Project).where(Project.name == project_name)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Project does not exist: {project_name}")

    async def create_epic(
        self, project_name: str, title: str, description: str | None = None
    ) -> dict[str, object]:
        """Create a new Epic. Validates project exists. Returns dict."""
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
        """Fetch epic by PK. Returns None if not found."""
        epic = await self.session.get(Epic, epic_id)
        if epic is None:
            return None
        return self._epic_to_dict(epic)

    async def list_epics(self, project_name: str) -> list[dict[str, object]]:
        """List all epics for a project, ordered by created_at desc."""
        stmt = (
            select(Epic).where(Epic.project_name == project_name).order_by(Epic.created_at.desc())
        )
        result = await self.session.execute(stmt)
        epics = result.scalars().all()
        return [self._epic_to_dict(e) for e in epics]

    async def close_epic(self, epic_id: uuid.UUID) -> dict[str, object]:
        """Set epic status to CLOSED. Raises ValueError if not found or already CLOSED."""
        epic = await self.session.get(Epic, epic_id)
        if epic is None:
            raise ValueError(f"Epic not found: {epic_id}")

        if epic.status == EpicStatus.CLOSED:
            raise ValueError(f"Epic is already CLOSED: {epic_id}")

        epic.status = EpicStatus.CLOSED
        epic.updated_at = datetime.now(UTC)
        await self.session.flush()
        return self._epic_to_dict(epic)

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

    async def create_task(
        self,
        project_name: str,
        title: str,
        description: str | None = None,
        epic_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        """Create a new Task."""
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
        """Fetch task by PK. Returns None if not found."""
        task = await self.session.get(Task, task_id)
        if task is None:
            return None
        return self._task_to_dict(task)

    async def list_tasks(
        self, project_name: str, *, status: TaskStatus | None = None
    ) -> list[dict[str, object]]:
        """List tasks for a project, optionally filtered by status."""
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
        """Update mutable task fields."""
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

    async def create_defect(
        self, task_id: uuid.UUID, title: str, description: str | None = None
    ) -> dict[str, object]:
        """Create OPEN defect linked to task."""
        task = await self.session.get(Task, task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        defect = self._build_defect(task_id, title, description)
        self.session.add(defect)
        await self.session.flush()

        logger.info("Defect created: task_id=%s, defect_id=%s, title=%s", task_id, defect.id, title)
        return self._defect_to_dict(defect)

    async def resolve_defect(self, defect_id: int) -> dict[str, object]:
        """Set defect status to RESOLVED."""
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
        """List defects for a task."""
        stmt = select(Defect).where(Defect.task_id == task_id)
        if status:
            stmt = stmt.where(Defect.status == status)

        result = await self.session.execute(stmt)
        defects = result.scalars().all()
        return [self._defect_to_dict(d) for d in defects]

    async def acquire_task(self, task_id: uuid.UUID, worker_id: str) -> dict[str, object]:
        """Acquire a PENDING task using Optimistic Concurrency Control (AD-6, AD-14)."""
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

    async def update_handover_context(
        self, task_id: uuid.UUID, context: HandoverContext | None
    ) -> dict[str, object]:
        """Update handover context with strict domain boundary enforcement (NFR-5, NFR-6)."""
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

    async def transition_state(
        self, task_id: uuid.UUID, to_status: TaskStatus, reason: TransitionReason | str
    ) -> dict[str, object]:
        """Transition task state safely (State Machine)."""
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
        """Update last_heartbeat_at for an active task (FR-3, NFR-4).

        Only IN_PROGRESS tasks may pulse heartbeats.
        The caller must provide the worker_id that owns the task (RT-3).
        """
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

    async def recycle_zombies(
        self, project_name: str, timeout_minutes: int = 15, batch_size: int = 100
    ) -> list[dict[str, object]]:
        """Scan for zombie tasks and recycle or circuit-break them (FR-5, FR-8).

        Zombie criteria: status=IN_PROGRESS AND
            (now() - last_heartbeat_at > timeout_minutes OR last_heartbeat_at IS NULL).

        For each zombie:
        - If attempt_count < 3 after increment: reset to PENDING (ZOMBIE_TIMEOUT).
        - If attempt_count >= 3 after increment: auto-BLOCKED + Defect (CIRCUIT_BREAKER).

        Note: timeout_minutes=0 acts as a force-recycle-all operation (RT2-12).

        Returns list of recycled/blocked task dicts. Each dict includes a
        'resilience_action' key: 'RECYCLED' or 'CIRCUIT_BREAKER' (RT2-7).
        """
        # RT-2: Defensive guard — verify our transitions are still legal per the matrix
        assert TaskStatus.PENDING in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS], (
            "State matrix no longer allows IN_PROGRESS → PENDING"
        )
        assert TaskStatus.BLOCKED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS], (
            "State matrix no longer allows IN_PROGRESS → BLOCKED"
        )

        threshold = datetime.now(UTC) - timedelta(minutes=timeout_minutes)

        # RT-7: Include tasks with NULL heartbeat (entered IN_PROGRESS via
        # transition_state instead of acquire_task)
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

        # RT-11: Single timestamp for the entire batch (atomic operation semantics)
        now = datetime.now(UTC)
        # RT2-1: Collect zombie objects, serialize AFTER flush (not before)
        processed_zombies: list[tuple[Task, str]] = []  # (task, action)

        for zombie in zombies:
            # Increment attempt_count first to decide circuit breaker
            zombie.attempt_count += 1
            # RT-3: Increment version to signal state change to cached references
            zombie.version += 1

            if zombie.attempt_count >= 3:
                # Circuit Breaker (FR-8, AD-9): auto-BLOCKED
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

                # RT2-5: Use _build_defect for validation without flushing
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
                # Normal zombie recycling (FR-5): reset to PENDING
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

        # RT-9: Batch flush with error logging
        try:
            await self.session.flush()
        except Exception:
            zombie_ids = [str(z.id) for z, _ in processed_zombies]
            logger.error(
                "recycle_zombies batch flush failed for zombies: %s",
                zombie_ids,
            )
            raise

        # RT2-1: Serialize AFTER flush — return only persisted state
        return [
            {**self._task_to_dict(zombie), "resilience_action": action}
            for zombie, action in processed_zombies
        ]

    async def get_task_transitions(self, task_id: uuid.UUID) -> list[dict[str, object]]:
        """Fetch audit trail for a task."""
        stmt = (
            select(StateTransition)
            .where(StateTransition.task_id == task_id)
            .order_by(StateTransition.timestamp.asc())
        )
        result = await self.session.execute(stmt)
        transitions = result.scalars().all()
        return [self._transition_to_dict(t) for t in transitions]
