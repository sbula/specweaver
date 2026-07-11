# mypy: ignore-errors
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener
from specweaver.workspace.memory.queries import MemoryQueryService
from specweaver.workspace.memory.store import Defect, DefectStatus, Task, TaskStatus
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


async def _create_task(
    session: AsyncSession,
    project_name: str,
    title: str,
    status: TaskStatus,
    updated_at_offset_hours: int = 0,
) -> Task:
    """Helper to create a task with specific timing."""
    now = datetime.now(UTC)
    task = Task(
        project_name=project_name,
        title=title,
        status=status,
        created_at=now - timedelta(hours=24),
        updated_at=now + timedelta(hours=updated_at_offset_hours),
    )
    session.add(task)
    await session.flush()
    return task


@pytest.mark.asyncio
async def test_get_active_tasks_multi_status(session: AsyncSession, base_project: Project):
    """Happy Path: Returns tasks matching the requested statuses, ordered by updated_at DESC."""
    # Create tasks
    t1 = await _create_task(session, base_project.name, "In progress", TaskStatus.IN_PROGRESS, 1)
    t2 = await _create_task(session, base_project.name, "Blocked", TaskStatus.BLOCKED, 3)
    await _create_task(session, base_project.name, "Pending", TaskStatus.PENDING, 2)

    service = MemoryQueryService(session)
    results = await service.get_active_tasks(
        base_project.name,
        statuses=[TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED],
        order_by="updated_at",
    )

    # Should only return t1 and t2, ordered by updated_at DESC (t2 then t1)
    assert len(results) == 2
    assert results[0].id == t2.id
    assert results[1].id == t1.id


@pytest.mark.asyncio
async def test_get_active_tasks_excludes_done(session: AsyncSession, base_project: Project):
    """Boundary: Ensure DONE tasks are not returned."""
    await _create_task(session, base_project.name, "Done task", TaskStatus.DONE)
    t2 = await _create_task(session, base_project.name, "Active task", TaskStatus.IN_PROGRESS)

    service = MemoryQueryService(session)
    results = await service.get_active_tasks(
        base_project.name,
        statuses=[TaskStatus.IN_PROGRESS],
    )

    assert len(results) == 1
    assert results[0].id == t2.id


@pytest.mark.asyncio
async def test_get_active_tasks_order_by_created_at(session: AsyncSession, base_project: Project):
    """Ordering: Alternative ordering by created_at works."""
    t1 = await _create_task(session, base_project.name, "Task 1", TaskStatus.IN_PROGRESS)
    t2 = await _create_task(session, base_project.name, "Task 2", TaskStatus.IN_PROGRESS)

    # Manually tweak created_at
    t1.created_at = datetime.now(UTC) + timedelta(hours=1)
    t2.created_at = datetime.now(UTC) + timedelta(hours=2)
    await session.flush()

    service = MemoryQueryService(session)
    results = await service.get_active_tasks(
        base_project.name,
        statuses=[TaskStatus.IN_PROGRESS],
        order_by="created_at",
    )

    assert len(results) == 2
    assert results[0].id == t2.id  # Newest created_at first


@pytest.mark.asyncio
async def test_get_active_tasks_limit(session: AsyncSession, base_project: Project):
    """Boundary: Respects limit parameter."""
    for i in range(5):
        await _create_task(session, base_project.name, f"Task {i}", TaskStatus.IN_PROGRESS)

    service = MemoryQueryService(session)
    results = await service.get_active_tasks(
        base_project.name,
        statuses=[TaskStatus.IN_PROGRESS],
        limit=3,
    )

    assert len(results) == 3


@pytest.mark.asyncio
async def test_get_active_tasks_empty_project(session: AsyncSession, base_project: Project):
    """Boundary: Returns [] for project with no tasks."""
    service = MemoryQueryService(session)
    results = await service.get_active_tasks(
        base_project.name,
        statuses=[TaskStatus.IN_PROGRESS],
    )

    assert results == []


@pytest.mark.asyncio
async def test_get_active_tasks_invalid_order_by(session: AsyncSession, base_project: Project):
    """Guard: Raises ValueError for unknown order_by parameter to prevent injection."""
    service = MemoryQueryService(session)

    with pytest.raises(ValueError, match="Invalid order_by field"):
        await service.get_active_tasks(
            base_project.name,
            statuses=[TaskStatus.IN_PROGRESS],
            order_by="status; DROP TABLE tasks",
        )


