# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A rubric a team edits on disk is what the model is actually asked to judge by.

Proves: C-VAL-05 FR-2, C-VAL-05 FR-5

The unit tests prove the loader resolves a file and the seam joins two halves. Neither watches the
result travel: `resolve_review_instructions` could return perfect text that the handler then never
passes to the prompt, and both would still be green.

This runs `ReviewSpecHandler` against a recording adapter and reads what the model received. It is
the only test here that would notice the wiring being dropped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.review import ReviewSpecHandler
from specweaver.core.flow.handlers.run_context import AnalysisContext, ModelAccess, RunContext

if TYPE_CHECKING:
    from pathlib import Path

CRITERIA = "Reject any spec that does not name its rollback plan."


class _RecordingLLM:
    """Captures the prompt and answers with a well-formed verdict."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, messages: Any, config: Any = None) -> Any:
        self.prompts.append(
            "\n".join(
                str(m.get("content", "")) if isinstance(m, dict) else str(m) for m in messages
            )
        )
        return "VERDICT: ACCEPTED\n- Nothing found [confidence: 90]\nLooks fine."


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "spec.md").write_text("# Widget\n\nIt widgets.\n", encoding="utf-8")
    rubrics = tmp_path / ".specweaver" / "rubrics"
    rubrics.mkdir(parents=True)
    (rubrics / "spec_review.md").write_text(
        f"---\nid: spec_review\nversion: 3.0\n---\n{CRITERIA}\n", encoding="utf-8"
    )
    return tmp_path


@pytest.mark.e2e
async def test_the_projects_own_criteria_reach_the_model(project: Path) -> None:
    llm = _RecordingLLM()
    context = RunContext(
        analysis=AnalysisContext(parsers={}),
        model=ModelAccess(llm=llm),
        project_path=project,
        spec_path=project / "spec.md",
    )

    await ReviewSpecHandler().execute(
        PipelineStep(name="review", action=StepAction.REVIEW, target=StepTarget.SPEC, params={}),
        context,
    )

    assert llm.prompts, "the handler never called the model"
    assert CRITERIA in llm.prompts[0]


@pytest.mark.e2e
async def test_the_shipped_criteria_do_not_reach_the_model_once_overridden(project: Path) -> None:
    """The control. If both arrived, the override would be additive rather than a replacement."""
    llm = _RecordingLLM()
    context = RunContext(
        analysis=AnalysisContext(parsers={}),
        model=ModelAccess(llm=llm),
        project_path=project,
        spec_path=project / "spec.md",
    )

    await ReviewSpecHandler().execute(
        PipelineStep(name="review", action=StepAction.REVIEW, target=StepTarget.SPEC, params={}),
        context,
    )

    assert "Single Responsibility" not in llm.prompts[0]


@pytest.mark.e2e
async def test_the_parser_contract_travels_with_the_override(project: Path) -> None:
    """FR-5 at full distance: the response format reaches the model even when a rubric replaced
    every word of the criteria."""
    llm = _RecordingLLM()
    context = RunContext(
        analysis=AnalysisContext(parsers={}),
        model=ModelAccess(llm=llm),
        project_path=project,
        spec_path=project / "spec.md",
    )

    await ReviewSpecHandler().execute(
        PipelineStep(name="review", action=StepAction.REVIEW, target=StepTarget.SPEC, params={}),
        context,
    )

    assert "VERDICT: ACCEPTED" in llm.prompts[0]
