from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.interfaces.cli.main import app as app  # type: ignore

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep

runner = CliRunner()


@pytest.mark.e2e
def test_pipeline_rendering_drops_memory_when_arbiter_profile(
    tmp_path: Path, _isolate_env: Path
) -> None:
    """
    E2E-1: Runs a mock pipeline using ARBITER profile.
    Verifies that the LLM adapter receives a prompt strictly missing the
    <agent_memory>, <constitution>, and <standards> tags.
    """
    project_dir = tmp_path / "proj_profile_arbiter"
    project_dir.mkdir()
    runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

    spec = project_dir / "specs" / "test_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text("# Test Spec", encoding="utf-8")

    from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse

    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"

    captured_prompt = ""

    from specweaver.infrastructure.llm.models import Message, Role

    async def _generate(messages: list[Message], **kwargs: object) -> LLMResponse:
        nonlocal captured_prompt
        # Store the last user message text
        captured_prompt = next((m.content for m in reversed(messages) if m.role == Role.USER), "")
        return LLMResponse(text="VERDICT: ACCEPTED\nDone.", model="mock")

    mock_llm.generate = _generate
    mock_llm.generate_with_tools = _generate

    with (
        patch("specweaver.infrastructure.llm.factory.create_llm_adapter") as mock_req,
        patch("specweaver.infrastructure.llm.router.ModelRouter.get_for_task", return_value=None),
        patch("specweaver.interfaces.cli.hitl_provider.HITLProvider") as mock_hitl_cls,
    ):
        mock_req.return_value = (None, mock_llm, GenerationConfig(model="mock"))
        mock_hitl = AsyncMock()
        mock_hitl.ask = AsyncMock(return_value="")
        mock_hitl_cls.return_value = mock_hitl

        # 'validate_only' invokes the ReviewStepHandler which uses the ARBITER profile by default in some configurations,
        # but wait, ReviewStepHandler uses FULL.
        # DraftStepHandler uses INTERACTIVE.
        # Which one uses ARBITER? The Validate Handler uses FULL, but drops standard rules if not provided.
        # We can pass an explicit pipeline yaml with a custom profile to ensure it uses ARBITER.
        # But wait, step profiles are hardcoded in the handlers.
        # To strictly test the pipeline with a profile, we can intercept the _build_base_prompt call or just use DraftStepHandler (which uses INTERACTIVE -> no constitution/standards).
        # Let's use `sw draft` to trigger the INTERACTIVE profile (which drops constitution and standards).
        # And we'll ensure Agent Memory is dropped if the profile is MINIMAL, but INTERACTIVE keeps memory.
        pass

    # Since we need to test specific profiles (ARBITER, FULL, MINIMAL), and the CLI commands map to specific handlers:
    # `sw draft` -> DraftStepHandler (INTERACTIVE profile -> no constitution/standards, has memory)
    # `sw review` -> ReviewSpecHandler (FULL profile -> has everything)
    # It's better to test the runner programmatically for E2E.

    import asyncio

    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings
    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.handlers._profiles import ARBITER
    from specweaver.core.flow.handlers.base import RunContext
    from specweaver.core.flow.handlers.draft import DraftSpecHandler

    # Create a custom handler that strictly uses the ARBITER profile to ensure E2E connectivity
    class MockHandler(DraftSpecHandler):
        async def execute(self, step: PipelineStep, run_context: RunContext) -> StepResult:
            from specweaver.core.flow.handlers.base import _build_base_prompt

            try:
                # Manually invoke with ARBITER to prove the pipe truncates it
                prompt = await _build_base_prompt(run_context, "Test instructions", profile=ARBITER)

                # Send to mock LLM to capture it
                from specweaver.infrastructure.llm.models import Message, Role

                await run_context.llm.generate([Message(role=Role.USER, content=prompt.build())])

                from specweaver.core.flow.engine.state import StepResult
                from specweaver.core.flow.handlers.base import _now_iso

                return StepResult(
                    status=StepStatus.PASSED,
                    output={},
                    started_at=_now_iso(),
                    completed_at=_now_iso(),
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                raise e

    pipeline = PipelineDefinition.create_single_step(
        name="test_arbiter",
        action=StepAction.DRAFT,
        target=StepTarget.SPEC,
    )

    db_path = _isolate_env / "specweaver.db"
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(db_path))

    # Add dummy agent memory
    conn = sqlite3.connect(db_path)
    from specweaver.core.flow.handlers.base import _now_iso
    from specweaver.workspace.memory.store import EpicStatus

    conn.execute(
        "INSERT INTO memory_epics (id, project_name, title, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            "11111111-2222-3333-4444-555555555555",
            project_dir.name,
            "Test Epic",
            EpicStatus.OPEN.value,
            _now_iso(),
            _now_iso(),
        ),
    )
    conn.execute(
        "INSERT INTO memory_tasks (id, project_name, epic_id, title, status, version, attempt_count, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "22222222-3333-4444-5555-666666666666",
            project_dir.name,
            "11111111-2222-3333-4444-555555555555",
            "Test Task",
            "PENDING",
            1,
            0,
            _now_iso(),
            _now_iso(),
        ),
    )
    conn.commit()
    conn.close()

    context = RunContext(
        project_path=project_dir,
        spec_path=spec,
        llm=mock_llm,
        config=SpecWeaverSettings(llm=LLMSettings(model="mock")),
        db=Database(db_path),
    )

    runner_instance = PipelineRunner(pipeline, context)
    # Inject our mock handler
    runner_instance._registry.register(StepAction.DRAFT, StepTarget.SPEC, MockHandler())  # type: ignore

    asyncio.run(runner_instance.run())

    assert "<instructions>" in captured_prompt
    assert "<agent_memory>" not in captured_prompt
    assert "<constitution>" not in captured_prompt
    assert "<standards>" not in captured_prompt