@pytest.mark.asyncio
async def test_get_recent_done_tasks_within_24h(session: AsyncSession, base_project: Project):
    """Happy Path: Returns DONE tasks within 24h that have handover context."""
    # Recent done task WITH handover
    t1 = await _create_task(session, base_project.name, "Recent Done", TaskStatus.DONE, 0)
    t1.handover_context = '{"summary": "did things"}'

    # Recent done task WITHOUT handover (should be excluded)
    await _create_task(session, base_project.name, "No handover", TaskStatus.DONE, 0)

    # Active task (should be excluded)
    await _create_task(session, base_project.name, "Active", TaskStatus.IN_PROGRESS, 0)

    service = MemoryQueryService(session)
    results = await service.get_recent_done_tasks(base_project.name)

    assert len(results) == 1
    assert results[0].id == t1.id


@pytest.mark.asyncio
async def test_get_recent_done_tasks_excludes_stale(session: AsyncSession, base_project: Project):
    """Boundary: Excludes DONE tasks > 24h old."""
    t1 = await _create_task(session, base_project.name, "Stale", TaskStatus.DONE, -25)  # 25h ago
    t1.handover_context = '{"summary": "too old"}'

    t2 = await _create_task(session, base_project.name, "Recent", TaskStatus.DONE, -10)  # 10h ago
    t2.handover_context = '{"summary": "recent"}'

    service = MemoryQueryService(session)
    results = await service.get_recent_done_tasks(base_project.name)

    assert len(results) == 1
    assert results[0].id == t2.id


@pytest.mark.asyncio
async def test_get_recent_done_tasks_custom_age(session: AsyncSession, base_project: Project):
    """Config: Respects max_age_hours parameter."""
    t1 = await _create_task(session, base_project.name, "Stale", TaskStatus.DONE, -30)  # 30h ago
    t1.handover_context = '{"summary": "old"}'

    service = MemoryQueryService(session)

    # Default 24h excludes it
    res1 = await service.get_recent_done_tasks(base_project.name)
    assert len(res1) == 0

    # 48h includes it
    res2 = await service.get_recent_done_tasks(base_project.name, max_age_hours=48)
    assert len(res2) == 1
    assert res2[0].id == t1.id


async def _create_defect(
    session: AsyncSession, task_id: uuid.UUID, title: str, status: DefectStatus
) -> Defect:
    now = datetime.now(UTC)
    defect = Defect(
        task_id=task_id,
        title=title,
        status=status,
        created_at=now,
    )
    session.add(defect)
    await session.flush()
    return defect


@pytest.mark.asyncio
async def test_get_open_defects_batch(session: AsyncSession, base_project: Project):
    """Happy Path: Returns defects grouped by task_id."""
    t1 = await _create_task(session, base_project.name, "T1", TaskStatus.BLOCKED)
    t2 = await _create_task(session, base_project.name, "T2", TaskStatus.BLOCKED)

    d1 = await _create_defect(session, t1.id, "D1", DefectStatus.OPEN)
    d2 = await _create_defect(session, t1.id, "D2", DefectStatus.OPEN)
    d3 = await _create_defect(session, t2.id, "D3", DefectStatus.OPEN)

    service = MemoryQueryService(session)
    results = await service.get_open_defects_for_tasks([t1.id, t2.id])

    assert len(results) == 2
    assert len(results[t1.id]) == 2
    assert {d.id for d in results[t1.id]} == {d1.id, d2.id}
    assert len(results[t2.id]) == 1
    assert results[t2.id][0].id == d3.id


@pytest.mark.asyncio
async def test_get_open_defects_excludes_resolved(session: AsyncSession, base_project: Project):
    """Boundary: Only OPEN defects are returned."""
    t1 = await _create_task(session, base_project.name, "T1", TaskStatus.BLOCKED)

    d1 = await _create_defect(session, t1.id, "Open", DefectStatus.OPEN)
    await _create_defect(session, t1.id, "Resolved", DefectStatus.RESOLVED)

    service = MemoryQueryService(session)
    results = await service.get_open_defects_for_tasks([t1.id])

    assert len(results) == 1
    assert len(results[t1.id]) == 1
    assert results[t1.id][0].id == d1.id


@pytest.mark.asyncio
async def test_get_open_defects_empty_ids(session: AsyncSession):
    """Boundary: Returns {} immediately for empty task_ids."""
    service = MemoryQueryService(session)
    results = await service.get_open_defects_for_tasks([])
    assert results == {}
