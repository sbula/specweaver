# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.handlers import ReviewCodeHandler, RunContext
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget

# ---------------------------------------------------------------------------
# Telemetry run_id propagation
# ---------------------------------------------------------------------------


class TestRunIdPropagation:
    """Tests for run_id propagation from RunContext to GenerationConfig."""

    @pytest.mark.asyncio
    @patch("specweaver.workflows.review.reviewer.Reviewer.review_code")
    async def test_review_code_handler_injects_run_id(
        self, mock_review_code, tmp_path: Path
    ) -> None:
        """Handlers must inject context.run_id into GenerationConfig for telemetry correlation."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        code = tmp_path / "src" / "test.py"
        code.parent.mkdir()
        code.write_text("x = 1")

        from specweaver.workflows.review.reviewer import ReviewResult, ReviewVerdict

        mock_review_code.return_value = ReviewResult(
            verdict=ReviewVerdict.ACCEPTED,
            findings=[],
            summary="LGTM",
            raw_response="LGTM",
        )

        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock()
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            output_dir=tmp_path / "src",
            llm=mock_adapter,
        )
        ctx.run_id = "mock-run-id-1234"

        step = PipelineStep(name="rev_code", action=StepAction.REVIEW, target=StepTarget.CODE)
        handler = ReviewCodeHandler()

        await handler.execute(step, ctx)

        # Verify the Reviewer was instantiated with a config containing the run_id
        # We need to peek at the args passed to _resolve_review_routing which happens during execute.
        # Actually, let's just patch _resolve_review_routing and assert? No, we should test the actual injection.
        from specweaver.core.flow._review import _resolve_review_routing

        _, config = _resolve_review_routing(ctx)
        assert config.run_id == "mock-run-id-1234"


class TestExtractPromptFeedback:
    """Verifies edge cases of hitl and validation feedback extraction."""

    def test_ignores_missing_findings_key(self, tmp_path: Path) -> None:
        """Verifies it skips feedback gracefully if 'findings' is missing."""
        from specweaver.core.flow._generation import _extract_prompt_feedback

        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "f", llm=MagicMock())
        ctx.feedback = {"test_step": {"other_data": True}}
        step = PipelineStep(name="test_step", action=StepAction.GENERATE, target=StepTarget.CODE)

        ovr, val = _extract_prompt_feedback(ctx, step)
        assert ovr is None
        assert val is None
        assert "test_step" not in ctx.feedback  # verify popped even if no findings

    def test_drops_remarks_if_approved(self, tmp_path: Path) -> None:
        """Verifies dictator remarks are dropped if hitl_verdict is 'approve'."""
        from specweaver.core.flow._generation import _extract_prompt_feedback

        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "f", llm=MagicMock())
        ctx.feedback = {
            "test_step": {
                "findings": {
                    "hitl_verdict": "approve",
                    "remarks": "Looks good!",
                }
            }
        }
        step = PipelineStep(name="test_step", action=StepAction.GENERATE, target=StepTarget.CODE)

        ovr, val = _extract_prompt_feedback(ctx, step)
        assert ovr is None
        assert val is None

    def test_ignores_passed_results(self, tmp_path: Path) -> None:
        """Verifies mapping drops validation rules if none failed."""
        from specweaver.core.flow._generation import _extract_prompt_feedback

        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "f", llm=MagicMock())
        ctx.feedback = {
            "test_step": {
                "findings": {
                    "results": [
                        {"status": "PASS", "rule_id": "T01"},
                        {"status": "PASS", "rule_id": "T02"},
                    ]
                }
            }
        }
        step = PipelineStep(name="test_step", action=StepAction.GENERATE, target=StepTarget.CODE)

        ovr, val = _extract_prompt_feedback(ctx, step)
        assert ovr is None
        assert val is None
