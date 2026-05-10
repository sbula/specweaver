import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.config.database import register_fk_pragma_listener
from specweaver.workspace.memory.hydrator import MemoryHydrator
from specweaver.workspace.memory.models import HandoverContext
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.store import Base, Project


@pytest_asyncio.fixture
async def engine() -> AsyncSession:
    """Create an in-memory SQLite database with schema and FK constraints."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    register_fk_pragma_listener(eng.sync_engine)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncSession) -> AsyncSession:
    """Provide a transactional scoped session."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def base_project(session: AsyncSession) -> Project:
    from datetime import UTC, datetime

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
async def test_memory_hydration_integration_flow(
    session: AsyncSession, base_project: Project
) -> None:
    """
    [Integration] Demonstrates end-to-end compatibility between the Write-Side
    (MemoryRepository) and the Read-Side (MemoryHydrator).
    """
    repo = MemoryRepository(session)

    # 1. Use the real Repository API to create an Epic and Task
    import uuid

    epic = await repo.create_epic(base_project.name, "Feature X")
    epic_id_uuid = uuid.UUID(str(epic["id"]))
    task = await repo.create_task(base_project.name, "Implement Y", None, epic_id=epic_id_uuid)

    # 2. Transition task to IN_PROGRESS and simulate an agent finishing its work
    import uuid

    task_id_uuid = uuid.UUID(str(task["id"]))
    await repo.acquire_task(task_id_uuid, "worker_1")

    # Simulate a pipeline finish by creating a HandoverContext
    handover = HandoverContext(
        summary="I finished part 1, but part 2 still needs doing.",
        files_touched=["src/foo.py"],
        errors_encountered=[],
        metadata={"model": "claude"},
    )
    # 3. Update the handover context using the exact mechanism from B-INTL-09
    await repo.update_handover_context(task_id_uuid, handover)
    await session.commit()

    # 4. Use the Hydrator (D-INTL-06) to retrieve and format the data
    hydrator = MemoryHydrator(session, base_project.name)
    result = await hydrator.hydrate()

    xml_block = result.format_prompt_block()

    # 5. Verify the formatted output is correct
    assert '<agent_memory trust="low">' in xml_block
    assert "</agent_memory>" in xml_block

    json_start = xml_block.find(">") + 1
    json_end = xml_block.rfind("</agent_memory>")
    json_str = xml_block[json_start:json_end].strip()

    data = json.loads(json_str)

    # Verify the task appears and has the EXACT summary we set via the repository
    assert len(data["active_tasks"]) == 1
    assert data["active_tasks"][0]["title"] == "Implement Y"
    assert data["active_tasks"][0]["handover_summary"] == handover.summary

    # Verify the handover summary was also correctly added to the untrusted notes section
    assert len(data["handover_notes"]) == 1
    assert data["handover_notes"][0] == handover.summary
