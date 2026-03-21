# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Integration tests for Flow Engine display rendering."""

import io
from pathlib import Path

import pytest
from rich.console import Console

from specweaver.flow.display import RichPipelineDisplay
from specweaver.flow.handlers import StepHandlerRegistry, RunContext
from specweaver.flow.models import PipelineDefinition, PipelineStep, StepAction, StepTarget, GateDefinition, GateType, GateCondition, OnFailAction
from specweaver.flow.runner import PipelineRunner
from specweaver.flow.state import StepResult, StepStatus


class FakePassHandler:
    async def execute(self, step, context):
        return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")

class FakeHitlHandler:
    async def execute(self, step, context):
        return StepResult(status=StepStatus.WAITING_FOR_INPUT, output={"message": "wait"}, started_at="1", completed_at="2")


@pytest.mark.asyncio
async def test_display_integration_full_pipeline(tmp_path: Path) -> None:
    """End-to-end display rendering for a pipeline with passes, parks, and gates."""
    # Capture Rich console output
    console = Console(file=io.StringIO(), force_terminal=False)
    display = RichPipelineDisplay(console=console)
    
    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, FakePassHandler())
    registry.register(StepAction.REVIEW, StepTarget.SPEC, FakeHitlHandler())
    
    pipeline = PipelineDefinition(
        name="test_display",
        steps=[
            PipelineStep(name="draft", action=StepAction.DRAFT, target=StepTarget.SPEC),
            PipelineStep(
                name="review", 
                action=StepAction.REVIEW, 
                target=StepTarget.SPEC,
                gate=GateDefinition(type=GateType.HITL, condition=GateCondition.ACCEPTED)
            ),
        ]
    )
    
    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    runner = PipelineRunner(pipeline, context, registry=registry, on_event=display)
    
    # Run pipeline
    run = await runner.run()
    
    output = console.file.getvalue()
    # It should have started, rendered the draft step (passed), and parked at review
    assert "parked" in output.lower()
    assert "review" in output.lower()
    assert "waiting" in output.lower() or "parked" in output.lower()
    assert run.current_step == 1
