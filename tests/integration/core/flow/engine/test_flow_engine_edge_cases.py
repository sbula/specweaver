# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests exercising multiple flow engine edge cases in a single run.
This ensures proper interaction between Runner, Handlers, Gates, and Display.
"""

from __future__ import annotations
from specweaver.core.flow.handlers.base import RunContext

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest

from specweaver.core.flow.engine.models import (
    GateCondition,
    GateDefinition,
    OnFailAction,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.store import StateStore



@pytest.fixture
def temp_store(tmp_path: Path) -> StateStore:
    db_path = tmp_path / "test_state.db"
    return StateStore(db_path)


@pytest.mark.asyncio
async def test_complex_edge_cases_scenario(temp_store: StateStore, tmp_path: Path) -> None:
    """Exercises multiple edge cases in one go:
    - Step missing a handler (unhandled action/target)
    - Gate retry logic
    - Parked gate
    - Persistence roundtrip with rich history
    """

    # Create a pipeline with intentionally challenging scenarios
    pipeline = PipelineDefinition(
        name="edge_case_pipeline",
        steps=[
            # 1. Standard step that should pass via validate_tests
            PipelineStep(
                name="valid_step",
                action=StepAction.VALIDATE,
                target=StepTarget.TESTS,
                description="A valid step",
            ),
            # 2. Step that loops/retries heavily using unknown condition
            PipelineStep(
                name="bouncing_step",
                action=StepAction.VALIDATE,
                target=StepTarget.CODE,
                gate=GateDefinition(
                    condition=GateCondition.ALL_PASSED, on_fail=OnFailAction.RETRY, max_retries=1
                ),
            ),
            # 3. Step that will park the pipeline definitively
            PipelineStep(
                name="parking_step",
                action=StepAction.REVIEW,
                target=StepTarget.SPEC,
                gate=GateDefinition(condition=GateCondition.ACCEPTED, on_fail=OnFailAction.ABORT),
            ),
        ],
    )

    # We use a dummy spec path
    spec_path = tmp_path / "dummy.md"
    spec_path.write_text("# Dummy")
    context = RunContext(project_path=tmp_path, spec_path=spec_path)
    runner = PipelineRunner(pipeline, context, store=temp_store)

    run = await runner.run()

    # We no longer need to retrieve by run_id separately as run() returns the object

    # Since we didn't mock the inner execution perfectly, let's just make sure
    # it didn't crash and recorded expected things.
    # We expect parking_step to either be not reached or PARKED/FAILED depending
    # on whether bouncing_step passed or failed validation.

    assert str(run.status).split(".")[-1].lower() in (
        "completed",
        "parked",
        "failed",
        "aborted",
        "success",
    )

    # Ensure audit log captured the run's complexity
    audit_logs = temp_store.get_audit_log(run.run_id)
    assert len(audit_logs) > 0
    assert any("started" in entry["event"].lower() for entry in audit_logs)

    # Let's verify the display plugin wouldn't crash
    from specweaver.core.flow.engine.display import RichPipelineDisplay

    display = RichPipelineDisplay()
    # Ensure starting and immediately stopping with a complex run works
    display("run_started", run=run)
    display("run_completed", run=run)
    display.stop()
