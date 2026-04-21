from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.review import ReviewCodeHandler, ReviewSpecHandler


class TestReviewSpecHandler:
    """Tests for the review+spec handler."""

    @pytest.mark.asyncio
    async def test_review_spec_no_llm(self, tmp_path: Path) -> None:
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)  # no LLM
        step = PipelineStep(name="rev", action=StepAction.REVIEW, target=StepTarget.SPEC)
        handler = ReviewSpecHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "llm" in result.error_message.lower()

    @pytest.mark.asyncio
    @patch("specweaver.workflows.review.reviewer.Reviewer.review_spec")
    @patch("specweaver.core.flow.handlers.review.evaluate_and_fetch_mcp_context")
    async def test_review_spec_extracts_mcp_context(
        self, mock_fetch_mcp, mock_review_spec, tmp_path: Path
    ) -> None:
        """Verifies MCP environment context is fetched and passed to Reviewer."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=MagicMock())
        ctx.run_id = "test-run"

        step = PipelineStep(name="rev", action=StepAction.REVIEW, target=StepTarget.SPEC)
        handler = ReviewSpecHandler()

        from specweaver.workflows.review.reviewer import ReviewResult, ReviewVerdict
        mock_review_spec.return_value = ReviewResult(
            verdict=ReviewVerdict.ACCEPTED,
            remarks="LGTM",
            findings=[],
        )
        mock_fetch_mcp.return_value = "mcp://mock:\n  |\n    mock"

        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.PASSED
        mock_review_spec.assert_called_once()
        mock_fetch_mcp.assert_called_once_with(ctx)

        # Verify kwargs
        call_kwargs = mock_review_spec.call_args.kwargs
        assert call_kwargs.get("environment_context") == "mcp://mock:\n  |\n    mock"

class TestReviewCodeHandler:
    """Tests for the review+code handler."""

    @pytest.mark.asyncio
    async def test_review_code_no_llm(self, tmp_path: Path) -> None:
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(name="rev_code", action=StepAction.REVIEW, target=StepTarget.CODE)
        handler = ReviewCodeHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "llm" in result.error_message.lower()

    @pytest.mark.asyncio
    @patch("specweaver.workflows.review.reviewer.Reviewer.review_code")
    @patch("specweaver.core.flow.handlers.review.evaluate_and_fetch_mcp_context")
    async def test_review_code_extracts_mcp_context(
        self, mock_fetch_mcp, mock_review_code, tmp_path: Path
    ) -> None:
        """Verifies MCP environment context is fetched and passed to Reviewer for code evaluation."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=MagicMock(), output_dir=tmp_path)
        ctx.run_id = "test-run"
        (tmp_path / "test.py").write_text("x = 1")

        step = PipelineStep(name="rev_code", action=StepAction.REVIEW, target=StepTarget.CODE)
        handler = ReviewCodeHandler()

        from specweaver.workflows.review.reviewer import ReviewResult, ReviewVerdict
        mock_review_code.return_value = ReviewResult(
            verdict=ReviewVerdict.ACCEPTED,
            remarks="LGTM",
            findings=[],
        )
        mock_fetch_mcp.return_value = "mcp://mock:\n  |\n    mock_code"

        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.PASSED
        mock_review_code.assert_called_once()
        mock_fetch_mcp.assert_called_once_with(ctx)

        # Verify kwargs
        call_kwargs = mock_review_code.call_args.kwargs
        assert call_kwargs.get("environment_context") == "mcp://mock:\n  |\n    mock_code"
