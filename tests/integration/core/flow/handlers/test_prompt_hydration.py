import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from specweaver.core.flow.handlers.base import RunContext, _build_base_prompt
from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig
from specweaver.workspace.memory.models import HandoverContext
from specweaver.workspace.memory.repository import MemoryRepository
from specweaver.workspace.store import Base, Project


@pytest_asyncio.fixture
async def memory_db_engine() -> AsyncGenerator[Any, None]:
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(memory_db_engine: Any) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(memory_db_engine, expire_on_commit=False) as session:
        yield session


@pytest_asyncio.fixture
async def base_project(db_session: AsyncSession) -> Project:
    from datetime import UTC, datetime

    now = datetime.now(UTC)
    project = Project(
        name="test_proj",
        root_path="/tmp/test",
        created_at=now,
        last_used_at=now,
    )
    db_session.add(project)
    await db_session.flush()
    await db_session.refresh(project)
    return project


class FakeDB:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def async_session_scope(self) -> AsyncGenerator[AsyncSession, None]:
        yield self._session


@pytest.mark.asyncio
async def test_build_base_prompt_with_hydration(db_session: AsyncSession, base_project: Project) -> None:
    """
    [Integration - Happy Path]
    Test that _build_base_prompt properly integrates with the real SQLite
    database via MemoryHydrator and outputs a valid <agent_memory> block.
    """
    project_name = base_project.name

    # 1. Pre-populate the SQLite DB using the real Write-Side (MemoryRepository)
    repo = MemoryRepository(db_session)
    epic = await repo.create_epic(project_name, "Integration Epic")
    epic_id_uuid = uuid.UUID(str(epic["id"]))
    task = await repo.create_task(project_name, "Integration Task", None, epic_id=epic_id_uuid)
    task_id_uuid = uuid.UUID(str(task["id"]))
    await repo.acquire_task(task_id_uuid, "integration_worker")

    handover = HandoverContext(
        summary="Completed part 1 successfully.",
        files_touched=["src/test.py"],
        errors_encountered=[],
        metadata={},
    )
    await repo.update_handover_context(task_id_uuid, handover)
    await db_session.commit()

    # 2. Setup RunContext with the real database
    context = RunContext(
        project_path=Path(f"/tmp/{project_name}"),
        spec_path=Path("/tmp/fake_spec.md"),
        project_metadata=ProjectMetadata(
            project_name=project_name,
            archetype="generic",
            language_target="python",
            date_iso="2026-05-09",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test"),
        ),
        constitution="Be safe.",
        standards="Use types.",
        db=FakeDB(db_session),
    )

    # 3. Call the orchestrator function
    builder = await _build_base_prompt(context, "Do the integration test.")
    prompt = builder.build()

    # 4. Verify hydration was successful
    assert "Do the integration test." in prompt
    assert "<agent_memory" in prompt
    assert "Integration Task" in prompt
    assert "Completed part 1 successfully." in prompt


@pytest.mark.asyncio
async def test_build_base_prompt_with_corrupted_handover(db_session: AsyncSession, base_project: Project) -> None:
    """
    [Integration - Degradation]
    Test that a corrupted handover_context in the real database causes
    the MemoryHydrator to throw, which _build_base_prompt gracefully catches
    without crashing, resulting in a prompt without the memory block.
    """
    project_name = base_project.name

    # 1. Insert corrupted JSON directly into the DB using raw SQL
    repo = MemoryRepository(db_session)
    epic = await repo.create_epic(project_name, "Corrupted Epic")
    epic_id_uuid = uuid.UUID(str(epic["id"]))
    task = await repo.create_task(project_name, "Corrupted Task", None, epic_id=epic_id_uuid)
    task_id_uuid = uuid.UUID(str(task["id"]))
    await repo.acquire_task(task_id_uuid, "integration_worker")

    # Inject invalid JSON directly
    from sqlalchemy import text
    await db_session.execute(text(
        "UPDATE memory_tasks SET handover_context = 'INVALID_JSON_HERE' WHERE title = 'Corrupted Task'"
    ))
    await db_session.commit()

    # 2. Setup RunContext
    context = RunContext(
        project_path=Path(f"/tmp/{project_name}"),
        spec_path=Path("/tmp/fake_spec.md"),
        project_metadata=ProjectMetadata(
            project_name=project_name,
            archetype="generic",
            language_target="python",
            date_iso="2026-05-09",
            safe_config=PromptSafeConfig(llm_model="test", llm_provider="test", validation_rules={})
        ),
        constitution="Be safe.",
        standards="Use types.",
        db=FakeDB(db_session),
    )

    # 3. Call the function - it should NOT crash
    builder = await _build_base_prompt(context, "Test degradation.")
    prompt = builder.build()

    # 4. Verify prompt was built and memory was included but handover context was dropped
    assert "Test degradation." in prompt
    assert "<agent_memory" in prompt
    assert "Corrupted Task" in prompt
    assert "INVALID_JSON_HERE" not in prompt
