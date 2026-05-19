from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.handlers._profiles import ARBITER, FULL, INTERACTIVE, MINIMAL
from specweaver.core.flow.handlers.base import RunContext, _build_base_prompt
from specweaver.infrastructure.llm.models import ProjectMetadata, PromptSafeConfig


@pytest.fixture
def mock_db():
    db = MagicMock()
    session = AsyncMock()
    session_scope = AsyncMock()
    session_scope.__aenter__.return_value = session
    db.async_session_scope.return_value = session_scope
    return db


@pytest.fixture
def run_context(mock_db):
    metadata = ProjectMetadata(
        project_name="fake_project",
        archetype="generic",
        language_target="python",
        date_iso="2026-05-09",
        safe_config=PromptSafeConfig(llm_provider="fake", llm_model="fake"),
    )
    return RunContext(
        project_path=Path("/tmp/fake_project"),
        spec_path=Path("/tmp/fake_project/spec.yaml"),
        constitution="Always be honest",
        standards="Use type hints",
        db=mock_db,
        project_metadata=metadata,
        parsers={},
    )


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_with_profile_full(mock_hydrator_class, run_context):
    # H1
    mock_hydrator = mock_hydrator_class.return_value
    mock_result = MagicMock()
    mock_result.task_count = 1
    mock_result.token_estimate = 100
    mock_result.format_prompt_block.return_value = "Memory Tasks"
    mock_hydrator.hydrate = AsyncMock(return_value=mock_result)

    builder = await _build_base_prompt(run_context, "Instr", profile=FULL)
    output = builder.build()

    assert "<constitution>" in output
    assert "<standards>" in output
    assert "<agent_memory>" in output


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_with_profile_interactive(mock_hydrator_class, run_context):
    # H2
    mock_hydrator = mock_hydrator_class.return_value
    mock_result = MagicMock()
    mock_result.task_count = 1
    mock_result.token_estimate = 100
    mock_result.format_prompt_block.return_value = "Memory Tasks"
    mock_hydrator.hydrate = AsyncMock(return_value=mock_result)

    builder = await _build_base_prompt(run_context, "Instr", profile=INTERACTIVE)
    output = builder.build()

    assert "<constitution>" not in output
    assert "<standards>" not in output
    assert "<agent_memory>" in output


@pytest.mark.asyncio
async def test_build_base_prompt_with_profile_arbiter(run_context):
    # H3
    builder = await _build_base_prompt(run_context, "Instr", profile=ARBITER)
    output = builder.build()
    assert "<constitution>" not in output
    assert "<standards>" not in output
    assert "<project_metadata>" not in output


@pytest.mark.asyncio
async def test_build_base_prompt_with_profile_minimal(run_context):
    # H4
    builder = await _build_base_prompt(run_context, "Instr", profile=MINIMAL)
    output = builder.build()
    assert "<constitution>" not in output
    assert "<standards>" not in output
    assert "<agent_memory>" not in output


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_memory_skipped_when_slot_inactive(
    mock_hydrator_class, run_context
):
    # H7
    builder = await _build_base_prompt(run_context, "Instr", profile=MINIMAL)
    output = builder.build()
    assert "<agent_memory>" not in output
    run_context.db.async_session_scope.assert_not_called()


@pytest.mark.asyncio
@patch("specweaver.workspace.memory.hydrator.MemoryHydrator")
async def test_build_base_prompt_memory_hydrated_when_slot_active(mock_hydrator_class, run_context):
    # H8
    mock_hydrator = mock_hydrator_class.return_value
    mock_result = MagicMock()
    mock_result.task_count = 1
    mock_result.token_estimate = 100
    mock_result.format_prompt_block.return_value = "Mem Content"
    mock_hydrator.hydrate = AsyncMock(return_value=mock_result)

    builder = await _build_base_prompt(run_context, "Instr", profile=FULL)
    mem_blocks = [b for b in builder._blocks if b.kind == "agent_memory"]
    assert len(mem_blocks) == 1
    assert mem_blocks[0].text == "Mem Content"


@pytest.mark.asyncio
async def test_build_base_prompt_memory_slot_active_but_db_none(run_context):
    # H9
    run_context.db = None
    builder = await _build_base_prompt(run_context, "Instr", profile=FULL)
    output = builder.build()
    assert "<agent_memory>" not in output


