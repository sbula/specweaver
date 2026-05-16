import json
import logging
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener
from specweaver.workspace.memory.hydrator import MemoryHydrator
from specweaver.workspace.memory.store import Task, TaskStatus
from specweaver.workspace.store import Base, Project


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    register_fk_pragma_listener(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def base_project(session: AsyncSession) -> Project:
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
    session: AsyncSession, project_name: str, title: str, status: TaskStatus
) -> Task:
    task = Task(
        id=uuid.uuid4(),
        project_name=project_name,
        title=title,
        status=status,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(task)
    await session.flush()
    return task


@pytest.mark.asyncio
async def test_bootstrap_hydrates_existing_handover(session: AsyncSession, base_project: Project):
    """Happy Path: Task with handover_context JSON has summary in handover_notes."""
    task = await _create_task(
        session, base_project.name, "Task with Handover", TaskStatus.IN_PROGRESS
    )
    task.handover_context = json.dumps({"summary": "This is a handover note."})
    await session.commit()

    hydrator = MemoryHydrator(session, base_project.name)
    result = await hydrator.hydrate()

    assert len(result.active_tasks) == 1
    assert result.active_tasks[0].handover_summary == "This is a handover note."
    assert "This is a handover note." in result.handover_notes


@pytest.mark.asyncio
async def test_bootstrap_with_corrupt_handover(
    session: AsyncSession, base_project: Project, caplog
):
    """Graceful Degradation: Task with invalid JSON logs WARNING, task included without summary."""
    task = await _create_task(
        session, base_project.name, "Task with Corrupt Handover", TaskStatus.IN_PROGRESS
    )
    task.handover_context = "INVALID JSON DATA"
    await session.commit()

    hydrator = MemoryHydrator(session, base_project.name)
    with caplog.at_level(logging.WARNING):
        result = await hydrator.hydrate()

    assert len(result.active_tasks) == 1
    assert result.active_tasks[0].handover_summary is None
    assert "Failed to parse handover context" in caplog.text


@pytest.mark.asyncio
async def test_bootstrap_with_null_handover(session: AsyncSession, base_project: Project):
    """Boundary Case: Task with handover_context = None -> Task included, no handover notes."""
    task = await _create_task(
        session, base_project.name, "Task without Handover", TaskStatus.IN_PROGRESS
    )
    task.handover_context = None
    await session.commit()

    hydrator = MemoryHydrator(session, base_project.name)
    result = await hydrator.hydrate()

    assert len(result.active_tasks) == 1
    assert result.active_tasks[0].handover_summary is None
    assert len(result.handover_notes) == 0


@pytest.mark.asyncio
async def test_bootstrap_trust_tagging(session: AsyncSession, base_project: Project):
    """Hostile/Safety: Task with handover context -> format_prompt_block() includes _trust: low."""
    task = await _create_task(
        session, base_project.name, "Task with Handover", TaskStatus.IN_PROGRESS
    )
    task.handover_context = json.dumps({"summary": "Handover Note"})
    await session.commit()

    hydrator = MemoryHydrator(session, base_project.name)
    result = await hydrator.hydrate()

    # Asserting that the hydration result correctly renders the trust tagging
    xml_output = result.format_prompt_block()

    assert xml_output.startswith("<agent_memory")
    assert 'trust="low"' in xml_output
    assert "_trust" in xml_output


@pytest.mark.asyncio
async def test_bootstrap_multiple_tasks_with_handover(session: AsyncSession, base_project: Project):
    """Boundary Case: 3 IN_PROGRESS tasks, 2 with handover -> Both summaries appear in handover_notes."""
    t1 = await _create_task(session, base_project.name, "T1", TaskStatus.IN_PROGRESS)
    t1.handover_context = json.dumps({"summary": "Note 1"})

    t2 = await _create_task(session, base_project.name, "T2", TaskStatus.IN_PROGRESS)
    t2.handover_context = None

    t3 = await _create_task(session, base_project.name, "T3", TaskStatus.IN_PROGRESS)
    t3.handover_context = json.dumps({"summary": "Note 3"})

    await session.commit()

    hydrator = MemoryHydrator(session, base_project.name)
    result = await hydrator.hydrate()

    assert len(result.active_tasks) == 3
    assert len(result.handover_notes) == 2
    assert "Note 1" in result.handover_notes
    assert "Note 3" in result.handover_notes
