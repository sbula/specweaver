# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A brake stop is reported once, as a stop; a review's reasons reach the run.

Found on real Gemini runs, 2026-10-10: a planned stop printed a full traceback and then its
message again, and a denied review logged "failed: no error message".

| Bucket | Case |
|---|---|
| Happy | a denied review's step carries its summary as the failure reason |
| Boundary | a stop inside a step keeps its message in the step result |
| Degradation | a real crash still logs its traceback |
| Hostile | a stop never logs a traceback or a warning that repeats its message |
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.review import ReviewSpecHandler
from specweaver.core.flow.handlers.run_context import ModelAccess, RunContext
from specweaver.infrastructure.llm.budget import Limit, SpendLimitReachedError
from tests.scripted_llm import FixedRouter

if TYPE_CHECKING:
    from pathlib import Path

_STOP = SpendLimitReachedError(
    Limit("brake.hosted_spend_per_run", "usd", 0.001), 0.0, "limit would be crossed"
)


def _ctx(tmp_path: Path) -> tuple[PipelineStep, RunContext]:
    spec = tmp_path / "s_spec.md"
    spec.write_text("# S\n", encoding="utf-8")
    ctx = RunContext(
        project_path=tmp_path,
        spec_path=spec,
        model=ModelAccess(llm_router=FixedRouter(MagicMock())),
    )
    return PipelineStep(name="rev", action=StepAction.REVIEW, target=StepTarget.SPEC), ctx


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.review.evaluate_and_fetch_mcp_context", return_value=None)
@patch("specweaver.workflows.review.reviewer.Reviewer.review_spec")
async def test_a_stop_is_one_quiet_line_not_a_traceback(
    review, _mcp, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    review.side_effect = _STOP
    step, ctx = _ctx(tmp_path)

    with caplog.at_level(logging.DEBUG):
        result = await ReviewSpecHandler().execute(step, ctx)

    assert result.status is StepStatus.ERROR
    assert "limit would be crossed" in result.error_message
    assert not [r for r in caplog.records if r.exc_info]
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.review.evaluate_and_fetch_mcp_context", return_value=None)
@patch("specweaver.workflows.review.reviewer.Reviewer.review_spec")
async def test_a_real_crash_keeps_its_traceback(
    review, _mcp, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    review.side_effect = RuntimeError("boom")
    step, ctx = _ctx(tmp_path)

    with caplog.at_level(logging.DEBUG):
        await ReviewSpecHandler().execute(step, ctx)

    assert [r for r in caplog.records if r.exc_info]


@pytest.mark.asyncio
@patch("specweaver.core.flow.handlers.review.evaluate_and_fetch_mcp_context", return_value=None)
@patch("specweaver.workflows.review.reviewer.Reviewer.review_spec")
async def test_a_denied_review_says_why(review, _mcp, tmp_path: Path) -> None:
    from specweaver.workflows.review.reviewer import ReviewResult, ReviewVerdict

    review.return_value = ReviewResult(verdict=ReviewVerdict.DENIED, summary="no contract")
    step, ctx = _ctx(tmp_path)

    result = await ReviewSpecHandler().execute(step, ctx)

    assert result.status is StepStatus.FAILED
    assert "no contract" in result.error_message