class TestHandlerProfileIntegration:
    """Integration tests verifying handlers correctly pass render_profile overrides to _build_base_prompt."""

    @pytest.fixture
    def mock_build_base_prompt(self):
        with patch("specweaver.core.flow.handlers.base._build_base_prompt") as mock:
            mock.return_value = MagicMock()
            yield mock

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "handler_class, default_profile, module_path",
        [
            ("GenerateCodeHandler", FULL, "specweaver.core.flow.handlers.generation"),
            ("GenerateTestsHandler", FULL, "specweaver.core.flow.handlers.generation"),
            ("PlanSpecHandler", FULL, "specweaver.core.flow.handlers.generation"),
            ("ReviewSpecHandler", FULL, "specweaver.core.flow.handlers.review"),
            ("ReviewCodeHandler", FULL, "specweaver.core.flow.handlers.review"),
            ("DraftSpecHandler", INTERACTIVE, "specweaver.core.flow.handlers.draft"),
            ("DecomposeFeatureHandler", MINIMAL, "specweaver.core.flow.handlers.decompose"),
            ("ArbitrateVerdictHandler", ARBITER, "specweaver.core.flow.handlers.arbiter"),
        ],
    )
    async def test_handler_backward_compatibility_uses_default_profile(
        self,
        handler_class: str,
        default_profile: Any,
        module_path: str,
        run_context: Any,
        mock_build_base_prompt: Any,
    ) -> None:
        """H10: Handlers use their static default profile when no render_profile is in params."""
        import importlib

        from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget

        module = importlib.import_module(module_path)
        handler_class_ref = getattr(module, handler_class)
        handler = handler_class_ref()
        step = PipelineStep(
            name="test_step", action=StepAction.GENERATE, target=StepTarget.CODE, params={}
        )

        # We expect a failure because LLM is None or other setup is missing, but that's fine.
        # We just want to check the call args to _build_base_prompt if it gets called.
        # Let's mock the necessary context components.
        run_context.llm = MagicMock()
        run_context.context_provider = MagicMock()

        # We mock the specific generator/drafter/etc to prevent full execution.
        def mock_exists(self: Any) -> bool:
            return not ("draft" in handler_class.lower() and "spec" in str(self))

        with (
            patch(
                "specweaver.core.flow.handlers.generation.Generator", new=MagicMock(), create=True
            ),
            patch("specweaver.core.flow.handlers.review.Reviewer", new=MagicMock(), create=True),
            patch("specweaver.core.flow.handlers.draft.Drafter", new=MagicMock(), create=True),
            patch(
                "specweaver.core.flow.handlers.decompose.FeatureDecomposer",
                new=MagicMock(),
                create=True,
            ),
            patch(
                "specweaver.core.flow.handlers.context_assembler.evaluate_and_fetch_skeleton_context",
                return_value=[],
            ),
            patch(
                "specweaver.core.flow.handlers.mcp_assembler.evaluate_and_fetch_mcp_context",
                return_value=None,
            ),
            patch(
                "specweaver.core.flow.handlers.review._build_tool_dispatcher",
                return_value=MagicMock(),
            ),
            patch(
                "specweaver.core.flow.handlers.generation._build_tool_dispatcher",
                return_value=MagicMock(),
            ),
            patch(
                "specweaver.sandbox.language.core.stack_trace_filter_factory.create_stack_trace_filter",
                return_value=MagicMock(),
            ),
            patch(
                "specweaver.core.flow.handlers.review.ReviewCodeHandler._find_code_path",
                return_value=Path("/tmp/fake_project/code.py"),
            ),
            patch("pathlib.Path.exists", autospec=True, side_effect=mock_exists),
            patch("pathlib.Path.read_text", return_value="mock spec"),
        ):
            result = await handler.execute(step, run_context)
            print(f"\n\nBACKWARD COMPAT RESULT: {result}\n\n")

        # Assert _build_base_prompt was called with the default profile
        assert mock_build_base_prompt.called, f"_build_base_prompt not called for {handler_class}"
        call_kwargs = mock_build_base_prompt.call_args.kwargs
        assert call_kwargs.get("profile") is default_profile

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "handler_class, default_profile, module_path",
        [
            ("GenerateCodeHandler", FULL, "specweaver.core.flow.handlers.generation"),
            ("GenerateTestsHandler", FULL, "specweaver.core.flow.handlers.generation"),
            ("PlanSpecHandler", FULL, "specweaver.core.flow.handlers.generation"),
            ("ReviewSpecHandler", FULL, "specweaver.core.flow.handlers.review"),
            ("ReviewCodeHandler", FULL, "specweaver.core.flow.handlers.review"),
            ("DraftSpecHandler", INTERACTIVE, "specweaver.core.flow.handlers.draft"),
            ("DecomposeFeatureHandler", MINIMAL, "specweaver.core.flow.handlers.decompose"),
            ("ArbitrateVerdictHandler", ARBITER, "specweaver.core.flow.handlers.arbiter"),
        ],
    )
    async def test_handler_uses_override_profile(
        self,
        handler_class: str,
        default_profile: Any,
        module_path: str,
        run_context: Any,
        mock_build_base_prompt: Any,
    ) -> None:
        """H11: Handlers use the render_profile override from step.params."""
        import importlib

        from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget

        module = importlib.import_module(module_path)
        handler_class_ref = getattr(module, handler_class)
        handler = handler_class_ref()
        # Override with MINIMAL
        step = PipelineStep(
            name="test_step",
            action=StepAction.GENERATE,
            target=StepTarget.CODE,
            params={"render_profile": "MINIMAL"},
        )

        run_context.llm = MagicMock()
        run_context.context_provider = MagicMock()

        def mock_exists(self: Any) -> bool:
            return not ("draft" in handler_class.lower() and "spec" in str(self))

        with (
            patch(
                "specweaver.core.flow.handlers.generation.Generator", new=MagicMock(), create=True
            ),
            patch("specweaver.core.flow.handlers.review.Reviewer", new=MagicMock(), create=True),
            patch(
                "specweaver.core.flow.handlers.context_assembler.evaluate_and_fetch_skeleton_context",
                return_value=[],
            ),
            patch(
                "specweaver.core.flow.handlers.mcp_assembler.evaluate_and_fetch_mcp_context",
                return_value=None,
            ),
            patch(
                "specweaver.core.flow.handlers.review._build_tool_dispatcher",
                return_value=MagicMock(),
            ),
            patch(
                "specweaver.core.flow.handlers.generation._build_tool_dispatcher",
                return_value=MagicMock(),
            ),
            patch(
                "specweaver.core.flow.handlers.review.ReviewCodeHandler._find_code_path",
                return_value=Path("/tmp/fake_project/code.py"),
            ),
            patch("pathlib.Path.exists", autospec=True, side_effect=mock_exists),
            patch("pathlib.Path.read_text", return_value="mock spec"),
        ):
            result = await handler.execute(step, run_context)
            print(f"\n\nRESULT: {result}\n\n")

        assert mock_build_base_prompt.called
        call_kwargs = mock_build_base_prompt.call_args.kwargs
        assert call_kwargs.get("profile") is MINIMAL

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "handler_class, module_path",
        [
            ("GenerateCodeHandler", "specweaver.core.flow.handlers.generation"),
            ("GenerateTestsHandler", "specweaver.core.flow.handlers.generation"),
            ("PlanSpecHandler", "specweaver.core.flow.handlers.generation"),
            ("ReviewSpecHandler", "specweaver.core.flow.handlers.review"),
            ("ReviewCodeHandler", "specweaver.core.flow.handlers.review"),
            ("DraftSpecHandler", "specweaver.core.flow.handlers.draft"),
            ("DecomposeFeatureHandler", "specweaver.core.flow.handlers.decompose"),
            ("ArbitrateVerdictHandler", "specweaver.core.flow.handlers.arbiter"),
        ],
    )
    async def test_handler_returns_error_result_on_invalid_profile(
        self, handler_class: str, module_path: str, run_context: Any, mock_build_base_prompt: Any
    ) -> None:
        """H12: Handlers return a StepStatus.ERROR result when resolve_profile raises ValueError."""
        import importlib

        from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
        from specweaver.core.flow.engine.state import StepStatus

        module = importlib.import_module(module_path)
        handler_class_ref = getattr(module, handler_class)
        handler = handler_class_ref()
        # Override with INVALID
        step = PipelineStep(
            name="test_step",
            action=StepAction.GENERATE,
            target=StepTarget.CODE,
            params={"render_profile": "INVALID"},
        )

        run_context.llm = MagicMock()
        run_context.context_provider = MagicMock()

        # We don't need to mock Generator here because resolve_profile should fail before instantiation
        def mock_exists(self: Any) -> bool:
            if "draft" in handler_class.lower() and "spec" in str(self):
                return False
            return True

        with (
            patch(
                "specweaver.core.flow.handlers.generation.Generator", new=MagicMock(), create=True
            ),
            patch("specweaver.core.flow.handlers.review.Reviewer", new=MagicMock(), create=True),
            patch(
                "specweaver.core.flow.handlers.context_assembler.evaluate_and_fetch_skeleton_context",
                return_value=[],
            ),
            patch(
                "specweaver.core.flow.handlers.mcp_assembler.evaluate_and_fetch_mcp_context",
                return_value=None,
            ),
            patch(
                "specweaver.core.flow.handlers.review._build_tool_dispatcher",
                return_value=MagicMock(),
            ),
            patch(
                "specweaver.core.flow.handlers.generation._build_tool_dispatcher",
                return_value=MagicMock(),
            ),
            patch(
                "specweaver.core.flow.handlers.review.ReviewCodeHandler._find_code_path",
                return_value=Path("/tmp/fake_project/code.py"),
            ),
            patch("pathlib.Path.exists", autospec=True, side_effect=mock_exists),
            patch("pathlib.Path.read_text", return_value="mock spec"),
        ):
            result = await handler.execute(step, run_context)

        assert result.status == StepStatus.ERROR
        assert "Unknown render profile 'INVALID'" in result.error_message
        assert not mock_build_base_prompt.called
