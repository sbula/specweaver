# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — Artifact Lineage hookups and lifecycle survivability.

These tests ensure that the artifact UUID tags physically injected by handlers
are properly extracted, propagated down the pipeline, logged to the DB,
and successfully survive pipeline Loop-Back validations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.draft import DraftSpecHandler
from specweaver.core.flow.handlers.generation import GenerateCodeHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import (
    GateCondition,
    GateDefinition,
    GateType,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepStatus
from specweaver.core.flow.engine.store import StateStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeFailingReviewHandler:
    """A review handler that fails once, then passes, triggering one loop-back."""

    def __init__(self):
        self.calls = 0

    async def execute(self, step, context):
        from specweaver.core.flow.engine.state import StepResult
        from specweaver.core.flow.handlers.base import _now_iso

        self.calls += 1
        return StepResult(
            status=StepStatus.FAILED if self.calls == 1 else StepStatus.PASSED,
            output={"failures": 1} if self.calls == 1 else {},
            started_at=_now_iso(),
            completed_at=_now_iso(),
        )


@pytest.fixture
def lineage_db(tmp_path: Path) -> Database:
    """Returns a real DB configured at tmp_path."""
    db_path = tmp_path / "specweaver.db"
    db = Database(db_path)
    return db


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("specweaver.workflows.drafting.drafter.Drafter.draft")
@patch("specweaver.core.loom.commons.git.executor.GitExecutor.run")
async def test_lineage_tracking_flow_database(
    mock_git, mock_draft, tmp_path: Path, lineage_db: Database
) -> None:
    """Verify Draft -> Generate Code pipeline writes correct parent-child DB logs."""

    spec = tmp_path / "specs" / "feature.md"
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    spec.parent.mkdir(parents=True, exist_ok=True)

    # Drafter makes a tagged spec
    async def _mock_draft(*args, **kwargs):
        spec.write_text(
            "# sw-artifact: 11111111-2222-3333-4444-555555555555\nContent", encoding="utf-8"
        )
        return spec

    mock_draft.side_effect = _mock_draft

    mock_llm = MagicMock()

    async def _mock_llm_generate(messages, config):
        # find the tag in the prompt
        tag = ""
        for msg in messages:
            if "# sw-artifact:" in msg.content:
                for line in msg.content.split("\n"):
                    if "# sw-artifact:" in line:
                        tag = line.split("'")[1] if "'" in line else line
                        break
        return MagicMock(text=f"```python\n{tag}\nprint(1)\n```")

    mock_llm.generate = AsyncMock(side_effect=_mock_llm_generate)

    ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=src_dir, llm=mock_llm)
    ctx.context_provider = AsyncMock()
    ctx.db = lineage_db
    store = StateStore(tmp_path / ".specweaver_state.db")

    pipeline = PipelineDefinition(
        name="test_flow",
        steps=[
            PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(name="gen_code", action=StepAction.GENERATE, target=StepTarget.CODE),
        ],
    )

    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, DraftSpecHandler())
    registry.register(StepAction.GENERATE, StepTarget.CODE, GenerateCodeHandler())

    mock_git.return_value = (0, "", "")

    runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
    run = await runner.run()

    assert run.status == RunStatus.COMPLETED

    # Verify DB contains the events
    with lineage_db.connect() as conn:
        rows = conn.execute(
            "SELECT artifact_id, parent_id, event_type FROM artifact_events ORDER BY timestamp ASC"
        ).fetchall()

        # We expect two hits: draft, then code gen
        assert len(rows) == 2

        draft_row = rows[0]
        assert draft_row["artifact_id"] == "11111111-2222-3333-4444-555555555555"
        assert draft_row["parent_id"] is None
        assert draft_row["event_type"] == "drafted_spec"

        code_row = rows[1]
        assert code_row["artifact_id"] != "11111111-2222-3333-4444-555555555555"
        assert code_row["parent_id"] == "11111111-2222-3333-4444-555555555555"
        assert code_row["event_type"] == "generated_code"


@pytest.mark.asyncio
@patch("specweaver.core.loom.commons.git.executor.GitExecutor.run")
async def test_loop_back_preservation(mock_git, tmp_path: Path, lineage_db: Database) -> None:
    """Verify Code UUID is preserved when pipeline loops back and regenerates code."""
    spec = tmp_path / "specs" / "feature.md"
    src_dir = tmp_path / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text(
        "# sw-artifact: 11111111-2222-3333-4444-555555555555\nContent", encoding="utf-8"
    )

    mock_llm = MagicMock()

    async def _mock_llm_generate(messages, config):
        # find the tag in the prompt
        tag = ""
        for msg in messages:
            if "# sw-artifact:" in msg.content:
                for line in msg.content.split("\n"):
                    if "# sw-artifact:" in line:
                        tag = line.split("'")[1] if "'" in line else line
                        break
        return MagicMock(text=f"```python\n{tag}\nprint(1)\n```")

    mock_llm.generate = AsyncMock(side_effect=_mock_llm_generate)

    ctx = RunContext(project_path=tmp_path, spec_path=spec, output_dir=src_dir, llm=mock_llm)
    ctx.context_provider = AsyncMock()
    ctx.db = lineage_db
    store = StateStore(tmp_path / ".specweaver_state.db")

    pipeline = PipelineDefinition(
        name="loop_flow",
        steps=[
            PipelineStep(name="gen_code", action=StepAction.GENERATE, target=StepTarget.CODE),
            PipelineStep(
                name="rev_code",
                action=StepAction.REVIEW,
                target=StepTarget.CODE,
                gate=GateDefinition(
                    type=GateType.AUTO,
                    condition=GateCondition.ALL_PASSED,
                    on_fail=OnFailAction.LOOP_BACK,
                    loop_target="gen_code",
                    max_retries=2,
                ),
            ),
        ],
    )

    registry = StepHandlerRegistry()
    registry.register(StepAction.GENERATE, StepTarget.CODE, GenerateCodeHandler())
    registry.register(StepAction.REVIEW, StepTarget.CODE, _FakeFailingReviewHandler())

    mock_git.return_value = (0, "", "")

    runner = PipelineRunner(pipeline, ctx, registry=registry, store=store)
    run = await runner.run()

    assert run.status == RunStatus.COMPLETED

    # Since it failed review once and looped back, we should have TWO code generations in DB.
    # But crucially, they should have the EXACT SAME artifact_uuid because the second run extracted it from the file!
    with lineage_db.connect() as conn:
        rows = conn.execute(
            "SELECT artifact_id, parent_id, event_type FROM artifact_events WHERE event_type='generated_code' ORDER BY timestamp ASC"
        ).fetchall()

        assert len(rows) == 2
        gen1_id = rows[0]["artifact_id"]
        gen2_id = rows[1]["artifact_id"]

        # This is the vital assertion: The regenerated code preserved the lineage!
        assert gen1_id == gen2_id
        assert gen1_id is not None
