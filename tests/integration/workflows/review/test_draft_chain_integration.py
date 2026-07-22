# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""INT-US-02 SF-01 T4: the draft -> validate -> review loop, run for REAL.

Real PipelineRunner + real GateEvaluator (loop_back + inject_feedback) + the real
feedback-aware DraftSpecHandler. Stubbed at the LLM edges only: Drafter.draft writes
deterministic spec files; ValidateSpecHandler passes; ReviewSpecHandler emits a scripted
verdict sequence. Proves the rejection loop is ALIVE (the shipped one was dead) and bounded.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext, _now_iso
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.workflows.review.interfaces.cli import _build_draft_pipeline

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _passed(output: dict) -> StepResult:
    return StepResult(
        status=StepStatus.PASSED, output=output, started_at=_now_iso(), completed_at=_now_iso()
    )


def _failed(output: dict) -> StepResult:
    return StepResult(
        status=StepStatus.FAILED,
        output=output,
        error_message="review rejected",
        started_at=_now_iso(),
        completed_at=_now_iso(),
    )


def _review_sequence(*verdicts: str):
    """Scripted ReviewSpecHandler.execute: yields verdicts in order."""
    seq = list(verdicts)

    async def _execute(self, step, context):
        verdict = seq.pop(0)
        output = {"verdict": verdict, "findings": [] if verdict == "accepted" else ["Purpose vague"]}
        return _passed(output) if verdict == "accepted" else _failed(output)

    return _execute


async def _validate_ok(self, step, context):
    return _passed({"total": 12, "passed": 12, "results": []})


def _make_context(tmp_path: Path) -> RunContext:
    spec = tmp_path / "specs" / "greeter_spec.md"
    spec.parent.mkdir(parents=True, exist_ok=True)
    config = MagicMock()
    config.llm.model = "test-model"
    config.llm.temperature = 0.2
    config.llm.max_output_tokens = 4096
    ctx = RunContext(project_path=tmp_path, spec_path=spec, config=config)
    ctx.llm = AsyncMock()
    ctx.context_provider = AsyncMock()
    return ctx


def _drafter_writer(spec, versions: list[int]):
    """Drafter.draft stub: writes a versioned spec each call (proves regeneration)."""

    async def _draft(*args, **kwargs):
        versions.append(len(versions) + 1)
        spec.write_text(f"# spec v{len(versions)}\n", encoding="utf-8")
        return spec

    return _draft


def _run(ctx: RunContext):
    pipeline = _build_draft_pipeline("greeter")
    return asyncio.run(PipelineRunner(pipeline, ctx, registry=StepHandlerRegistry()).run())


