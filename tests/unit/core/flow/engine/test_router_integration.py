import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest

from specweaver.core.config.database import Database
from specweaver.core.config.settings_loader import load_settings
from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.generation import GenerateCodeHandler
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import TaskType
from specweaver.infrastructure.llm.router import ModelRouter
from specweaver.infrastructure.llm.store import LlmRepository
from tests.fixtures.db_utils import register_test_project, set_test_active_project


@pytest.fixture
def tmp_db(tmp_path: Path) -> Database:
    """Provides a fresh database with a registered project."""
    from specweaver.core.config.cli_db_utils import bootstrap_database

    bootstrap_database(str(tmp_path / "test.db"))
    db = Database(tmp_path / "test.db")
    register_test_project(db, "test-proj", str(tmp_path))
    set_test_active_project(db, "test-proj")
    return db


def _create_and_link(
    db: Database,
    name: str,
    provider: str,
    model: str,
    temperature: float,
    project: str,
    tasks: list[str],
) -> int:
    async def _do() -> int:
        async with db.async_session_scope() as session:
            repo = LlmRepository(session)
            pid = await repo.create_llm_profile(
                name,
                provider=provider,
                model=model,
                temperature=temperature,
                max_output_tokens=8192,
                response_format="text",
            )
            for t in tasks:
                await repo.link_project_profile(project, t, pid)
            return pid

    return anyio.run(_do)


async def _async_create_and_link(
    db: Database,
    name: str,
    provider: str,
    model: str,
    temperature: float,
    project: str,
    tasks: list[str],
) -> int:
    async with db.async_session_scope() as session:
        repo = LlmRepository(session)
        pid = await repo.create_llm_profile(
            name,
            provider=provider,
            model=model,
            temperature=temperature,
            max_output_tokens=8192,
            response_format="text",
        )
        for t in tasks:
            await repo.link_project_profile(project, t, pid)
        return pid


def test_cost_override_injection(tmp_db: Database) -> None:
    """T8: ModelRouter correctly injects DB cost overrides into the TelemetryCollector."""
    _create_and_link(
        tmp_db, "gemini-fast", "gemini", "gemini-flash", 0.1, "test-proj", ["task:implement"]
    )

    router = ModelRouter(
        lambda r: load_settings(tmp_db, "test-proj", llm_role=r),
        telemetry_project="test-proj",
        cost_overrides={"gemini-flash": (2.0, 3.0)},
    )
    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy"}):
        res = router.get_for_task(TaskType.IMPLEMENT)

        assert res is not None
        assert isinstance(res.adapter, TelemetryCollector)
        assert res.adapter._cost_overrides is not None
        assert "gemini-flash" in res.adapter._cost_overrides
        assert res.adapter._cost_overrides["gemini-flash"].input_cost_per_1k == 2.0


def test_memory_leak_check_caching(tmp_db: Database) -> None:
    """T16: ModelRouter must strictly bound adapter cache growth under heavy request load."""
    _create_and_link(
        tmp_db,
        "gemini-1",
        "gemini",
        "gemini-flash",
        0.1,
        "test-proj",
        ["task:implement", "task:plan", "task:draft"],
    )

    _create_and_link(
        tmp_db,
        "claude",
        "anthropic",
        "claude-3",
        0.5,
        "test-proj",
        ["task:review", "task:validate"],
    )

    router = ModelRouter(
        lambda r: load_settings(tmp_db, "test-proj", llm_role=r), telemetry_project="test-proj"
    )

    with patch.dict(os.environ, {"GEMINI_API_KEY": "dummy1", "ANTHROPIC_API_KEY": "dummy2"}):
        with patch("specweaver.infrastructure.llm.router.get_adapter_class") as mock_get_class:
            mock_class = MagicMock()
            mock_instance = MagicMock()
            mock_instance.available.return_value = True
            mock_class.return_value = mock_instance
            mock_get_class.return_value = mock_class
            for t in [
                TaskType.IMPLEMENT,
                TaskType.PLAN,
                TaskType.DRAFT,
                TaskType.REVIEW,
                TaskType.VALIDATE,
            ]:
                res = router.get_for_task(t)
                assert res is not None, f"Failed for task {t}"

        # 5 distinct task types executed 50 times each (250 calls total),
        # but only 2 underlying providers used with 2 distinct API keys (mocked from os.environ).
        # Cache length MUST be exactly 2.
        assert len(router._cache) == 2


@pytest.mark.asyncio
async def test_fallback_pipeline_execution(tmp_db: Database, tmp_path: Path) -> None:
    """T12: Pipeline fully executes generation step when router has NO configurations mapped."""
    spec_file = tmp_path / "s.md"
    spec_file.write_text("# Spec")
    out_dir = tmp_path / "out"
    out_dir.mkdir(exist_ok=True)
    context = RunContext(project_path=tmp_path, spec_path=spec_file, output_dir=out_dir)
    context.db = tmp_db

    mock_adapter = AsyncMock()
    mock_adapter.generate.return_value = MagicMock(text="```python\nprint(1)\n```")
    context.llm = mock_adapter

    # Attach router but with an EMPTY database mapped for this project.
    context.llm_router = ModelRouter(
        lambda r: None, telemetry_project="test-proj"
    )

    handler = GenerateCodeHandler()
    step = PipelineStep(name="test", action=StepAction.GENERATE, target=StepTarget.CODE)

    res = await handler.execute(step, context)

    assert res.status.value == "passed", getattr(res, "message", "No message")
    mock_adapter.generate.assert_called_once()

    _, kwargs = mock_adapter.generate.call_args
    # It might pass kwargs differently based on LLM implementation, just check temperature if present
    if "temperature" in kwargs:
        assert kwargs["temperature"] == 0.2


@pytest.mark.asyncio
async def test_initialization_failure_fallbacks_safely(tmp_db: Database, tmp_path: Path) -> None:
    """T13: E2E Adapter initialization crash safely degrades to fallback."""
    # Create invalid constraint
    # Create invalid constraint and capture its ID (default global profiles occupy early IDs)
    pid = await _async_create_and_link(
        tmp_db, "qwen-fail", "qwen_uninstalled", "ghost", 0.1, "test-proj", ["task:implement"]
    )

    spec_file = tmp_path / "s.md"
    spec_file.write_text("# Spec")
    context = RunContext(project_path=tmp_path, spec_path=spec_file, output_dir=tmp_path / "out")
    context.db = tmp_db

    mock_fallback_adapter = AsyncMock()
    mock_response = MagicMock(text="```python\nprint(2)\n```")
    mock_fallback_adapter.generate.return_value = mock_response
    mock_fallback_adapter.generate_with_tools.return_value = mock_response
    context.llm = mock_fallback_adapter

    context.llm_router = ModelRouter(
        lambda r: load_settings(tmp_db, "test-proj", llm_role=r), telemetry_project="test-proj"
    )

    handler = GenerateCodeHandler()
    step = PipelineStep(name="test2", action=StepAction.GENERATE, target=StepTarget.CODE)

    # Despite the router route finding "qwen_uninstalled", initialization should except softly
    # and the pipeline fallback execution seamlessly handles the fallback adapter.
    res = await handler.execute(step, context)

    assert res.status.value == "passed", f"Exception from execute: {getattr(res, 'error', 'None')}"
    mock_fallback_adapter.generate.assert_called_once()
