# mypy: ignore-errors
from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.draft import DraftSpecHandler

if TYPE_CHECKING:
    from pathlib import Path
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
    @patch("specweaver.core.flow.store.FlowRepository")
    @patch("specweaver.workflows.drafting.drafter.Drafter.draft")
    async def test_draft_spec_creates_uuid(
        self, mock_draft: AsyncMock, mock_repo_class, tmp_path: Path
    ) -> None:
        """If drafting succeeds, StepResult contains a generated artifact_uuid."""
        spec = tmp_path / "test_spec.md"
        ctx = RunContext(project_path=tmp_path, spec_path=spec, db=MagicMock())
        ctx.llm = AsyncMock()
        ctx.context_provider = AsyncMock()

        mock_repo = MagicMock()
        mock_repo.log_artifact_event = AsyncMock()
        mock_repo_class.return_value = mock_repo

        # mock drafter output: it should write the file when called.
        async def mock_draft_side_effect(*args, **kwargs):
            spec.write_text("Hello spec", encoding="utf-8")
            return spec

        mock_draft.side_effect = mock_draft_side_effect

        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        handler = DraftSpecHandler()

        ctx.run_id = "test-run"

        result = await handler.execute(step, ctx)

        assert result.status == StepStatus.PASSED
        assert result.artifact_uuid is not None

        # Also ensure it wrote the uuid to the spec
        content = spec.read_text(encoding="utf-8")
        assert "<!-- sw-artifact:" in content

        mock_repo.log_artifact_event.assert_called_with(
            artifact_id=result.artifact_uuid,
            parent_id=None,
            run_id="test-run",
            event_type="drafted_spec",
            model_id="unknown",
        )


# ---------------------------------------------------------------------------


class TestDraftSpecHandlerFeedbackLoop:
    """INT-US-02 SF-01 (AD-6a): the loop_back rejection loop must be REAL.

    Seam-first contract tests: feedback consumed exactly once; re-draft happens even when
    the spec exists; headless rejection parks WITH the findings; malformed feedback is
    treated as absent. Deliberately no assertions on Drafter prompt internals (the engine
    is a D-INTL-07 supersession target)."""

    def _feedback(self) -> dict:
        return {
            "draft": {
                "from_step": "review_spec",
                "findings": {"verdict": "rejected", "findings": ["Purpose section vague"]},
            }
        }

    @pytest.mark.asyncio
    @patch("specweaver.core.flow.store.FlowRepository")
    @patch("specweaver.workflows.drafting.drafter.Drafter.draft")
    async def test_feedback_with_provider_redrafts_despite_existing_spec(
        self, mock_draft: AsyncMock, mock_repo_class, tmp_path: Path
    ) -> None:
        """[Happy] reviewer feedback + provider + llm -> re-draft runs even though the
        spec file exists (the old dead-loop skip must NOT fire), and feedback is consumed."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# v1 draft\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec, db=MagicMock())
        ctx.llm = AsyncMock()
        ctx.context_provider = AsyncMock()
        ctx.run_id = "test-run"
        ctx.feedback = self._feedback()

        mock_repo = MagicMock()
        mock_repo.log_artifact_event = AsyncMock()
        mock_repo_class.return_value = mock_repo

        async def redraft(*args, **kwargs):
            spec.write_text("# v2 draft\n", encoding="utf-8")
            return spec

        mock_draft.side_effect = redraft

        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        result = await DraftSpecHandler().execute(step, ctx)

        assert result.status == StepStatus.PASSED
        mock_draft.assert_awaited()  # the re-draft actually ran
        assert "v2" in spec.read_text(encoding="utf-8")
        assert "draft" not in ctx.feedback  # consumed exactly once

    @pytest.mark.asyncio
    async def test_no_feedback_existing_spec_skips_byte_identical(self, tmp_path: Path) -> None:
        """[Boundary] no feedback + existing spec -> the historic skip path, unchanged."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Already drafted\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        result = await DraftSpecHandler().execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert "already exists" in result.output["message"]

    @pytest.mark.asyncio
    async def test_feedback_without_provider_parks_with_findings(self, tmp_path: Path) -> None:
        """[Degradation] reviewer feedback but headless (no provider/llm) -> park, and the
        findings travel IN the park output so the resuming human sees them."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# v1 draft\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        ctx.feedback = self._feedback()

        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        result = await DraftSpecHandler().execute(step, ctx)

        assert result.status == StepStatus.WAITING_FOR_INPUT
        assert "Purpose section vague" in str(result.output)
        assert "draft" not in ctx.feedback  # still consumed (no sticky re-park loops)

    @pytest.mark.asyncio
    async def test_malformed_feedback_treated_as_absent(self, tmp_path: Path) -> None:
        """[Hostile] feedback entry without a findings key / wrong type -> behaves exactly
        like no-feedback (skip on existing spec), never crashes."""
        spec = tmp_path / "test_spec.md"
        spec.write_text("# Already drafted\n", encoding="utf-8")
        ctx = RunContext(project_path=tmp_path, spec_path=spec)
        ctx.feedback = {"draft": "not-a-dict"}

        step = PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)
        result = await DraftSpecHandler().execute(step, ctx)
        assert result.status == StepStatus.PASSED
        assert "already exists" in result.output["message"]


class TestPopFeedbackDirect:
    """G2: _pop_feedback branch coverage, direct (each malformed variant -> None, popped)."""

    def _step(self):
        return PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC)

    def _ctx(self, tmp_path, feedback):
        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "s_spec.md")
        ctx.feedback = feedback
        return ctx

    def test_entry_without_findings_key_returns_none_and_pops(self, tmp_path) -> None:
        ctx = self._ctx(tmp_path, {"draft": {"from_step": "review_spec"}})
        assert DraftSpecHandler._pop_feedback(self._step(), ctx) is None
        assert "draft" not in ctx.feedback  # popped even though malformed

    def test_findings_non_dict_returns_none_and_pops(self, tmp_path) -> None:
        ctx = self._ctx(tmp_path, {"draft": {"findings": ["list", "not", "dict"]}})
        assert DraftSpecHandler._pop_feedback(self._step(), ctx) is None
        assert "draft" not in ctx.feedback

    def test_empty_feedback_dict_returns_none(self, tmp_path) -> None:
        ctx = self._ctx(tmp_path, {})
        assert DraftSpecHandler._pop_feedback(self._step(), ctx) is None

    def test_other_steps_feedback_untouched(self, tmp_path) -> None:
        ctx = self._ctx(tmp_path, {"generate_code": {"findings": {"x": 1}}})
        assert DraftSpecHandler._pop_feedback(self._step(), ctx) is None
        assert "generate_code" in ctx.feedback  # only THIS step's entry is consumed
