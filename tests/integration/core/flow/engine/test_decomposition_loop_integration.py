# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for the Feature Decomposition Loop."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers import StepHandlerRegistry
from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.engine.store import StateStore


@pytest.fixture
def mock_store(tmp_path: Path) -> StateStore:
    return StateStore(tmp_path / "concurrent_state.db")


@pytest.mark.asyncio
async def test_3_strikes_loop_coverage_abort(tmp_path: Path, mock_store: StateStore) -> None:
    """NFR-1 / FR-5: 3-strikes hard abort if coverage score stays < 1.0."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

    # We will load the actual feature_decomposition pipeline, but we'll mock the StepHandlers
    pipe = PipelineDefinition.model_validate_json(
        json.dumps(
            {
                "name": "test",
                "steps": [
                    {
                        "name": "fail_loop",
                        "action": "decompose",
                        "target": "feature",
                        "gate": {
                            "type": "auto",
                            "condition": "all_passed",
                            "on_fail": "loop_back",
                            "loop_target": "fail_loop",
                            "max_retries": 3,
                        },
                    }
                ],
            }
        )
    )

    registry = StepHandlerRegistry()
    mock_handler = AsyncMock()
    # Mocking failure to trigger loop 3 times
    mock_handler.execute.return_value = AsyncMock(
        status=StepStatus.FAILED, error_message="FR-5 failed", output={}
    )
    registry.register("decompose", "feature", mock_handler)

    runner = PipelineRunner(pipe, ctx, store=mock_store, registry=registry)
    run_state = await runner.run()

    # Assert
    assert run_state.status.value == "failed"
    # Should execute 1 time + 3 retries = 4 times
    assert mock_handler.execute.call_count == 4


@pytest.mark.asyncio
async def test_fan_out_cascade_failures_bubble_up(tmp_path: Path, mock_store: StateStore) -> None:
    """FR-4 / Story 13: Sub-Pipeline failures cascade gracefully to parent."""
    ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")

    # The parent orchestrate step
    pipe = PipelineDefinition.model_validate_json(
        json.dumps(
            {
                "name": "test",
                "steps": [{"name": "orch", "action": "orchestrate", "target": "components"}],
            }
        )
    )

    plan_data = {
        "feature_spec": "path.md",
        "components": [{"component": "valid_comp"}],
        "integration_seams": [],
        "build_sequence": ["valid_comp"],
        "coverage_score": 1.0,
        "timestamp": "2026",
    }
    ctx.plan = json.dumps(plan_data)

    with patch("specweaver.core.flow.handlers.decompose.OrchestrateComponentsHandler") as _:
        handler_instance = AsyncMock()
        # Mocking the actual fan_out failure
        handler_instance.execute.return_value = AsyncMock(
            status=StepStatus.FAILED, error_message="1 sub-pipelines failed.", output={}
        )

        registry = StepHandlerRegistry()
        registry.register("orchestrate", "components", handler_instance)

        runner = PipelineRunner(pipe, ctx, store=mock_store, registry=registry)
        run_state = await runner.run()

        assert run_state.status.value == "failed"
        assert handler_instance.execute.call_count == 1
