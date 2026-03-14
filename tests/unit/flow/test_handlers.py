# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for step handlers — protocol, context, registry, and handler mocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from specweaver.flow.handlers import (
    DraftSpecHandler,
    GenerateCodeHandler,
    GenerateTestsHandler,
    ReviewCodeHandler,
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


# ---------------------------------------------------------------------------
# DraftSpecHandler
# ---------------------------------------------------------------------------


class TestDraftSpecHandler:
    """Tests for the draft+spec handler (HITL parking)."""

    @pytest.mark.asyncio
    async def test_draft_spec_exists_passes(self, tmp_path: Path) -> None:
        """If spec already exists, draft step passes immediately."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Already drafted\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        handler = DraftSpecHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED

    @pytest.mark.asyncio
    async def test_draft_spec_missing_parks(self, tmp_path: Path) -> None:
        """If spec doesn't exist, draft step parks for HITL input."""
        spec = tmp_path / "nonexistent_spec.md"
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        handler = DraftSpecHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.WAITING_FOR_INPUT
        assert "sw draft" in result.output["message"]


# ---------------------------------------------------------------------------
# Registry edge cases
# ---------------------------------------------------------------------------


class TestRegistryEdgeCases:
    """Additional registry tests."""

    def test_custom_handler_override(self) -> None:
        """Custom handler replaces the default for a given action+target."""
        registry = StepHandlerRegistry()
        original = registry.get(StepAction.VALIDATE, StepTarget.SPEC)

        class CustomHandler:
            async def execute(self, step, context):
                pass

        custom = CustomHandler()
        registry.register(StepAction.VALIDATE, StepTarget.SPEC, custom)
        assert registry.get(StepAction.VALIDATE, StepTarget.SPEC) is custom
        assert registry.get(StepAction.VALIDATE, StepTarget.SPEC) is not original


# ---------------------------------------------------------------------------
# ReviewCodeHandler
# ---------------------------------------------------------------------------


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
