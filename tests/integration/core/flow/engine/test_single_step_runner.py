# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for single_step pipeline execution."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep


def test_single_step_pipeline_executes_smoothly(tmp_path: Path) -> None:
    """PipelineRunner successfully executes a dynamically compiled single_step."""
    from unittest.mock import MagicMock

    pipeline = PipelineDefinition.create_single_step(
        name="test_dummy_step",
        action=StepAction.DRAFT,
        target=StepTarget.SPEC,
        description="A simple single step to verify runner plumbing",
        params={"foo": "bar"},
    )

    # We must patch StepHandlerRegistry or use a fake handler because we don't want to actually draft
    # Let's mock a handler and inject it


    class DummyHandler:
        async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
            import datetime

            from specweaver.core.flow.engine.state import StepResult, StepStatus

            return StepResult(
                status=StepStatus.PASSED,
                output={"msg": "success", "params": step.params},
                started_at=datetime.datetime.now(datetime.UTC).isoformat(),
                completed_at=datetime.datetime.now(datetime.UTC).isoformat(),
            )

    context = RunContext(project_path=tmp_path, spec_path=tmp_path / "dummy.md", config=MagicMock())

    registry = StepHandlerRegistry()
    registry.register(StepAction.DRAFT, StepTarget.SPEC, DummyHandler())

    runner = PipelineRunner(pipeline, context, registry=registry)

    try:
        run_state = asyncio.run(runner.run())
        assert run_state.status == RunStatus.COMPLETED
        assert len(run_state.step_records) == 1
        record = run_state.step_records[0]
        assert record.step_name == "test_dummy_step"
        assert record.status == StepStatus.PASSED
        assert record.result is not None
        assert record.result.output["msg"] == "success"
        assert record.result.output["params"]["foo"] == "bar"
    finally:
        pass
