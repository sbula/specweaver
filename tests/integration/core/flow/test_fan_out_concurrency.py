# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for high-concurrency state store writes during fan_out."""

import asyncio
from pathlib import Path

import pytest

from specweaver.core.flow.handlers import RunContext, StepHandlerRegistry
from specweaver.core.flow.models import PipelineDefinition, PipelineStep, StepAction, StepTarget
from specweaver.core.flow.runner import PipelineRunner
from specweaver.core.flow.state import StepResult, StepStatus
from specweaver.core.flow.store import StateStore


class FakeAsyncWorkHandler:
    """Simulates async work to allow context switching between threads."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        # Sleep forces asyncio to yield, maximizing concurrent interleaved writes
        await asyncio.sleep(0.01)
        return StepResult(status=StepStatus.PASSED, output={}, started_at="1", completed_at="2")


@pytest.mark.asyncio
async def test_high_concurrency_statestore_persistence(tmp_path: Path) -> None:
    """
    Spawns 10 parallel sub-pipelines via `fan_out`, simulating concurrent updates
    into the SQLite WAL StateStore.
    This guarantees that the runner doesn't fail with SQLITE_BUSY when child runs yield.
    """
    store = StateStore(tmp_path / "concurrent_state.db")
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

    registry = StepHandlerRegistry()
    registry.register(StepAction.VALIDATE, StepTarget.CODE, FakeAsyncWorkHandler())

    # We build a primary runner but just create a dummy parent run in the store
    master_pipe = PipelineDefinition(name="master", steps=[])
    runner = PipelineRunner(master_pipe, ctx, store=store, registry=registry)

    parent_run = await runner.run()  # this saves it to store
    parent_id = parent_run.run_id

    # We build 10 sub pipelines, each with 3 steps
    sub_pipes = []
    for i in range(10):
        pipe = PipelineDefinition(
            name=f"sub_{i}",
            steps=[
                PipelineStep(name=f"step_{j}", action=StepAction.VALIDATE, target=StepTarget.CODE)
                for j in range(3)
            ],
        )
        sub_pipes.append(pipe)

    # Fan out the 10 child pipelines concurrently using the real parent_id
    results = await runner.fan_out(sub_pipes, parent_run_id=parent_id)

    assert len(results) == 10

    # Ensure all 10 are actually persisted in the DB
    stored_runs = []
    for r in results:
        stored = store.load_run(r.run_id)
        assert stored is not None
        assert stored.parent_run_id == parent_id
        assert stored.status.value == "completed"
        stored_runs.append(stored)

    assert len(stored_runs) == 10
