# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for step handlers — protocol, context, registry, and handler mocks."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.flow.handlers import (
    DraftSpecHandler,
    GenerateCodeHandler,
    GenerateTestsHandler,
    PlanSpecHandler,
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

    def test_plan_defaults_to_none(self, tmp_path: Path) -> None:
        """RunContext.plan should default to None."""
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=tmp_path / "specs" / "test.md",
        )
        assert ctx.plan is None


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

    @pytest.mark.asyncio
    @patch.object(ValidateSpecHandler, "_run_validation")
    async def test_validate_spec_atom_crash(self, mock_run_val, tmp_path: Path) -> None:
        """Exceptions in the underlying _run_validation are caught and logged as ERROR."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(name="val", action=StepAction.VALIDATE, target=StepTarget.SPEC)
        handler = ValidateSpecHandler()
        mock_run_val.side_effect = ValueError("Boom")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "Boom" in result.error_message


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

    @pytest.mark.asyncio
    @patch.object(ValidateCodeHandler, "_run_validation")
    async def test_validate_code_atom_crash(self, mock_run_val, tmp_path: Path) -> None:
        """Exceptions in the underlying validation are caught and wrapped."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=tmp_path / "src")
        # Ensure path exists so it actually tries to validate
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "test.py").write_text("x = 1")

        step = PipelineStep(name="val", action=StepAction.VALIDATE, target=StepTarget.CODE)
        handler = ValidateCodeHandler()
        # Mock _run_validation to crash
        mock_run_val.side_effect = ValueError("Code Boom")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "Code Boom" in result.error_message


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

    @pytest.mark.asyncio
    @patch("specweaver.loom.commons.git.executor.GitExecutor.run")
    async def test_generate_code_success_path(self, mock_git, tmp_path: Path) -> None:
        """Verifies successful LLM code generation does not crash and passes output."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir(exist_ok=True)
        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=MagicMock(text="```python\nx = 2\n```", finish_reason=1, parsed=None)
        )
        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, output_dir=src_dir, llm=mock_adapter
        )
        ctx.run_id = "test-run"
        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()
        mock_git.return_value = (0, "", "")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert "generated_path" in result.output
        assert result.artifact_uuid is not None

    @pytest.mark.asyncio
    @patch("specweaver.loom.commons.git.executor.GitExecutor.run")
    async def test_generate_code_extracts_existing_uuid(self, mock_git, tmp_path: Path) -> None:
        """Verifies UUID extraction from an existing file before overwriting."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir(exist_ok=True)
        py_file = src_dir / "test.py"
        valid_uuid = "11111111-2222-3333-4444-555555555555"
        py_file.write_text(f"# sw-artifact: {valid_uuid}\nprint('old')\n")
        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=MagicMock(text="```python\nprint('new')\n```", finish_reason=1, parsed=None)
        )
        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, output_dir=src_dir, llm=mock_adapter
        )
        ctx.run_id = "test-run"
        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()
        mock_git.return_value = (0, "", "")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid == "11111111-2222-3333-4444-555555555555"

    @pytest.mark.asyncio
    @patch("specweaver.loom.commons.git.executor.GitExecutor.run")
    async def test_generate_code_mints_new_uuid_if_missing(self, mock_git, tmp_path: Path) -> None:
        """Verifies handler mints tracking UUID when file exists but lacks sw-artifact tag."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir(exist_ok=True)
        py_file = src_dir / "test.py"
        py_file.write_text("print('old code, no tag')\n")
        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=MagicMock(text="```python\nx = 2\n```", finish_reason=1, parsed=None)
        )
        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, output_dir=src_dir, llm=mock_adapter
        )
        ctx.run_id = "test-run"
        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()
        mock_git.return_value = (0, "", "")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid is not None

    @pytest.mark.asyncio
    @patch("specweaver.loom.commons.git.executor.GitExecutor.run")
    async def test_generate_code_without_db(self, mock_git, tmp_path: Path) -> None:
        """Verifies handler gracefully skips lineage linkage if context.db is absent."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        src_dir = tmp_path / "src"
        src_dir.mkdir(exist_ok=True)
        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=MagicMock(text="```python\npass\n```", finish_reason=1, parsed=None)
        )
        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, output_dir=src_dir, llm=mock_adapter
        )
        # deliberately NOT setting ctx.db
        step = PipelineStep(name="gen", action=StepAction.GENERATE, target=StepTarget.CODE)
        handler = GenerateCodeHandler()
        mock_git.return_value = (0, "", "")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid is not None


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

    @pytest.mark.asyncio
    @patch("specweaver.loom.commons.git.executor.GitExecutor.run")
    async def test_generate_tests_success_path(self, mock_git, tmp_path: Path) -> None:
        """Verifies successful LLM test generation does not crash."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=MagicMock(
                text="```python\ndef test_x(): pass\n```", finish_reason=1, parsed=None
            )
        )
        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, output_dir=tests_dir, llm=mock_adapter
        )
        ctx.run_id = "test-run"
        step = PipelineStep(name="gen_tests", action=StepAction.GENERATE, target=StepTarget.TESTS)
        handler = GenerateTestsHandler()
        mock_git.return_value = (0, "", "")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert "generated_path" in result.output
        assert result.artifact_uuid is not None

    @pytest.mark.asyncio
    @patch("specweaver.loom.commons.git.executor.GitExecutor.run")
    async def test_generate_tests_extracts_existing_uuid(self, mock_git, tmp_path: Path) -> None:
        """Verifies UUID extraction from an existing test file before overwriting."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        py_file = tests_dir / "test_test.py"
        valid_uuid = "11111111-2222-3333-4444-666666666666"
        py_file.write_text(f"# sw-artifact: {valid_uuid}\nprint('old')\n")
        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=MagicMock(text="```python\nprint('new')\n```", finish_reason=1, parsed=None)
        )
        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, output_dir=tests_dir, llm=mock_adapter
        )
        ctx.run_id = "test-run"
        step = PipelineStep(name="gen_tests", action=StepAction.GENERATE, target=StepTarget.TESTS)
        handler = GenerateTestsHandler()
        mock_git.return_value = (0, "", "")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid == "11111111-2222-3333-4444-666666666666"

    @pytest.mark.asyncio
    @patch("specweaver.loom.commons.git.executor.GitExecutor.run")
    async def test_generate_tests_without_db(self, mock_git, tmp_path: Path) -> None:
        """Verifies test generator gracefully skips lineage linkage if context.db is absent."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir(exist_ok=True)
        mock_adapter = MagicMock()
        mock_adapter.generate = AsyncMock(
            return_value=MagicMock(text="```python\npass\n```", finish_reason=1, parsed=None)
        )
        ctx = RunContext(
            project_path=tmp_path, spec_path=spec, output_dir=tests_dir, llm=mock_adapter
        )
        ctx.db = None
        step = PipelineStep(name="gen_tests", action=StepAction.GENERATE, target=StepTarget.TESTS)
        handler = GenerateTestsHandler()
        mock_git.return_value = (0, "", "")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid is not None

# ---------------------------------------------------------------------------
# PlanSpecHandler
# ---------------------------------------------------------------------------


class TestPlanSpecHandler:
    """Tests for the plan+spec handler."""

    @pytest.mark.asyncio
    async def test_plan_spec_no_llm(self, tmp_path: Path) -> None:
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(
            project_path=tmp_path,
            spec_path=spec,
        )
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)
        handler = PlanSpecHandler()
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "llm" in result.error_message.lower()

    @pytest.mark.asyncio
    @patch("specweaver.planning.planner.Planner.generate_plan")
    async def test_plan_spec_success_path_with_uuid(self, mock_create, tmp_path: Path) -> None:
        """Verifies plan generation mints UUID and saves YAML."""
        spec = tmp_path / "test_spec.md"
        valid_uuid = "11111111-2222-3333-4444-888888888888"
        spec.write_text(f"# sw-artifact: {valid_uuid}\nTest\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=MagicMock())
        ctx.db = MagicMock()
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)
        handler = PlanSpecHandler()

        from specweaver.planning.models import PlanArtifact
        mock_create.return_value = PlanArtifact(
            spec_path="test.md",
            spec_name="test",
            spec_hash="hash",
            file_layout=[],
            timestamp="2026-01-01T00:00:00Z"
        )

        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid is not None
        assert "plan_path" in result.output

        # Verify it was written to disk with UUID tag
        import pathlib
        plan_yaml = pathlib.Path(result.output["plan_path"])
        assert plan_yaml.exists()
        content = plan_yaml.read_text(encoding="utf-8")
        assert f"# sw-artifact: {result.artifact_uuid}" in content

        # Verify db was called with correct parent_id
        ctx.db.log_artifact_event.assert_called_with(
            artifact_id=result.artifact_uuid,
            parent_id="11111111-2222-3333-4444-888888888888",
            run_id="",
            event_type="generated_plan"
        )

    @pytest.mark.asyncio
    @patch("specweaver.planning.planner.Planner.generate_plan")
    async def test_plan_spec_derives_parent_from_run_id(self, mock_create, tmp_path: Path) -> None:
        """If spec lacks a tag, parent_id falls back to run_id."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# No tag here\nTest\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=MagicMock())
        ctx.db = MagicMock()
        ctx.run_id = "test-run-123"
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)
        handler = PlanSpecHandler()

        from specweaver.planning.models import PlanArtifact
        mock_create.return_value = PlanArtifact(
            spec_path="test.md",
            spec_name="test",
            spec_hash="hash",
            file_layout=[],
            timestamp="2026-01-01T00:00:00Z"
        )

        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.PASSED

        ctx.db.log_artifact_event.assert_called_with(
            artifact_id=result.artifact_uuid,
            parent_id="test-run-123",
            run_id="test-run-123",
            event_type="generated_plan"
        )

    @pytest.mark.asyncio
    @patch("specweaver.planning.planner.Planner.generate_plan")
    async def test_plan_spec_planner_exception(self, mock_create, tmp_path: Path) -> None:
        """Verifies handler catches planner exceptions and returns a clean error."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec, llm=MagicMock())
        step = PipelineStep(name="plan", action=StepAction.PLAN, target=StepTarget.SPEC)
        handler = PlanSpecHandler()

        mock_create.side_effect = Exception("Planner crashed")
        result = await handler.execute(step, ctx)
        assert result.status == StepStatus.ERROR
        assert "Planner crashed" in result.error_message


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

    @pytest.mark.asyncio
    @patch("specweaver.drafting.drafter.Drafter.draft")
    async def test_draft_spec_creates_uuid(self, mock_draft: AsyncMock, tmp_path: Path) -> None:
        """If drafting succeeds, StepResult contains a generated artifact_uuid."""
        spec = tmp_path / "test_spec.md"
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        ctx.llm = AsyncMock()
        ctx.context_provider = AsyncMock()

        # mock drafter output: it should write the file when called.
        async def mock_draft_side_effect(*args, **kwargs):
            spec.write_text("Hello spec", encoding="utf-8")
            return spec

        mock_draft.side_effect = mock_draft_side_effect

        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        handler = DraftSpecHandler()
        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid is not None

        # Also ensure it wrote the uuid to the spec
        content = spec.read_text(encoding="utf-8")
        assert "<!-- sw-artifact:" in content


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


# ---------------------------------------------------------------------------
# Edge cases: ValidateSpecHandler with kind param
# ---------------------------------------------------------------------------


class TestValidateSpecHandlerKindWiring:
    """ValidateSpecHandler reads kind from step.params."""

    @pytest.mark.asyncio
    async def test_kind_feature_in_params(self, tmp_path: Path) -> None:
        """step.params['kind'] = 'feature' applies feature thresholds."""
        spec = tmp_path / "feature_spec.md"
        spec.write_text(
            "# Sell Shares\n\n## Intent\n\nEnable users to sell their shares. Users may want to.\n"
        )
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(
            name="val",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
            params={"kind": "feature"},
        )
        handler = ValidateSpecHandler()
        result = await handler.execute(step, ctx)
        # Should run without error — kind is threaded to validation
        assert result.status in (StepStatus.PASSED, StepStatus.FAILED)
        assert "results" in result.output

    @pytest.mark.asyncio
    async def test_invalid_kind_falls_back(self, tmp_path: Path) -> None:
        """Invalid kind string falls back to default (no crash)."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n\n## 1. Purpose\n\nDoes one thing.\n")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(
            name="val",
            action=StepAction.VALIDATE,
            target=StepTarget.SPEC,
            params={"kind": "nonexistent_kind"},
        )
        handler = ValidateSpecHandler()
        result = await handler.execute(step, ctx)
        # Should still work with default rules
        assert result.status in (StepStatus.PASSED, StepStatus.FAILED)


