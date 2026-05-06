import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener

# We will import MemoryRepository once it's created, but for now this will cause an ImportError
# which is expected for the RED phase.
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.memory.store import EpicStatus
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
class TestMemoryRepositoryEpics:
    async def test_create_epic_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: Create epic with defaults."""
        repo = MemoryRepository(session)
        epic_dict = await repo.create_epic(project_name=base_project.name, title="Test Epic")

        assert "id" in epic_dict
        assert epic_dict["title"] == "Test Epic"
        assert epic_dict["status"] == EpicStatus.OPEN.value
        assert epic_dict["project_name"] == base_project.name

    async def test_create_epic_invalid_project(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError for nonexistent project."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Project does not exist"):
            await repo.create_epic(project_name="nonexistent", title="Test Epic")

    async def test_create_epic_empty_title(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Hostile Input: Raises ValueError for empty/whitespace title (RT-3)."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="title cannot be empty or whitespace-only"):
            await repo.create_epic(project_name=base_project.name, title="   ")

    async def test_list_epics_ordering(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path (RT-8): List epics ordered by created_at desc."""
        repo = MemoryRepository(session)
        # We need sleep or wait to ensure distinct timestamps, or SQLite timestamps are fine.
        # Let's create two epics.
        e1 = await repo.create_epic(project_name=base_project.name, title="Epic 1")
        e2 = await repo.create_epic(project_name=base_project.name, title="Epic 2")

        epics = await repo.list_epics(project_name=base_project.name)
        assert len(epics) == 2
        # Descending order by created_at: newest first
        assert epics[0]["id"] == e2["id"]
        assert epics[1]["id"] == e1["id"]

    async def test_close_epic(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: OPEN -> CLOSED succeeds."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="Test Epic")
        epic_id = uuid.UUID(epic["id"])

        updated_epic = await repo.close_epic(epic_id=epic_id)
        assert updated_epic["status"] == EpicStatus.CLOSED.value

    async def test_close_epic_already_closed(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary: Raises ValueError when already closed."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="Test Epic")
        epic_id = uuid.UUID(epic["id"])

        await repo.close_epic(epic_id=epic_id)

        with pytest.raises(ValueError, match="already CLOSED"):
            await repo.close_epic(epic_id=epic_id)

    async def test_close_epic_not_found(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError when epic not found."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="not found"):
            await repo.close_epic(epic_id=uuid.uuid4())

    async def test_close_epic_updates_timestamp(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary (RT-23): Verifies updated_at is bumped on close."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="Test Epic")
        epic_id = uuid.UUID(epic["id"])

        updated_epic = await repo.close_epic(epic_id=epic_id)
        assert updated_epic["updated_at"] > epic["updated_at"]

    async def test_get_epic_found(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: Fetch epic by ID."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="Test Epic")
        fetched = await repo.get_epic(uuid.UUID(epic["id"]))
        assert fetched is not None
        assert fetched["id"] == epic["id"]

    async def test_get_epic_not_found(self, session: AsyncSession) -> None:
        """Boundary: Fetch epic by ID returns None if not found."""
        repo = MemoryRepository(session)
        fetched = await repo.get_epic(uuid.uuid4())
        assert fetched is None


@pytest.mark.asyncio
class TestMemoryRepositoryTasks:
    async def test_create_task_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: Create task returns dict with correct defaults."""
        repo = MemoryRepository(session)
        task_dict = await repo.create_task(project_name=base_project.name, title="Test Task")

        assert "id" in task_dict
        assert task_dict["title"] == "Test Task"
        # TaskStatus string value
        assert task_dict["status"] == "PENDING"
        assert task_dict["version"] == 1
        assert task_dict["attempt_count"] == 0
        assert task_dict["project_name"] == base_project.name

    async def test_create_task_sets_timestamps(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-19: Verifies created_at and updated_at are set on creation."""
        repo = MemoryRepository(session)
        task_dict = await repo.create_task(project_name=base_project.name, title="Test Task")
        assert task_dict["created_at"] is not None
        assert task_dict["updated_at"] is not None

    async def test_create_task_invalid_project(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError for nonexistent project."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Project does not exist"):
            await repo.create_task(project_name="nonexistent", title="Test Task")

    async def test_create_task_empty_title(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-3: Raises ValueError for empty/whitespace title."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="title cannot be empty or whitespace-only"):
            await repo.create_task(project_name=base_project.name, title="   ")

    async def test_create_task_with_epic(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: Task linked to existing epic."""
        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name=base_project.name, title="Epic")
        task = await repo.create_task(
            project_name=base_project.name, title="Task", epic_id=uuid.UUID(epic["id"])
        )
        assert task["epic_id"] == epic["id"]

    async def test_create_task_invalid_epic(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary: Raises ValueError for nonexistent epic_id."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Epic not found"):
            await repo.create_task(
                project_name=base_project.name, title="Task", epic_id=uuid.uuid4()
            )

    async def test_create_task_epic_project_mismatch(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-13: Raises ValueError if epic belongs to different project."""
        # Create a second project inline
        now = datetime.now(UTC)
        p2 = Project(name="proj2", root_path="/tmp/p2", created_at=now, last_used_at=now)
        session.add(p2)
        await session.flush()

        repo = MemoryRepository(session)
        epic = await repo.create_epic(project_name="proj2", title="Epic in proj2")

        with pytest.raises(ValueError, match="Epic belongs to a different project"):
            await repo.create_task(
                project_name=base_project.name, title="Task", epic_id=uuid.UUID(epic["id"])
            )

    async def test_get_task_found(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: Returns task dict by UUID."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="Task")
        fetched = await repo.get_task(uuid.UUID(task["id"]))
        assert fetched is not None
        assert fetched["id"] == task["id"]

    async def test_get_task_not_found(self, session: AsyncSession) -> None:
        """Boundary: Returns None for unknown UUID."""
        repo = MemoryRepository(session)
        fetched = await repo.get_task(uuid.uuid4())
        assert fetched is None

    async def test_list_tasks_all(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: Lists all tasks for a project."""
        repo = MemoryRepository(session)
        await repo.create_task(project_name=base_project.name, title="T1")
        await repo.create_task(project_name=base_project.name, title="T2")
        tasks = await repo.list_tasks(project_name=base_project.name)
        assert len(tasks) == 2

    async def test_list_tasks_filtered_by_status(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: Filters by TaskStatus.
        We don't have transition_state implemented yet, but we can set status manually for the test
        or just rely on PENDING filtering.
        """
        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")

        # Manually change status of t1 for testing list_tasks filter
        task_model = await session.get(Task, uuid.UUID(t1["id"]))
        task_model.status = TaskStatus.DONE
        await session.flush()

        await repo.create_task(project_name=base_project.name, title="T2")  # PENDING

        pending_tasks = await repo.list_tasks(
            project_name=base_project.name, status=TaskStatus.PENDING
        )
        assert len(pending_tasks) == 1
        assert pending_tasks[0]["title"] == "T2"

        done_tasks = await repo.list_tasks(project_name=base_project.name, status=TaskStatus.DONE)
        assert len(done_tasks) == 1
        assert done_tasks[0]["title"] == "T1"

    async def test_list_tasks_empty_project(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary: Returns empty list for project with no tasks."""
        repo = MemoryRepository(session)
        tasks = await repo.list_tasks(project_name=base_project.name)
        assert tasks == []

    async def test_list_tasks_nonexistent_project(self, session: AsyncSession) -> None:
        """RT-6: Returns empty list for nonexistent project."""
        repo = MemoryRepository(session)
        tasks = await repo.list_tasks(project_name="nonexistent")
        assert tasks == []

    async def test_list_tasks_ordering(self, session: AsyncSession, base_project: Project) -> None:
        """RT-8: Creates 2+ tasks, verifies created_at desc ordering."""
        repo = MemoryRepository(session)
        t1 = await repo.create_task(project_name=base_project.name, title="T1")
        t2 = await repo.create_task(project_name=base_project.name, title="T2")
        tasks = await repo.list_tasks(project_name=base_project.name)
        assert len(tasks) == 2
        assert tasks[0]["id"] == t2["id"]
        assert tasks[1]["id"] == t1["id"]

    async def test_update_task(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: Updates title/description, bumps updated_at (RT-4)."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        updated = await repo.update_task(
            task_id=uuid.UUID(task["id"]), title="T1 Updated", description="New description"
        )
        assert updated["title"] == "T1 Updated"
        assert updated["description"] == "New description"
        assert updated["updated_at"] > task["updated_at"]

    async def test_update_task_empty_title(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-14: Raises ValueError for empty/whitespace title."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        with pytest.raises(ValueError, match="title cannot be empty or whitespace-only"):
            await repo.update_task(task_id=uuid.UUID(task["id"]), title="   ")

    async def test_update_task_not_found(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Task not found"):
            await repo.update_task(task_id=uuid.uuid4(), title="New Title")


@pytest.mark.asyncio
class TestMemoryRepositoryDefects:
    async def test_create_defect_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: Defect created with status=OPEN."""
        from specweaver.workspace.memory.store import DefectStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        defect = await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")
        assert defect["title"] == "Bug 1"
        assert defect["status"] == DefectStatus.OPEN.value
        assert "id" in defect

    async def test_create_defect_invalid_task(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError for nonexistent task."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Task not found"):
            await repo.create_defect(task_id=uuid.uuid4(), title="Bug")

    async def test_create_defect_empty_title(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-3: Raises ValueError for empty/whitespace title."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        with pytest.raises(ValueError, match="title cannot be empty or whitespace-only"):
            await repo.create_defect(task_id=uuid.UUID(task["id"]), title="   ")

    async def test_resolve_defect(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: OPEN -> RESOLVED, resolved_at set."""
        from specweaver.workspace.memory.store import DefectStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        defect = await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")

        resolved = await repo.resolve_defect(defect_id=defect["id"])
        assert resolved["status"] == DefectStatus.RESOLVED.value
        assert resolved["resolved_at"] is not None

    async def test_resolve_defect_already_resolved(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary: Raises ValueError if already resolved."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        defect = await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")

        await repo.resolve_defect(defect_id=defect["id"])
        with pytest.raises(ValueError, match="already RESOLVED"):
            await repo.resolve_defect(defect_id=defect["id"])

    async def test_resolve_defect_not_found(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError."""
        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Defect not found"):
            await repo.resolve_defect(defect_id=99999)

    async def test_list_defects(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: Lists defects for a task."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")
        await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 2")

        defects = await repo.list_defects(task_id=uuid.UUID(task["id"]))
        assert len(defects) == 2

    async def test_list_defects_filtered(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: Filters by DefectStatus."""
        from specweaver.workspace.memory.store import DefectStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        d1 = await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")
        await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 2")

        await repo.resolve_defect(defect_id=d1["id"])

        open_defects = await repo.list_defects(
            task_id=uuid.UUID(task["id"]), status=DefectStatus.OPEN
        )
        assert len(open_defects) == 1
        assert open_defects[0]["title"] == "Bug 2"

        resolved_defects = await repo.list_defects(
            task_id=uuid.UUID(task["id"]), status=DefectStatus.RESOLVED
        )
        assert len(resolved_defects) == 1
        assert resolved_defects[0]["title"] == "Bug 1"

    async def test_structured_logging_on_defect_create(
        self, session: AsyncSession, base_project: Project, caplog
    ) -> None:
        """RT-10: Verifies logger.info emitted on defect creation."""
        import logging

        caplog.set_level(logging.INFO)
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        defect = await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")

        assert any(
            "Defect created" in record.message and str(defect["id"]) in record.message
            for record in caplog.records
        )

    async def test_structured_logging_on_defect_resolve(
        self, session: AsyncSession, base_project: Project, caplog
    ) -> None:
        """RT-10: Verifies logger.info emitted on defect resolution."""
        import logging

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        defect = await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")

        caplog.clear()
        caplog.set_level(logging.INFO)
        await repo.resolve_defect(defect_id=defect["id"])

        assert any(
            "Defect resolved" in record.message and str(defect["id"]) in record.message
            for record in caplog.records
        )


@pytest.mark.asyncio
class TestMemoryRepositoryDependencies:
    async def test_update_handover_context_pydantic(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-15, U-21: Happy Path: Sets HandoverContext on task."""
        from specweaver.workspace.memory.models import HandoverContext

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        context = HandoverContext(summary="test summary")
        updated = await repo.update_handover_context(task_id=uuid.UUID(task["id"]), context=context)
        assert updated["handover_context"] == context.to_json_str()

    async def test_update_handover_context_none_clears(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-20: Boundary: None clears context."""
        from specweaver.workspace.memory.models import HandoverContext

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.update_handover_context(task_id=uuid.UUID(task["id"]), context=HandoverContext())

        cleared = await repo.update_handover_context(task_id=uuid.UUID(task["id"]), context=None)
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


@pytest.mark.asyncio
class TestMemoryRepositoryAcquisition:
    async def test_acquire_task_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """U-9, U-12, U-14: OCC acquisition increments version, sets worker."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        task_id = uuid.UUID(task["id"])

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
        task_id = uuid.UUID(task["id"])

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
        task_id = uuid.UUID(task["id"])

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
        task_id = uuid.UUID(task["id"])

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


@pytest.mark.asyncio
class TestMemoryRepositoryStateMachine:
    async def test_transition_state_happy_path(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: PENDING -> IN_PROGRESS."""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        updated = await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.IN_PROGRESS, reason="Started work"
        )
        assert updated["status"] == TaskStatus.IN_PROGRESS.value

    async def test_transition_state_illegal(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary (RT-5): Raises IllegalStateTransitionError for invalid transition."""
        from specweaver.workspace.memory.errors import IllegalStateTransitionError
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        # PENDING -> DONE is illegal
        with pytest.raises(IllegalStateTransitionError):
            await repo.transition_state(
                task_id=uuid.UUID(task["id"]), to_status=TaskStatus.DONE, reason="Done"
            )

    async def test_transition_state_updates_timestamp(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-4: Verifies updated_at is bumped."""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        updated = await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.IN_PROGRESS, reason="Started"
        )
        assert updated["updated_at"] > task["updated_at"]

    async def test_transition_state_creates_audit_trail(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-16: Verifies TaskTransition row is created."""
        from specweaver.workspace.memory.store import TaskStatus, TransitionReason

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        await repo.transition_state(
            task_id=uuid.UUID(task["id"]),
            to_status=TaskStatus.IN_PROGRESS,
            reason=TransitionReason.ACQUIRED,
        )

        transitions = await repo.get_task_transitions(task_id=uuid.UUID(task["id"]))
        assert len(transitions) == 1
        assert transitions[0]["from_status"] == TaskStatus.PENDING.value
        assert transitions[0]["to_status"] == TaskStatus.IN_PROGRESS.value
        assert transitions[0]["reason"] == TransitionReason.ACQUIRED.value

    async def test_transition_state_task_not_found(self, session: AsyncSession) -> None:
        """Boundary: Raises ValueError."""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        with pytest.raises(ValueError, match="Task not found"):
            await repo.transition_state(
                task_id=uuid.uuid4(), to_status=TaskStatus.IN_PROGRESS, reason=""
            )

    async def test_transition_state_bump_attempt_count(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-22: IN_PROGRESS -> BLOCKED bumps attempt_count."""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        updated = await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.BLOCKED, reason="blocked"
        )
        assert updated["attempt_count"] == 1

    async def test_transition_state_clear_locked_at(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """RT-24: IN_PROGRESS -> BLOCKED clears locked_at/heartbeat."""
        from specweaver.workspace.memory.store import Task, TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        # manually set locked_at
        task_model = await session.get(Task, uuid.UUID(task["id"]))
        task_model.locked_at = datetime.now(UTC)
        task_model.last_heartbeat_at = datetime.now(UTC)
        await session.flush()

        updated = await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.BLOCKED, reason="blocked"
        )
        assert updated["locked_at"] is None
        assert updated["last_heartbeat_at"] is None

    async def test_transition_state_to_done_with_open_defects(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary (RT-9): Raises DefectBlocksCompletionError if OPEN defects exist."""
        from specweaver.workspace.memory.errors import DefectBlocksCompletionError
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")

        with pytest.raises(DefectBlocksCompletionError):
            await repo.transition_state(
                task_id=uuid.UUID(task["id"]), to_status=TaskStatus.DONE, reason="done"
            )

    async def test_transition_state_to_done_without_defects(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Happy Path: IN_PROGRESS -> DONE succeeds if no OPEN defects."""
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        d = await repo.create_defect(task_id=uuid.UUID(task["id"]), title="Bug 1")
        await repo.resolve_defect(defect_id=d["id"])

        updated = await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.DONE, reason="done"
        )
        assert updated["status"] == TaskStatus.DONE.value

    async def test_get_task_transitions(self, session: AsyncSession, base_project: Project) -> None:
        """Happy Path: Returns transitions ordered by created_at."""
        from specweaver.workspace.memory.store import TaskStatus, TransitionReason

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]),
            to_status=TaskStatus.IN_PROGRESS,
            reason=TransitionReason.ACQUIRED,
        )
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]),
            to_status=TaskStatus.BLOCKED,
            reason=TransitionReason.MANUAL_UNBLOCK,
        )

        transitions = await repo.get_task_transitions(task_id=uuid.UUID(task["id"]))
        assert len(transitions) == 2
        assert transitions[0]["reason"] == TransitionReason.ACQUIRED.value
        assert transitions[1]["reason"] == TransitionReason.MANUAL_UNBLOCK.value

    async def test_get_task_transitions_empty(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Boundary: Returns empty list if no transitions."""
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        transitions = await repo.get_task_transitions(task_id=uuid.UUID(task["id"]))
        assert transitions == []

    async def test_structured_logging_on_transition(
        self, session: AsyncSession, base_project: Project, caplog
    ) -> None:
        """RT-10: Verifies logger.info emitted on successful transition."""
        import logging

        from specweaver.workspace.memory.store import TaskStatus

        caplog.set_level(logging.INFO)
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        await repo.transition_state(
            task_id=uuid.UUID(task["id"]), to_status=TaskStatus.IN_PROGRESS, reason="start"
        )

        assert any(
            "Task transition" in record.message and "PENDING → IN_PROGRESS" in record.message
            for record in caplog.records
        )

    async def test_structured_logging_on_illegal_transition(
        self, session: AsyncSession, base_project: Project, caplog
    ) -> None:
        """RT-10: Verifies logger.error emitted on illegal transition."""
        import logging

        from specweaver.workspace.memory.errors import IllegalStateTransitionError
        from specweaver.workspace.memory.store import TaskStatus

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        caplog.set_level(logging.ERROR)
        with pytest.raises(IllegalStateTransitionError):
            await repo.transition_state(
                task_id=uuid.UUID(task["id"]), to_status=TaskStatus.DONE, reason="nope"
            )

        assert any("Illegal state transition" in record.message for record in caplog.records)

    async def test_transition_archived_clears_context(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """FR-7: Transition to ARCHIVED sets handover_context = None."""
        from specweaver.workspace.memory.models import HandoverContext
        from specweaver.workspace.memory.store import TaskStatus, TransitionReason

        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")
        await repo.update_handover_context(
            task_id=uuid.UUID(task["id"]), context=HandoverContext(summary="some context")
        )
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]),
            to_status=TaskStatus.IN_PROGRESS,
            reason=TransitionReason.ACQUIRED,
        )
        await repo.transition_state(
            task_id=uuid.UUID(task["id"]),
            to_status=TaskStatus.DONE,
            reason=TransitionReason.COMPLETED,
        )

        updated = await repo.transition_state(
            task_id=uuid.UUID(task["id"]),
            to_status=TaskStatus.ARCHIVED,
            reason=TransitionReason.ARCHIVED,
        )
        assert updated["handover_context"] is None

    async def test_structured_logging_on_blocked(
        self, session: AsyncSession, base_project: Project, caplog
    ) -> None:
        """NFR-8: Verifies logger.warning emitted on BLOCKED transition."""
        import logging

        from specweaver.workspace.memory.store import TaskStatus, TransitionReason

        caplog.set_level(logging.WARNING)
        repo = MemoryRepository(session)
        task = await repo.create_task(project_name=base_project.name, title="T1")

        await repo.transition_state(
            task_id=uuid.UUID(task["id"]),
            to_status=TaskStatus.BLOCKED,
            reason=TransitionReason.MANUAL_UNBLOCK,
        )
        assert any(
            "Task transition" in record.message and "PENDING → BLOCKED" in record.message
            for record in caplog.records
        )

    async def test_transition_all_valid_paths(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Exhaustively tests every valid cell in the State Transition Matrix."""
        from specweaver.workspace.memory.store import (
            ALLOWED_TRANSITIONS,
            Task,
            TransitionReason,
        )

        repo = MemoryRepository(session)

        for from_status, allowed in ALLOWED_TRANSITIONS.items():
            for to_status in allowed:
                task_dict = await repo.create_task(
                    project_name=base_project.name,
                    title=f"T_val_{from_status.name}_{to_status.name}",
                )
                task_id = uuid.UUID(task_dict["id"])

                task_model = await session.get(Task, task_id)
                task_model.status = from_status
                await session.flush()

                updated = await repo.transition_state(
                    task_id=task_id, to_status=to_status, reason=TransitionReason.MANUAL_UNBLOCK
                )
                assert updated["status"] == to_status.value

    async def test_transition_all_invalid_paths(
        self, session: AsyncSession, base_project: Project
    ) -> None:
        """Exhaustively tests every invalid cell in the State Transition Matrix."""
        from specweaver.workspace.memory.errors import IllegalStateTransitionError
        from specweaver.workspace.memory.store import (
            ALLOWED_TRANSITIONS,
            Task,
            TaskStatus,
            TransitionReason,
        )

        repo = MemoryRepository(session)

        for from_status in TaskStatus:
            allowed = ALLOWED_TRANSITIONS.get(from_status, set())
            for to_status in TaskStatus:
                if to_status == from_status or to_status in allowed:
                    continue

                task_dict = await repo.create_task(
                    project_name=base_project.name,
                    title=f"T_inv_{from_status.name}_{to_status.name}",
                )
                task_id = uuid.UUID(task_dict["id"])

                task_model = await session.get(Task, task_id)
                task_model.status = from_status
                await session.flush()

                with pytest.raises(IllegalStateTransitionError):
                    await repo.transition_state(
                        task_id=task_id, to_status=to_status, reason=TransitionReason.MANUAL_UNBLOCK
                    )
