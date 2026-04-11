# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for PipelineRunner integration with RouterEvaluator."""

from __future__ import annotations

from typing import Any

import pytest

from specweaver.flow.handlers import RunContext, StepHandler, StepHandlerRegistry
from specweaver.flow.models import (
    PipelineDefinition,
    PipelineStep,
    RouterDefinition,
    RouterRule,
    RuleOperator,
    StepAction,
    StepTarget,
)
from specweaver.flow.runner import PipelineRunner
from specweaver.flow.state import RunStatus, StepResult, StepStatus


class FakeHandler(StepHandler):
    def __init__(self, output: dict[str, Any] | None = None, failing: bool = False):
        self._output = output or {}
        self._failing = failing
        self.call_count = 0

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        self.call_count += 1
        return StepResult(
            status=StepStatus.FAILED if self._failing else StepStatus.PASSED,
            output=self._output,
            started_at="2026",
            completed_at="2026",
        )

@pytest.fixture
def mock_context(tmp_path) -> RunContext:

    project_path = tmp_path / "test-project"
    spec_path = project_path / "spec.md"
    project_path.mkdir(parents=True, exist_ok=True)
    spec_path.touch()

    return RunContext(project_path=project_path, spec_path=spec_path)

@pytest.fixture
def registry() -> StepHandlerRegistry:
    return StepHandlerRegistry()

@pytest.mark.asyncio
async def test_runner_executes_sequential_when_no_router(mock_context, registry):
    registry.register(StepAction.VALIDATE, StepTarget.SPEC, FakeHandler())
    registry.register(StepAction.REVIEW, StepTarget.SPEC, FakeHandler())

    pipe = PipelineDefinition(
        name="test_linear",
        steps=[
            PipelineStep(name="step_a", action=StepAction.VALIDATE, target=StepTarget.SPEC),
            PipelineStep(name="step_b", action=StepAction.REVIEW, target=StepTarget.SPEC),
        ]
    )
    runner = PipelineRunner(pipe, mock_context, registry=registry)
    run = await runner.run()

    assert run.status == RunStatus.COMPLETED
    assert run.step_records[0].status == StepStatus.PASSED
    assert run.step_records[1].status == StepStatus.PASSED
    assert run.current_step == 2

@pytest.mark.asyncio
async def test_runner_respects_router_skip_step(mock_context, registry):
    h1 = FakeHandler(output={"complexity": "simple"})
    h2 = FakeHandler()
    h3 = FakeHandler()

    registry.register(StepAction.PLAN, StepTarget.SPEC, h1)
    registry.register(StepAction.DECOMPOSE, StepTarget.FEATURE, h2)
    registry.register(StepAction.GENERATE, StepTarget.CODE, h3)

    pipe = PipelineDefinition(
        name="test_branch",
        steps=[
            PipelineStep(
                name="assess",
                action=StepAction.PLAN,
                target=StepTarget.SPEC,
                router=RouterDefinition(
                    rules=[
                        RouterRule(field="complexity", operator=RuleOperator.EQ, value="complex", target="decompose")
                    ],
                    default_target="generate"
                )
            ),
            PipelineStep(name="decompose", action=StepAction.DECOMPOSE, target=StepTarget.FEATURE),
            PipelineStep(name="generate", action=StepAction.GENERATE, target=StepTarget.CODE),
        ]
    )
    runner = PipelineRunner(pipe, mock_context, registry=registry)
    run = await runner.run()

    assert run.status == RunStatus.COMPLETED
    # Assess passed
    assert run.step_records[0].status == StepStatus.PASSED
    # Decompose skipped
    assert h2.call_count == 0
    assert run.step_records[1].status == StepStatus.PENDING
    assert run.step_records[1].result is None
    # Generate executed
    assert h3.call_count == 1
    assert run.step_records[2].status == StepStatus.PASSED

@pytest.mark.asyncio
async def test_router_respects_gate_precedence(mock_context, registry):
    """If a step fails its gate, the router is NOT executed!"""
    h1 = FakeHandler(output={"score": 10}, failing=True)  # Fails directly so gate isn't completely evaluated the same way but fail breaks
    h2 = FakeHandler()

    registry.register(StepAction.VALIDATE, StepTarget.SPEC, h1)
    registry.register(StepAction.REVIEW, StepTarget.SPEC, h2)

    pipe = PipelineDefinition(
        name="test_gate_first",
        steps=[
            PipelineStep(
                name="step_a",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                router=RouterDefinition(default_target="step_b")
            ),
            PipelineStep(name="step_b", action=StepAction.REVIEW, target=StepTarget.SPEC)
        ]
    )

    runner = PipelineRunner(pipe, mock_context, registry=registry)
    run = await runner.run()

    assert run.status == RunStatus.FAILED
    assert h1.call_count == 1
    assert h2.call_count == 0
    assert run.step_records[0].status == StepStatus.FAILED
    assert run.step_records[1].status == StepStatus.PENDING

@pytest.mark.asyncio
async def test_router_infinite_loop_guard(mock_context, registry):
    h1 = FakeHandler()
    h2 = FakeHandler()

    registry.register(StepAction.VALIDATE, StepTarget.SPEC, h1)
    registry.register(StepAction.REVIEW, StepTarget.SPEC, h2)

    pipe = PipelineDefinition(
        name="test_infinite",
        max_total_loops=5,  # Restrict to 5 jumps
        steps=[
            PipelineStep(name="step_a", action=StepAction.VALIDATE, target=StepTarget.SPEC),
            PipelineStep(
                name="step_b",
                action=StepAction.REVIEW,
                target=StepTarget.SPEC,
                router=RouterDefinition(default_target="step_a")  # Always jump backward
            )
        ]
    )

    runner = PipelineRunner(pipe, mock_context, registry=registry)
    run = await runner.run()

    assert run.status == RunStatus.FAILED
    # Should run A -> B 5 times, then B fails on the 6th jump attempt
    assert run.current_step == 1
    record = run.step_records[1]
    assert record.status == StepStatus.FAILED
    assert "Infinite routing loop" in record.result.error_message

@pytest.mark.asyncio
async def test_router_edge_cases_and_telemetry(mock_context, registry):
    h1 = FakeHandler(output={"count": 5}) # missing "name" field
    h2 = FakeHandler()

    registry.register(StepAction.VALIDATE, StepTarget.SPEC, h1)
    registry.register(StepAction.REVIEW, StepTarget.SPEC, h2)

    pipe = PipelineDefinition(
        name="test_edge_cases",
        steps=[
            PipelineStep(
                name="step_a",
                action=StepAction.VALIDATE,
                target=StepTarget.SPEC,
                router=RouterDefinition(
                    rules=[
                        RouterRule(field="name", operator=RuleOperator.EQ, target="step_a", value="missing")
                    ],
                    default_target="step_b"
                )
            ),
            PipelineStep(name="step_b", action=StepAction.REVIEW, target=StepTarget.SPEC)
        ]
    )

    events_caught = []
    def _catcher(event, **kw):
        events_caught.append(event)

    runner = PipelineRunner(pipe, mock_context, registry=registry, on_event=_catcher)
    run = await runner.run()

    assert run.status == RunStatus.COMPLETED
    assert "step_routed" in events_caught
