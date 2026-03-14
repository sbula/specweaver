# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for step handlers — protocol, context, registry, and handler mocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.flow.handlers import (
    GenerateCodeHandler,
    GenerateTestsHandler,
    ReviewSpecHandler,
    RunContext,
    StepHandlerRegistry,
    ValidateCodeHandler,
    ValidateSpecHandler,
)
from specweaver.flow.models import PipelineStep, StepAction, StepTarget
from specweaver.flow.state import StepStatus

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# RunContext
# ---------------------------------------------------------------------------


class TestRunContext:
    """Tests for RunContext construction."""

    def test_minimal_context(self, tmp_path: Path) -> None:
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "specs" / "test.md",
        )
        assert ctx.project_path == tmp_path
        assert ctx.llm is None
        assert ctx.topology is None
        assert ctx.settings is None

    def test_context_with_output_dir(self, tmp_path: Path) -> None:
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "specs" / "test.md",
            output_dir=tmp_path / "src",
        )
        assert ctx.output_dir == tmp_path / "src"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestStepHandlerRegistry:
    """Tests for the handler registry."""

    def test_default_registry_has_all_handlers(self) -> None:
        registry = StepHandlerRegistry()
        # All 7 valid action+target combos should be registered
        assert registry.get(StepAction.DRAFT, StepTarget.SPEC) is not None
        assert registry.get(StepAction.VALIDATE, StepTarget.SPEC) is not None
        assert registry.get(StepAction.VALIDATE, StepTarget.CODE) is not None
        assert registry.get(StepAction.REVIEW, StepTarget.SPEC) is not None
        assert registry.get(StepAction.REVIEW, StepTarget.CODE) is not None
        assert registry.get(StepAction.GENERATE, StepTarget.CODE) is not None
        assert registry.get(StepAction.GENERATE, StepTarget.TESTS) is not None

    def test_get_unknown_returns_none(self) -> None:
        registry = StepHandlerRegistry()
        # draft+code is not a valid combo
        assert registry.get(StepAction.DRAFT, StepTarget.CODE) is None


# ---------------------------------------------------------------------------
# ValidateSpecHandler
# ---------------------------------------------------------------------------


class TestValidateSpecHandler:
    """Tests for the validate+spec handler."""

    @pytest.mark.asyncio
    async def test_validate_spec_passed(self, tmp_path: Path) -> None:
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test Spec\n\n## 1. Purpose\n\nDoes one thing.\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(name="val", action=StepAction.VALIDATE, target=StepTarget.SPEC)
        handler = ValidateSpecHandler()
        result = await handler.execute(step, ctx)
        assert result.status in (StepStatus.PASSED, StepStatus.FAILED)
        assert "results" in result.output

    @pytest.mark.asyncio
    async def test_validate_spec_missing_file(self, tmp_path: Path) -> None:
        spec = tmp_path / "missing.md"
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(name="val", action=StepAction.VALIDATE, target=StepTarget.SPEC)
        handler = ValidateSpecHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert result.error_message != ""


# ---------------------------------------------------------------------------
# ValidateCodeHandler
# ---------------------------------------------------------------------------


class TestValidateCodeHandler:
    """Tests for the validate+code handler."""

    @pytest.mark.asyncio
    async def test_validate_code_no_code_file(self, tmp_path: Path) -> None:
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            output_dir=tmp_path / "src",
        )
        step = PipelineStep(name="val_code", action=StepAction.VALIDATE, target=StepTarget.CODE)
        handler = ValidateCodeHandler()
        result = await handler.execute(step, ctx)
        # No code to validate → error or skipped
        assert result.status in (StepStatus.ERROR, StepStatus.SKIPPED)


# ---------------------------------------------------------------------------
# ReviewSpecHandler (mocked LLM)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# GenerateCodeHandler (mocked LLM)
# ---------------------------------------------------------------------------


class TestGenerateCodeHandler:
    """Tests for the generate+code handler."""

    @pytest.mark.asyncio
    async def test_generate_code_no_llm(self, tmp_path: Path) -> None:
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            output_dir=tmp_path / "src",
        )
        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "llm" in result.error_message.lower()


# ---------------------------------------------------------------------------
# GenerateTestsHandler (mocked LLM)
# ---------------------------------------------------------------------------


class TestGenerateTestsHandler:
    """Tests for the generate+tests handler."""

    @pytest.mark.asyncio
    async def test_generate_tests_no_llm(self, tmp_path: Path) -> None:
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
            output_dir=tmp_path / "tests",
        )
        step = PipelineStep(name="gen_tests", action=StepAction.GENERATE, target=StepTarget.TESTS)
        handler = GenerateTestsHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "llm" in result.error_message.lower()