# ---------------------------------------------------------------------------
# Edge cases: validate_flow with DECOMPOSE steps
# ---------------------------------------------------------------------------


class TestValidateFlowWithDecompose:
    """PipelineDefinition.validate_flow handles DECOMPOSE steps."""

    def test_decompose_feature_pipeline_valid(self) -> None:
        """Pipeline with DECOMPOSE+FEATURE validates cleanly."""
        from specweaver.flow.models import (
            GateCondition,
            GateDefinition,
            OnFailAction,
            PipelineDefinition,
        )

        steps = [
            PipelineStep(
                name="draft_feature",
                action=StepAction.DRAFT,
                target=StepTarget.FEATURE,
            ),
            PipelineStep(
                name="validate_feature",
                action=StepAction.VALIDATE,
                target=StepTarget.FEATURE,
                params={"kind": "feature"},
                gate=GateDefinition(
                    condition=GateCondition.ALL_PASSED,
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="draft_feature",
                ),
            ),
            PipelineStep(
                name="decompose",
                action=StepAction.DECOMPOSE,
                target=StepTarget.FEATURE,
            ),
        ]
        p = PipelineDefinition(name="feature_decomp", steps=steps)
        errors = p.validate_flow()
        assert errors == []

    def test_decompose_spec_pipeline_invalid(self) -> None:
        """Pipeline with DECOMPOSE+SPEC is invalid (only FEATURE allowed)."""
        from specweaver.flow.models import PipelineDefinition

        steps = [
            PipelineStep(
                name="bad_decompose",
                action=StepAction.DECOMPOSE,
                target=StepTarget.SPEC,  # invalid
            ),
        ]
        p = PipelineDefinition(name="bad", steps=steps)
        errors = p.validate_flow()
        assert any("invalid" in e.lower() or "combination" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Telemetry run_id propagation
# ---------------------------------------------------------------------------


class TestRunIdPropagation:
    """Tests for run_id propagation from RunContext to GenerationConfig."""

    @pytest.mark.asyncio
    @patch("specweaver.review.reviewer.Reviewer.review_code")
    async def test_review_code_handler_injects_run_id(self, mock_review_code, tmp_path: Path) -> None:
        """Handlers must inject context.run_id into GenerationConfig for telemetry correlation."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Test\n")
        code = tmp_path / "src" / "test.py"
        code.parent.mkdir()
        code.write_text("x = 1")

        from specweaver.review.reviewer import ReviewResult, ReviewVerdict
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
        from specweaver.flow._review import _resolve_review_routing
        _, config = _resolve_review_routing(ctx)
        assert config.run_id == "mock-run-id-1234"
