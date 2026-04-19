# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for dynamic orchestration of components."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.decompose import OrchestrateComponentsHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_integration_physical_io_join_locks(tmp_path: Path) -> None:
    """
    FR-5 (Integration): Proves physical OS file interactions correctly serialize.
    JOIN steps physically wait for fan_out() parallel component mocks to resolve
    before engaging OS file descriptors on shared artifacts.
    """
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.state import StepResult, StepStatus

    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
    ctx.run_id = "parent_run"

    log_file = tmp_path / "execution_log.txt"
    log_file.touch()

    class FakeConcurrentIOHandler:
        async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
            # We open the file and append our sequence ID
            if step.gate and step.gate.type.value == "join":
                with log_file.open("a") as f:
                    f.write("JOIN_START\n")
            else:
                import asyncio

                await asyncio.sleep(0.05)
                with log_file.open("a") as f:
                    f.write(f"FAN_OUT_{step.params.get('component')}\n")
            return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")

    registry = StepHandlerRegistry()
    registry.register(StepAction.GENERATE, StepTarget.CODE, FakeConcurrentIOHandler())

    mock_plan = json.dumps({"components": [{"component": "Alpha"}, {"component": "Beta"}]})
    ctx.plan = mock_plan

    # Force step 1 to be standard, Step 2 to be Join
    custom_yaml = {
        "name": "test",
        "steps": [
            {"name": "s1", "action": "generate", "target": "code"},
            {"name": "s2", "action": "generate", "target": "code", "gate": {"type": "join"}},
        ],
    }

    handler = OrchestrateComponentsHandler()
    runner = PipelineRunner(pipeline=MagicMock(), context=ctx, registry=registry, store=MagicMock())
    ctx.pipeline_runner = runner
    ctx.topology = MagicMock(impact_of=MagicMock(return_value=set()))

    with patch("yaml.safe_load", return_value=custom_yaml), patch("importlib.resources.files"):
        step_def = PipelineStep(
            name="orch", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
        )
        res = await handler.execute(step_def, ctx)

    assert res.status == StepStatus.PASSED

    # Verify the physical logs!
    records = log_file.read_text().splitlines()

    # At least 1 fan_out component + 1 joined piece. The main point is IO serialization.
    assert len(records) >= 3
    # The last elements MUST be the join barrier! High level IO serialization confirmed.
    assert records[-1] == "JOIN_START"
    assert "FAN_OUT" in records[0]