@pytest.mark.e2e
def test_pipeline_rendering_truncates_context_budget_full_profile(
    tmp_path: Path, _isolate_env: Path
) -> None:
    """
    E2E-2: Runs a mock pipeline using FULL profile with constrained budget.
    Verifies that the output successfully drops the lowest priority block.
    """
    project_dir = tmp_path / "proj_profile_full"
    project_dir.mkdir()
    runner.invoke(app, ["init", project_dir.name, "--path", str(project_dir)])

    spec = project_dir / "specs" / "test_spec.md"
    spec.parent.mkdir(exist_ok=True)
    spec.write_text("# Test Spec", encoding="utf-8")

    from specweaver.infrastructure.llm.models import LLMResponse

    mock_llm = AsyncMock()
    mock_llm.available.return_value = True
    mock_llm.provider_name = "mock"

    captured_prompt = ""

    from specweaver.infrastructure.llm.models import Message, Role

    async def _generate(messages: list[Message], **kwargs: object) -> LLMResponse:
        nonlocal captured_prompt
        captured_prompt = next((m.content for m in reversed(messages) if m.role == Role.USER), "")
        return LLMResponse(text="VERDICT: ACCEPTED\nDone.", model="mock")

    mock_llm.generate = _generate
    mock_llm.generate_with_tools = _generate

    import asyncio

    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings
    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.handlers._profiles import FULL
    from specweaver.core.flow.handlers.base import RunContext
    from specweaver.core.flow.handlers.draft import DraftSpecHandler

    class MockHandler(DraftSpecHandler):
        async def execute(self, step: PipelineStep, run_context: RunContext) -> StepResult:
            from specweaver.core.flow.handlers.base import _build_base_prompt
            from specweaver.infrastructure.llm.models import TokenBudget

            try:
                # Use FULL profile but strict budget
                prompt = await _build_base_prompt(run_context, "Test instructions", profile=FULL)
                prompt._budget = TokenBudget(limit=100)  # strictly limit tokens

                # Add a massive low priority context
                prompt.add_context("A" * 5000, "massive_context", priority=3)

                from specweaver.infrastructure.llm.models import Message, Role

                await run_context.llm.generate([Message(role=Role.USER, content=prompt.build())])

                from specweaver.core.flow.engine.state import StepResult
                from specweaver.core.flow.handlers.base import _now_iso

                return StepResult(
                    status=StepStatus.PASSED,
                    output={},
                    started_at=_now_iso(),
                    completed_at=_now_iso(),
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                raise e

    pipeline = PipelineDefinition.create_single_step(
        name="test_full_budget",
        action=StepAction.DRAFT,
        target=StepTarget.SPEC,
    )

    db_path = _isolate_env / "specweaver.db"
    from specweaver.core.config.db_bootstrap import bootstrap_database

    bootstrap_database(str(db_path))

    context = RunContext(
        project_path=project_dir,
        spec_path=spec,
        llm=mock_llm,
        config=SpecWeaverSettings(llm=LLMSettings(model="mock")),
        db=Database(db_path),
    )

    runner_instance = PipelineRunner(pipeline, context)
    runner_instance._registry.register(StepAction.DRAFT, StepTarget.SPEC, MockHandler())  # type: ignore

    asyncio.run(runner_instance.run())

    assert "<instructions>" in captured_prompt
    # The massive context should be truncated due to strict budget of 100
    assert "massive_context" not in captured_prompt or "[truncated]" in captured_prompt
