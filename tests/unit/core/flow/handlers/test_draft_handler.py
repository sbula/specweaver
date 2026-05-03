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
