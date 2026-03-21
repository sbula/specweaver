# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for pipeline state persistence."""

from pathlib import Path

import pytest

from specweaver.flow.handlers import RunContext, StepHandlerRegistry
from specweaver.flow.models import (
    GateCondition,
    GateDefinition,
    GateType,
    PipelineDefinition,
    PipelineStep,
    StepAction,
    StepTarget,
)
from specweaver.flow.runner import PipelineRunner
from specweaver.flow.state import RunStatus, StepResult, StepStatus
from specweaver.flow.store import StateStore


class FakeHitlHandler:
    async def execute(self, step, context):
        return StepResult(status=StepStatus.WAITING_FOR_INPUT, output={"message": "wait"}, started_at="1", completed_at="2")


class FakePassHandler:
    async def execute(self, step, context):
        return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")


@pytest.mark.asyncio
async def test_pipeline_halt_and_resume(tmp_path: Path) -> None:
    """Simulates a pipeline halting on HITL, successfully persisting, and being re-loaded."""
    store_path = tmp_path / "pipeline.db"
    store = StateStore(store_path)

    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, FakePassHandler())
    registry.register(StepAction.REVIEW, StepTarget.SPEC, FakeHitlHandler())

    pipeline = PipelineDefinition(
        name="resume_test",
        steps=[
            PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(name="review", action=StepAction.REVIEW, target=StepTarget.SPEC,
                         gate=GateDefinition(type=GateType.HITL, condition=GateCondition.ACCEPTED)),
        ]
    )

    # Run 1: Should pass draft and park at review
    context1 = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    runner1 = PipelineRunner(pipeline, context1, store=store, registry=registry)
    run1 = await runner1.run()

    assert run1.status == RunStatus.PARKED
    assert run1.current_step == 1

    # Change the review handler to pass so it progresses on resume
    registry.register(StepAction.REVIEW, StepTarget.SPEC, FakePassHandler())

    # Run 2: Resume from store
    context2 = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

    pipeline2 = pipeline.model_copy(deep=True)
    pipeline2.steps[1].gate = None  # Remove HITL gate so it progresses past the review step

    runner2 = PipelineRunner(pipeline2, context2, store=store, registry=registry)
    # The runner will detect the latest run in the store for this project/pipeline
    run2 = await runner2.resume(run1.run_id)

    # It should resume from step 1 (review), which now passes, and then complete
    assert run2.status == RunStatus.COMPLETED
    assert run2.run_id == run1.run_id # Same run
    assert run2.current_step == 2 # Completed all 2 steps
