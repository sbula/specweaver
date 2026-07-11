# mypy: ignore-errors
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener

# We will import MemoryRepository once it's created, but for now this will cause an ImportError
# which is expected for the RED phase.
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.store import Base, Project


@pytest_asyncio.fixture
async def engine():
    """Create an in-memory SQLite database with schema and FK constraints."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    register_fk_pragma_listener(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Provide a transactional scoped session."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def base_project(session: AsyncSession) -> Project:
    """Create a foundational Project row for FK references."""
    now = datetime.now(UTC)
    project = Project(
        name="test_proj",
        root_path="/tmp/test",
        created_at=now,
        last_used_at=now,
    )
    session.add(project)
    await session.flush()
    await session.refresh(project)
    return project


@pytest.mark.asyncio
class TestMemoryRepositoryResilience:
    async def test_pulse_heartbeat_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-1: Pulses IN_PROGRESS task; last_heartbeat_at updated"""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        # Manually set assigned_worker_id and a past heartbeat
        from specweaver.workspace.memory.store import Task

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.assigned_worker_id = "agent-1"
        old_time = datetime(2020, 1, 1, tzinfo=UTC)
        task_model.last_heartbeat_at = old_time
        await session.flush()

        updated = await repo.pulse_heartbeat(
            task_id=uuid.UUID(str(task["id"])), worker_id="agent-1"
        )
        assert updated["last_heartbeat_at"] > old_time.isoformat()

    async def test_pulse_heartbeat_not_in_progress(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-2: Raises ValueError for PENDING task"""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        with pytest.raises(ValueError, match="status is PENDING, expected IN_PROGRESS"):
            await repo.pulse_heartbeat(task_id=uuid.UUID(str(task["id"])), worker_id="agent-1")

    async def test_pulse_heartbeat_not_found(self, session: AsyncSession) -> None:
        """U-3: Raises ValueError for unknown UUID"""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Task not found"):
            await repo.pulse_heartbeat(task_id=uuid.uuid4(), worker_id="agent-1")

    async def test_pulse_heartbeat_wrong_worker(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-26 / RT-3: Calling with wrong worker_id raises ValueError"""
        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.assigned_worker_id = "agent-1"
        await session.flush()

        with pytest.raises(ValueError, match="does not own task"):
            await repo.pulse_heartbeat(task_id=uuid.UUID(str(task["id"])), worker_id="agent-2")

    async def test_recycle_zombies_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-4: 1 zombie task recycled to PENDING, attempt_count = 1"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 1
        assert recycled[0]["status"] == "PENDING"
        assert recycled[0]["attempt_count"] == 1
        assert recycled[0]["resilience_action"] == "RECYCLED"

    async def test_recycle_zombies_no_zombies(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-5: Fresh tasks are not recycled"""
        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 0

    async def test_recycle_zombies_circuit_breaker(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-6: Task with attempt_count=2 becomes BLOCKED with defect"""
        from datetime import timedelta

        from sqlalchemy import select

        from specweaver.workspace.memory.store import Defect, Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        task_model.attempt_count = 2
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 1
        assert recycled[0]["status"] == "BLOCKED"
        assert recycled[0]["attempt_count"] == 3
        assert recycled[0]["resilience_action"] == "CIRCUIT_BREAKER"

        # Check defect
        stmt = select(Defect).where(Defect.task_id == uuid.UUID(str(task["id"])))
        res = await session.execute(stmt)
        defect = res.scalar_one()
        assert defect.title == "circuit_breaker: max retries exceeded"

    async def test_recycle_zombies_clears_worker_fields(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-7: assigned_worker_id, locked_at, last_heartbeat_at cleared"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        task_model.assigned_worker_id = "agent-1"
        task_model.locked_at = datetime.now(UTC)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert recycled[0]["assigned_worker_id"] is None
        assert recycled[0]["locked_at"] is None
        assert recycled[0]["last_heartbeat_at"] is None

    async def test_recycle_zombies_creates_audit_trail(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-8: StateTransition with ZOMBIE_TIMEOUT"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus, TransitionReason

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        await repo.recycle_zombies(project_name=base_project.name)
        transitions = await repo.get_task_transitions(uuid.UUID(str(task["id"])))
        assert transitions[-1]["reason"] == TransitionReason.ZOMBIE_TIMEOUT.value

    async def test_recycle_zombies_circuit_breaker_audit_trail(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-9: StateTransition with CIRCUIT_BREAKER"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus, TransitionReason

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        task_model.attempt_count = 2
        await session.flush()

        await repo.recycle_zombies(project_name=base_project.name)
        transitions = await repo.get_task_transitions(uuid.UUID(str(task["id"])))
        assert transitions[-1]["reason"] == TransitionReason.CIRCUIT_BREAKER.value

    async def test_recycle_zombies_batch(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-10: 3 zombies recycled in a single call"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)

        for i in range(3):
            t = await repo.create_task(project_name=base_project.name, title=f"T{i}")
            await repo.transition_state(
                task_id=uuid.UUID(str(t["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
            )
            task_model = await session.get(Task, uuid.UUID(str(t["id"])))
            assert task_model is not None
            task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 3

    async def test_recycle_zombies_custom_timeout(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-11: timeout_minutes=5 uses different threshold"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=10)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name, timeout_minutes=5)
        assert len(recycled) == 1

    async def test_recycle_zombies_structured_logging(
        self, session: AsyncSession, base_project: Project, caplog
    ) -> None:
        """U-22: logger.info emitted for zombie recycling"""
        import logging
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        caplog.set_level(logging.INFO)
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        await repo.recycle_zombies(project_name=base_project.name)
        assert any("Zombie recycled" in record.message for record in caplog.records)

    async def test_circuit_breaker_structured_logging(
        self, session: AsyncSession, base_project: Project, caplog
    ) -> None:
        """U-23: logger.error emitted for circuit breaker"""
        import logging
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        caplog.set_level(logging.ERROR)
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        task_model.attempt_count = 2
        await session.flush()

        await repo.recycle_zombies(project_name=base_project.name)
        assert any("Circuit breaker activated" in record.message for record in caplog.records)

    async def test_recycle_zombies_matrix_assertions(self, session: AsyncSession) -> None:
        """U-25 / RT-2: Verify ALLOWED_TRANSITIONS includes IN_PROGRESS to PENDING and BLOCKED"""
        from specweaver.workspace.memory.store import ALLOWED_TRANSITIONS, TaskStatus

        assert TaskStatus.PENDING in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS]
        assert TaskStatus.BLOCKED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS]

    async def test_recycle_zombies_null_heartbeat(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-27 / RT-7: Task with NULL heartbeat is detected as zombie"""
        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = None
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 1

    async def test_recycle_zombies_mixed_batch(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-28 / RT-12: Batch with 2 recyclable + 1 circuit-broken task"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)

        for i in range(3):
            t = await repo.create_task(project_name=base_project.name, title=f"T{i}")
            await repo.transition_state(
                task_id=uuid.UUID(str(t["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
            )
            task_model = await session.get(Task, uuid.UUID(str(t["id"])))
            assert task_model is not None
            task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
            if i == 2:
                task_model.attempt_count = 2
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert len(recycled) == 3
        actions = [r["resilience_action"] for r in recycled]
        assert actions.count("RECYCLED") == 2
        assert actions.count("CIRCUIT_BREAKER") == 1

    async def test_recycle_zombies_resilience_action_key(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-31 / RT2-7: Returned dicts contain resilience_action"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name)
        assert "resilience_action" in recycled[0]

    async def test_recycle_zombies_nonexistent_project(self, session: AsyncSession) -> None:
        """U-32 / RT2-10: returns empty list, no error"""
        repo = MemoryRepository(session)
        recycled = await repo.recycle_zombies(project_name="nonexistent")
        assert len(recycled) == 0

    async def test_recycle_zombies_zero_timeout(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-34 / RT2-12: timeout=0 recycles all IN_PROGRESS"""
        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(str(task["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        task_model = await session.get(Task, uuid.UUID(str(task["id"])))
        assert task_model is not None
        task_model.last_heartbeat_at = datetime.now(UTC)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name, timeout_minutes=0)
        assert len(recycled) == 1

    async def test_recycle_zombies_batch_limit(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-35 / RT3-2: batch_size=2 only processes 2 out of 3"""
        from datetime import timedelta

        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        for i in range(3):
            t = await repo.create_task(project_name=base_project.name, title=f"T{i}")
            await repo.transition_state(
                task_id=uuid.UUID(str(t["id"])), to_status=TaskStatus.IN_PROGRESS, reason="start"
            )
            task_model = await session.get(Task, uuid.UUID(str(t["id"])))
            assert task_model is not None
            task_model.last_heartbeat_at = datetime.now(UTC) - timedelta(minutes=20)
        await session.flush()

        recycled = await repo.recycle_zombies(project_name=base_project.name, batch_size=2)
        assert len(recycled) == 2