class TestDraftChainRealLoop:
    @patch("specweaver.core.flow.handlers.validation.ValidateSpecHandler.execute", new=_validate_ok)
    @patch("specweaver.workflows.drafting.drafter.Drafter.draft")
    def test_accept_first_pass(self, mock_draft, tmp_path: Path) -> None:
        """[Happy] draft -> validate -> review accepted in one pass; one draft only."""
        ctx = _make_context(tmp_path)
        versions: list[int] = []
        mock_draft.side_effect = _drafter_writer(ctx.spec_path, versions)

        with patch(
            "specweaver.core.flow.handlers.review.ReviewSpecHandler.execute",
            new=_review_sequence("accepted"),
        ):
            run_state = _run(ctx)

        assert run_state.status == RunStatus.COMPLETED, run_state
        assert versions == [1]

    @patch("specweaver.core.flow.handlers.validation.ValidateSpecHandler.execute", new=_validate_ok)
    @patch("specweaver.workflows.drafting.drafter.Drafter.draft")
    def test_reject_then_accept_loops_back_and_redrafts(self, mock_draft, tmp_path: Path) -> None:
        """[Happy/loop — THE contract] first review rejects -> loop_back re-enters draft,
        the re-draft actually RUNS (v2 written — the old dead-loop skip is gone), then the
        second review accepts."""
        ctx = _make_context(tmp_path)
        versions: list[int] = []
        mock_draft.side_effect = _drafter_writer(ctx.spec_path, versions)

        with patch(
            "specweaver.core.flow.handlers.review.ReviewSpecHandler.execute",
            new=_review_sequence("rejected", "accepted"),
        ):
            run_state = _run(ctx)

        assert run_state.status == RunStatus.COMPLETED, run_state
        assert versions == [1, 2]  # re-draft genuinely ran
        assert "v2" in ctx.spec_path.read_text(encoding="utf-8")
        assert ctx.feedback == {} or "draft_spec" not in ctx.feedback  # consumed

    @patch("specweaver.core.flow.handlers.validation.ValidateSpecHandler.execute", new=_validate_ok)
    @patch("specweaver.workflows.drafting.drafter.Drafter.draft")
    def test_reject_forever_exhausts_bounded_retries(self, mock_draft, tmp_path: Path) -> None:
        """[Degradation] review rejects every time -> the loop is BOUNDED (max_retries=2):
        exactly 3 drafts (initial + 2 re-drafts), then the run fails."""
        ctx = _make_context(tmp_path)
        versions: list[int] = []
        mock_draft.side_effect = _drafter_writer(ctx.spec_path, versions)

        with patch(
            "specweaver.core.flow.handlers.review.ReviewSpecHandler.execute",
            new=_review_sequence("rejected", "rejected", "rejected", "rejected"),
        ):
            run_state = _run(ctx)

        assert run_state.status != RunStatus.COMPLETED
        assert versions == [1, 2, 3]  # bounded: no unbounded LLM spend

    @patch("specweaver.core.flow.handlers.validation.ValidateSpecHandler.execute", new=_validate_ok)
    @patch("specweaver.workflows.drafting.drafter.Drafter.draft")
    def test_provider_raises_mid_redraft_fails_loud(self, mock_draft, tmp_path: Path) -> None:
        """[Hostile] the drafter blows up during the re-draft -> the step FAILS and the run
        fails — never a silent green."""
        ctx = _make_context(tmp_path)
        calls: list[int] = []

        async def _draft_then_boom(*args, **kwargs):
            calls.append(1)
            if len(calls) == 1:
                ctx.spec_path.write_text("# spec v1\n", encoding="utf-8")
                return ctx.spec_path
            raise RuntimeError("terminal lost")

        mock_draft.side_effect = _draft_then_boom

        with patch(
            "specweaver.core.flow.handlers.review.ReviewSpecHandler.execute",
            new=_review_sequence("rejected", "accepted"),
        ):
            run_state = _run(ctx)

        assert run_state.status != RunStatus.COMPLETED
        assert len(calls) == 2  # the failure happened in the re-draft, and was surfaced


def _validate_sequence(*outcomes: bool):
    """Scripted ValidateSpecHandler.execute: pass/fail per call (C-B corner)."""
    seq = list(outcomes)

    async def _execute(self, step, context):
        ok = seq.pop(0)
        output = {"total": 12, "passed": 12 if ok else 11, "results": []}
        return _passed(output) if ok else _failed(output)

    return _execute


class TestRedraftRevalidation:
    @patch("specweaver.workflows.drafting.drafter.Drafter.draft")
    def test_redrafted_spec_failing_validation_aborts_midloop(
        self, mock_draft, tmp_path: Path
    ) -> None:
        """[C-B corner] v1 validates but review rejects; the re-drafted v2 FAILS validation
        -> the abort gate fires mid-loop. Proves regenerated content is re-validated and the
        loop cannot smuggle an invalid spec through to review."""
        ctx = _make_context(tmp_path)
        versions: list[int] = []
        mock_draft.side_effect = _drafter_writer(ctx.spec_path, versions)

        with (
            patch(
                "specweaver.core.flow.handlers.validation.ValidateSpecHandler.execute",
                new=_validate_sequence(True, False),
            ),
            patch(
                "specweaver.core.flow.handlers.review.ReviewSpecHandler.execute",
                new=_review_sequence("rejected", "accepted"),
            ),
        ):
            run_state = _run(ctx)

        assert run_state.status != RunStatus.COMPLETED  # aborted on v2 validation
        assert versions == [1, 2]  # re-draft ran, then validation stopped the run
        records = {r.step_name: r for r in run_state.step_records}
        assert records["validate_spec"].status == StepStatus.FAILED
