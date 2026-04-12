# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for flow handlers — guard clauses and RunContext config field.

Covers gap analysis items:
- #18: RunContext.config field defaults to None
- #19: ReviewCodeHandler — no LLM returns error
- #20: ReviewCodeHandler — no code file returns error
- #21: ReviewSpecHandler — no LLM returns error
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.core.flow._base import RunContext
from specweaver.core.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.state import StepStatus

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# RunContext.config field (gap #18)
# ---------------------------------------------------------------------------


class TestRunContextConfigField:
    """RunContext.config attribute defaults to None."""

    def test_config_defaults_to_none(self, tmp_path: Path):
        """RunContext without config= kwarg → config is None."""
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
        )
        assert ctx.config is None

    def test_config_accepts_arbitrary_value(self, tmp_path: Path):
        """RunContext.config can hold any object (Any type)."""
        sentinel = object()
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            config=sentinel,
        )
        assert ctx.config is sentinel

    def test_llm_router_defaults_to_none(self, tmp_path: Path):
        """RunContext without llm_router= kwarg → llm_router is None (backward-compat)."""
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
        )
        assert ctx.llm_router is None

    def test_llm_router_accepts_arbitrary_value(self, tmp_path: Path):
        """RunContext.llm_router can hold any object (ModelRouter instance)."""
        sentinel = object()
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "spec.md",
            llm_router=sentinel,
        )
        assert ctx.llm_router is sentinel


# ---------------------------------------------------------------------------
# ReviewSpecHandler guard clause (gap #21)
# ---------------------------------------------------------------------------


class TestReviewSpecHandlerGuards:
    """ReviewSpecHandler returns error when LLM is not configured."""

    @pytest.mark.asyncio()
    async def test_no_llm_returns_error(self, tmp_path: Path):
        """ReviewSpecHandler with llm=None → error result."""
        from specweaver.core.flow._review import ReviewSpecHandler

        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test spec\n", encoding="utf-8")

        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            llm=None,
        )
        step = PipelineStep(
            name="review_spec",
            action=StepAction.REVIEW,
            target=StepTarget.SPEC,
        )

        handler = ReviewSpecHandler()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.ERROR
        assert "LLM adapter required" in result.error_message


# ---------------------------------------------------------------------------
# ReviewCodeHandler guard clauses (gap #19, #20)
# ---------------------------------------------------------------------------


class TestReviewCodeHandlerGuards:
    """ReviewCodeHandler returns error when LLM or code file is missing."""

    @pytest.mark.asyncio()
    async def test_no_llm_returns_error(self, tmp_path: Path):
        """ReviewCodeHandler with llm=None → error result."""
        from specweaver.core.flow._review import ReviewCodeHandler

        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test spec\n", encoding="utf-8")

        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            llm=None,
        )
        step = PipelineStep(
            name="review_code",
            action=StepAction.REVIEW,
            target=StepTarget.CODE,
        )

        handler = ReviewCodeHandler()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.ERROR
        assert "LLM adapter required" in result.error_message

    @pytest.mark.asyncio()
    async def test_no_code_file_returns_error(self, tmp_path: Path):
        """ReviewCodeHandler with no .py files in output_dir → error result."""
        from unittest.mock import MagicMock

        from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings
        from specweaver.core.flow._review import ReviewCodeHandler

        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test spec\n", encoding="utf-8")

        # output_dir exists but has no .py files
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        mock_llm = MagicMock()
        mock_config = SpecWeaverSettings(
            llm=LLMSettings(model="mock-model"),
        )

        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            llm=mock_llm,
            output_dir=output_dir,
            config=mock_config,
        )
        step = PipelineStep(
            name="review_code",
            action=StepAction.REVIEW,
            target=StepTarget.CODE,
        )

        handler = ReviewCodeHandler()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.ERROR
        assert "No code file found" in result.error_message
