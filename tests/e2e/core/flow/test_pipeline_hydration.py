import uuid
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.core.config.database import Database
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse
from specweaver.interfaces.cli.main import app  # type: ignore
from specweaver.workspace.memory.models import HandoverContext
from specweaver.workspace.memory.repository import MemoryRepository

runner = CliRunner()


def _make_mock_llm(captured_prompts: list[str]) -> object:
    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"

    async def _generate(
        messages: list[Any], config: Any = None, dispatcher: Any = None, on_tool_round: Any = None
    ) -> LLMResponse:
        for msg in messages:
            if hasattr(msg, "content"):
                captured_prompts.append(msg.content)
        return LLMResponse(text="VERDICT: ACCEPTED\nLooks good.", model="mock")

    mock_llm.generate = _generate
    mock_llm.generate_with_tools = _generate
    return mock_llm


@pytest.fixture()
def project_with_spec(
    tmp_path: Path, _mock_db: Database, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    project_dir = tmp_path / "e2e-pipe"
    project_dir.mkdir()

    # Patch the CLI's cached DB so `init` hits _mock_db
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: _mock_db)

    result = runner.invoke(app, ["init", "e2e-pipe", "--path", str(project_dir)])
    assert result.exit_code == 0

    spec = project_dir / "specs" / "test_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text("# Test Spec\n\n## 1. Purpose\n\nTest pipeline hydration.", encoding="utf-8")
    return project_dir, spec


class TestPipelineHydrationE2E:
    def test_pipeline_execution_with_populated_memory(
        self, project_with_spec: tuple[Path, Path], _mock_db: Database
    ) -> None:
        """
        [E2E - Happy Path]
        Pipeline execution with a populated MemoryBank successfully injects
        <agent_memory> into the LLM adapter call.
        """
        project_dir, spec = project_with_spec
        project_name = "e2e-pipe"
        db = _mock_db

        async def prepopulate_db() -> None:
            async with db.async_session_scope() as session:
                from sqlalchemy import text

                res = await session.execute(text("SELECT * FROM projects"))
                print("PROJECTS IN DB:", res.fetchall())

                repo = MemoryRepository(session)
                epic = await repo.create_epic(project_name, "E2E Epic")
                epic_id_uuid = uuid.UUID(str(epic["id"]))
                task = await repo.create_task(project_name, "E2E Task", None, epic_id=epic_id_uuid)
                task_id_uuid = uuid.UUID(str(task["id"]))
                await repo.acquire_task(task_id_uuid, "e2e_worker")

                handover = HandoverContext(
                    summary="E2E test memory.", files_touched=[], errors_encountered=[], metadata={}
                )
                await repo.update_handover_context(task_id_uuid, handover)
                await session.commit()

        import asyncio

        asyncio.run(prepopulate_db())

        # 2. Mock the LLM to capture the prompt
        captured_prompts: list[str] = []
        mock_llm = _make_mock_llm(captured_prompts)

        # 3. Run the pipeline command (e.g. review)
        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            result = runner.invoke(app, ["review", str(spec), "--project", str(project_dir)])

        # 4. Verify successful execution
        assert result.exit_code == 0

        # 5. Verify the prompt contains memory
        full_prompt = "\n".join(captured_prompts)
        assert "<agent_memory" in full_prompt
        assert "E2E Task" in full_prompt
        assert "E2E test memory." in full_prompt

    def test_pipeline_execution_with_empty_memory(
        self, project_with_spec: tuple[Path, Path], _mock_db: Database
    ) -> None:
        """
        [E2E - Degradation]
        Pipeline execution with an empty/missing memory bank bypasses
        hydration and completes successfully without <agent_memory>.
        """
        project_dir, spec = project_with_spec

        async def check_db() -> None:
            async with _mock_db.async_session_scope() as session:
                from sqlalchemy import text

                res = await session.execute(text("SELECT * FROM projects"))
                print("PROJECTS IN DB:", res.fetchall())

        import asyncio

        asyncio.run(check_db())

        captured_prompts: list[str] = []
        mock_llm = _make_mock_llm(captured_prompts)

        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            result = runner.invoke(app, ["review", str(spec), "--project", str(project_dir)])

        assert result.exit_code == 0
        full_prompt = "\n".join(captured_prompts)
        assert "<agent_memory" not in full_prompt

    def test_pipeline_execution_with_corrupted_memory(
        self, project_with_spec: tuple[Path, Path], _mock_db: Database
    ) -> None:
        """
        [E2E - Graceful Degradation]
        Pipeline execution with a corrupted handover_context in the MemoryBank
        bypasses hydration cleanly and completes successfully without <agent_memory>.
        """
        project_dir, spec = project_with_spec
        project_name = "e2e-pipe"
        db = _mock_db

        async def prepopulate_db_corrupted() -> None:
            async with db.async_session_scope() as session:
                from sqlalchemy import text

                res = await session.execute(text("SELECT * FROM projects"))
                print("PROJECTS IN DB CORRUPTED:", res.fetchall())

                # The project already exists from `init`. We just need an Epic and a corrupted Task.
                await session.execute(
                    text(
                        "INSERT INTO memory_epics (id, project_name, title, status, created_at, updated_at) "
                        "VALUES (:id, :proj, :title, 'OPEN', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
                    ),
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174000",
                        "proj": project_name,
                        "title": "Epic",
                    },
                )

                # Insert a corrupted task directly
                await session.execute(
                    text(
                        "INSERT INTO memory_tasks (id, project_name, title, status, created_at, updated_at, handover_context, epic_id, assigned_worker_id, last_heartbeat_at, version, attempt_count) "
                        "VALUES (:id, :proj, :title, 'IN_PROGRESS', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, :bad_json, :epic_id, NULL, NULL, 1, 0)"
                    ),
                    {
                        "id": "123e4567-e89b-12d3-a456-426614174001",
                        "proj": project_name,
                        "title": "Corrupted Task",
                        "epic_id": "123e4567-e89b-12d3-a456-426614174000",
                        "bad_json": '{"invalid": "schema", "missing": "fields"}',
                    },
                )

                await session.commit()

        import asyncio

        asyncio.run(prepopulate_db_corrupted())

        captured_prompts: list[str] = []
        mock_llm = _make_mock_llm(captured_prompts)

        with patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req:
            mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
            result = runner.invoke(app, ["review", str(spec), "--project", str(project_dir)])

        assert result.exit_code == 0
        full_prompt = "\n".join(captured_prompts)
        assert "<agent_memory" in full_prompt
        assert "Corrupted Task" in full_prompt
        assert "invalid" not in full_prompt  # The bad JSON should be dropped cleanly
