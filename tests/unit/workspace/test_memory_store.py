import uuid
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener
from specweaver.workspace.memory.store import (
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
from specweaver.workspace.store import Base, Project


@pytest.fixture
async def engine():
    """Create an in-memory SQLite database with schema and FK constraints."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    register_fk_pragma_listener(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    """Provide a transactional scoped session."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest.fixture
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
    await session.commit()
    await session.refresh(project)
    return project


@pytest.mark.asyncio
class TestMemoryStore:
    async def test_create_task_happy_path(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: Create task with all defaults and verify state."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(
            project_name=project_name,
            title="Test Task",
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)

        assert isinstance(task.id, uuid.UUID)
        assert task.status == TaskStatus.PENDING
        assert task.version == 1
        assert task.attempt_count == 0

    async def test_create_epic_happy_path(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: Create epic with defaults."""
        now = datetime.now(UTC)
        project_name = base_project.name
        epic = Epic(
            project_name=project_name,
            title="Test Epic",
            created_at=now,
            updated_at=now,
        )
        session.add(epic)
        await session.commit()
        await session.refresh(epic)

        assert isinstance(epic.id, uuid.UUID)
        assert epic.status == EpicStatus.OPEN

    async def test_task_fk_to_project(self, session: AsyncSession) -> None:
        """Boundary: Task creation fails if project_name does not exist."""
        now = datetime.now(UTC)
        task = Task(
            project_name="nonexistent_project",
            title="Test Task",
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
            await session.commit()

    async def test_task_fk_to_epic(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: Task can be linked to an Epic."""
        now = datetime.now(UTC)
        project_name = base_project.name
        epic = Epic(
            project_name=project_name,
            title="Test Epic",
            created_at=now,
            updated_at=now,
        )
        session.add(epic)
        await session.commit()

        task = Task(
            project_name=project_name,
            epic_id=epic.id,
            title="Test Task",
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        assert task.epic_id == epic.id

    async def test_task_dependency_composite_pk(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: Can create a DAG edge between two tasks."""
        now = datetime.now(UTC)
        project_name = base_project.name
        t1 = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        t2 = Task(project_name=project_name, title="T2", created_at=now, updated_at=now)
        session.add_all([t1, t2])
        await session.commit()

        dep = TaskDependency(parent_task_id=t1.id, child_task_id=t2.id)
        session.add(dep)
        await session.commit()
        await session.refresh(dep)
        assert dep.parent_task_id == t1.id

    async def test_task_dependency_prevents_duplicate(self, session: AsyncSession, base_project: Project) -> None:
        """Boundary: Duplicate dependency edges raise IntegrityError."""
        now = datetime.now(UTC)
        project_name = base_project.name
        t1 = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        t2 = Task(project_name=project_name, title="T2", created_at=now, updated_at=now)
        session.add_all([t1, t2])
        await session.commit()

        dep1 = TaskDependency(parent_task_id=t1.id, child_task_id=t2.id)
        dep2 = TaskDependency(parent_task_id=t1.id, child_task_id=t2.id)
        session.add_all([dep1, dep2])
        with pytest.raises(IntegrityError, match="UNIQUE constraint failed"):
            await session.commit()

    async def test_state_transition_audit_trail(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: Create state transition audit record."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        session.add(task)
        await session.commit()

        st = StateTransition(
            task_id=task.id,
            from_status=TaskStatus.PENDING,
            to_status=TaskStatus.IN_PROGRESS,
            reason=TransitionReason.ACQUIRED,
            timestamp=now,
        )
        session.add(st)
        await session.commit()
        await session.refresh(st)
        assert st.id is not None
        assert st.reason == TransitionReason.ACQUIRED

    async def test_defect_creation(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: Create defect attached to a task."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        session.add(task)
        await session.commit()

        defect = Defect(
            task_id=task.id,
            title="Syntax Error",
            created_at=now,
        )
        session.add(defect)
        await session.commit()
        await session.refresh(defect)
        assert defect.status == DefectStatus.OPEN

    async def test_fk_cascade_on_project_delete(self, session: AsyncSession, base_project: Project) -> None:
        """Boundary: Deleting project wipes tasks."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        session.add(task)
        await session.commit()

        await session.execute(sa.delete(Project).where(Project.name == project_name))
        await session.commit()

        result = await session.execute(sa.select(Task).where(Task.project_name == project_name))
        assert result.scalar_one_or_none() is None

    async def test_fk_cascade_on_task_delete(self, session: AsyncSession, base_project: Project) -> None:
        """Boundary: Deleting task wipes transitions, dependencies, and defects."""
        now = datetime.now(UTC)
        project_name = base_project.name
        t1 = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        t2 = Task(project_name=project_name, title="T2", created_at=now, updated_at=now)
        session.add_all([t1, t2])
        await session.commit()

        dep = TaskDependency(parent_task_id=t1.id, child_task_id=t2.id)
        st = StateTransition(
            task_id=t1.id,
            from_status=TaskStatus.PENDING,
            to_status=TaskStatus.IN_PROGRESS,
            reason=TransitionReason.ACQUIRED,
            timestamp=now,
        )
        defect = Defect(task_id=t1.id, title="Bug", created_at=now)
        session.add_all([dep, st, defect])
        await session.commit()

        await session.execute(sa.delete(Task).where(Task.id == t1.id))
        await session.commit()

        assert (await session.execute(sa.select(TaskDependency))).scalar_one_or_none() is None
        assert (await session.execute(sa.select(StateTransition))).scalar_one_or_none() is None
        assert (await session.execute(sa.select(Defect))).scalar_one_or_none() is None

    async def test_task_status_enum_values(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: All TaskStatus enums save successfully."""
        now = datetime.now(UTC)
        project_name = base_project.name
        for status in TaskStatus:
            task = Task(project_name=project_name, title="T", status=status, created_at=now, updated_at=now)
            session.add(task)
        await session.commit()
        count = (await session.execute(sa.select(sa.func.count()).select_from(Task))).scalar()
        assert count == len(TaskStatus)

    async def test_transition_reason_enum_values(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: All TransitionReason enums save successfully."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        session.add(task)
        await session.commit()

        for reason in TransitionReason:
            st = StateTransition(
                task_id=task.id,
                from_status=TaskStatus.PENDING,
                to_status=TaskStatus.IN_PROGRESS,
                reason=reason,
                timestamp=now,
            )
            session.add(st)
        await session.commit()
        count = (await session.execute(sa.select(sa.func.count()).select_from(StateTransition))).scalar()
        assert count == len(TransitionReason)

    async def test_indexes_exist(self) -> None:
        """Happy path: All composite indexes are registered in metadata."""
        indexes = {idx.name for idx in Task.__table__.indexes}
        assert "idx_task_status_project" in indexes
        assert "idx_task_heartbeat" in indexes
        assert "idx_task_worker" in indexes
        assert "idx_task_epic" in indexes

        dep_indexes = {idx.name for idx in TaskDependency.__table__.indexes}
        assert "idx_dep_child" in dep_indexes
        assert "idx_dep_parent" in dep_indexes

    async def test_self_dependency_rejected(self, session: AsyncSession, base_project: Project) -> None:
        """Hostile Input: Task depending on itself violates CHECK constraint."""
        now = datetime.now(UTC)
        project_name = base_project.name
        t1 = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        session.add(t1)
        await session.commit()

        dep = TaskDependency(parent_task_id=t1.id, child_task_id=t1.id)
        session.add(dep)
        with pytest.raises(IntegrityError, match="CHECK constraint failed: chk_no_self_dependency"):
            await session.commit()

    async def test_handover_context_length_limit(self, session: AsyncSession, base_project: Project) -> None:
        """Boundary: handover_context > 8192 bytes violates CHECK constraint."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(
            project_name=project_name,
            title="T1",
            handover_context="A" * 8193,
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        with pytest.raises(IntegrityError, match="CHECK constraint failed: chk_handover_length"):
            await session.commit()

    async def test_defect_description_length_limit(self, session: AsyncSession, base_project: Project) -> None:
        """Boundary: Defect description > 8192 bytes violates CHECK constraint."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        session.add(task)
        await session.commit()

        defect = Defect(
            task_id=task.id,
            title="Bug",
            description="X" * 8193,
            created_at=now,
        )
        session.add(defect)
        with pytest.raises(IntegrityError, match="CHECK constraint failed: chk_defect_desc_length"):
            await session.commit()

    async def test_defect_status_enum_values(self, session: AsyncSession, base_project: Project) -> None:
        """Happy path: All DefectStatus enums save successfully."""
        now = datetime.now(UTC)
        project_name = base_project.name
        task = Task(project_name=project_name, title="T1", created_at=now, updated_at=now)
        session.add(task)
        await session.commit()

        for status in DefectStatus:
            defect = Defect(
                task_id=task.id,
                title="Bug",
                status=status,
                created_at=now,
            )
            session.add(defect)
        await session.commit()
        count = (await session.execute(sa.select(sa.func.count()).select_from(Defect))).scalar()
        assert count == len(DefectStatus)

    async def test_version_and_attempt_constraints(self, session: AsyncSession, base_project: Project) -> None:
        """Boundary: version and attempt_count constraints."""
        now = datetime.now(UTC)
        project_name = base_project.name

        # version < 1
        task1 = Task(project_name=project_name, title="T1", version=0, created_at=now, updated_at=now)
        session.add(task1)
        with pytest.raises(IntegrityError, match="CHECK constraint failed: chk_version_positive"):
            await session.commit()
        await session.rollback()

        # attempt_count < 0
        task2 = Task(project_name=project_name, title="T2", attempt_count=-1, created_at=now, updated_at=now)
        session.add(task2)
        with pytest.raises(IntegrityError, match="CHECK constraint failed: chk_attempts_non_negative"):
            await session.commit()
