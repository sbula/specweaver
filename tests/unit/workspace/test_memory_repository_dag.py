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


class TestMemoryRepositoryDependencies:
    async def test_update_handover_context_pydantic(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-15, U-21: Happy Path: Sets HandoverContext on task."""
        from specweaver.workspace.memory.models import HandoverContext

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        context = HandoverContext(summary="test summary")
        updated = await repo.update_handover_context(
            task_id=uuid.UUID(str(task["id"])), context=context
        )
        assert updated["handover_context"] == context.to_json_str()

    async def test_update_handover_context_none_clears(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-20: Boundary: None clears context."""
        from specweaver.workspace.memory.models import HandoverContext

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.update_handover_context(
            task_id=uuid.UUID(str(task["id"])), context=HandoverContext()
        )

        cleared = await repo.update_handover_context(
            task_id=uuid.UUID(str(task["id"])), context=None
        )
        assert cleared["handover_context"] is None

    async def test_update_handover_context_task_not_found(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Task not found"):
            await repo.update_handover_context(task_id=uuid.uuid4(), context=None)

    async def test_insert_dependency_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-1: Valid edge insertion with cycle check."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")

        await repo.insert_dependency(parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"]))

        from sqlalchemy import select

        from specweaver.workspace.memory.store import TaskDependency

        stmt = select(TaskDependency).where(
            TaskDependency.parent_task_id == uuid.UUID(t1["id"]),
            TaskDependency.child_task_id == uuid.UUID(t2["id"]),
        )
        res = await session.execute(stmt)
        assert res.scalar_one_or_none() is not None

    async def test_insert_dependency_self_reference(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-2: Self-dependency rejected."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")

        with pytest.raises(ValueError, match="Cannot add self-dependency"):
            await repo.insert_dependency(
                parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t1["id"])
            )

    async def test_insert_dependency_duplicate(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-3: Duplicate edge rejected."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")

        await repo.insert_dependency(parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"]))

        with pytest.raises(ValueError, match="Dependency already exists"):
            await repo.insert_dependency(
                parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"])
            )

    async def test_insert_dependency_cycle_direct(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-4: A->B then B->A raises CyclicDependencyError."""
        from specweaver.workspace.memory.errors import CyclicDependencyError

        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")

        await repo.insert_dependency(parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"]))
        with pytest.raises(CyclicDependencyError):
            await repo.insert_dependency(
                parent_id=uuid.UUID(t2["id"]), child_id=uuid.UUID(t1["id"])
            )

    async def test_insert_dependency_cycle_transitive(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-5: A->B->C then C->A raises CyclicDependencyError."""
        from specweaver.workspace.memory.errors import CyclicDependencyError

        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")
        t3 = await repo.create_task(project_name=base_project.name, title="T3")

        await repo.insert_dependency(parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"]))
        await repo.insert_dependency(parent_id=uuid.UUID(t2["id"]), child_id=uuid.UUID(t3["id"]))
        with pytest.raises(CyclicDependencyError):
            await repo.insert_dependency(
                parent_id=uuid.UUID(t3["id"]), child_id=uuid.UUID(t1["id"])
            )

    async def test_insert_dependency_diamond_no_cycle(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-6: A->C, B->C is valid."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")
        t3 = await repo.create_task(project_name=base_project.name, title="T3")

        await repo.insert_dependency(parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t3["id"]))
        await repo.insert_dependency(parent_id=uuid.UUID(t2["id"]), child_id=uuid.UUID(t3["id"]))

    async def test_insert_dependency_nonexistent_parent(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-7: Nonexistent parent raises ValueError."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        with pytest.raises(ValueError, match="Parent task not found"):
            await repo.insert_dependency(parent_id=uuid.uuid4(), child_id=uuid.UUID(t1["id"]))

    async def test_insert_dependency_nonexistent_child(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-8: Nonexistent child raises ValueError."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        with pytest.raises(ValueError, match="Child task not found"):
            await repo.insert_dependency(parent_id=uuid.UUID(t1["id"]), child_id=uuid.uuid4())

    async def test_insert_dependency_long_chain_no_cycle(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-22: 10-node linear chain."""
        repo = MemoryRepository(session)
        tasks = [
            await repo.create_task(project_name=base_project.name, title=f"T{i}") for i in range(10)
        ]
        for i in range(9):
            await repo.insert_dependency(
                parent_id=uuid.UUID(tasks[i]["id"]), child_id=uuid.UUID(tasks[i + 1]["id"])
            )

    async def test_remove_task_dependency(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: Successfully removes TaskDependency link."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")

        await repo.insert_dependency(parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"]))
        await repo.remove_task_dependency(
            parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"])
        )

        from sqlalchemy import select

        from specweaver.workspace.memory.store import TaskDependency

        stmt = select(TaskDependency).where(
            TaskDependency.parent_task_id == uuid.UUID(t1["id"]),
            TaskDependency.child_task_id == uuid.UUID(t2["id"]),
        )
        res = await session.execute(stmt)
        assert res.scalar_one_or_none() is None

    async def test_remove_task_dependency_not_found(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary: Raises ValueError if link not found."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")

        with pytest.raises(ValueError, match="Dependency not found"):
            await repo.remove_task_dependency(
                parent_id=uuid.UUID(t1["id"]), child_id=uuid.UUID(t2["id"])
            )


class TestMemoryRepositoryAcquisition:
    async def test_acquire_task_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-9, U-12, U-14: OCC acquisition increments version, sets worker."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        updated = await repo.acquire_task(task_id=task_id, worker_id="agent-1")
        assert updated["status"] == "IN_PROGRESS"
        assert updated["assigned_worker_id"] == "agent-1"
        assert updated["version"] == 2
        assert updated["locked_at"] is not None
        assert updated["last_heartbeat_at"] is not None

    async def test_acquire_task_not_pending(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-10: Non-PENDING task raises IllegalStateTransitionError."""
        from specweaver.workspace.memory.errors import IllegalStateTransitionError

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        await repo.acquire_task(task_id=task_id, worker_id="agent-1")

        with pytest.raises(IllegalStateTransitionError):
            await repo.acquire_task(task_id=task_id, worker_id="agent-2")

    async def test_acquire_task_not_found(self, session: AsyncSession) -> None:
        """U-11: Nonexistent task raises ValueError."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Task not found"):
            await repo.acquire_task(task_id=uuid.uuid4(), worker_id="agent-1")

    async def test_acquire_task_audit_trail(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-13: StateTransition created with ACQUIRED reason."""
        from specweaver.workspace.memory.store import TransitionReason

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        await repo.acquire_task(task_id=task_id, worker_id="agent-1")

        transitions = await repo.get_task_transitions(task_id)
        assert len(transitions) == 1
        assert transitions[0]["reason"] == TransitionReason.ACQUIRED.value
        assert transitions[0]["to_status"] == "IN_PROGRESS"

    async def test_acquire_task_version_mismatch(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-23: Manually bump version between GET and UPDATE; assert StaleTaskVersionError."""
        from specweaver.workspace.memory.errors import StaleTaskVersionError
        from specweaver.workspace.memory.store import Task

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(str(task["id"]))

        # To simulate a race, we mock session.execute to return 0 rows for the UPDATE
        class MockResult:
            rowcount = 0

        original_execute = repo.session.execute

        async def mock_execute(stmt, *args, **kwargs):
            if "UPDATE memory_tasks" in str(stmt):
                from sqlalchemy import select

                # Before returning 0 rows, let's bump the DB version so refresh gets the new one
                task_model = await original_execute(select(Task).where(Task.id == task_id))
                tm = task_model.scalar_one()
                tm.version = 2
                await session.flush()
                return MockResult()
            return await original_execute(stmt, *args, **kwargs)

        repo.session.execute = mock_execute

        with pytest.raises(StaleTaskVersionError) as exc_info:
            await repo.acquire_task(task_id=task_id, worker_id="agent-1")

        assert exc_info.value.expected_version == 1
        assert exc_info.value.actual_version == 2
