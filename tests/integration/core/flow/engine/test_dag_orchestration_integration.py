# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests for DAG orchestration: fan-out of decomposed components, dependency
starvation, and collision handling.

Split out of `test_planning_integration.py`, which had grown past the file-size limit. That
file covers planning through to prompts and generators; this one covers what the orchestrator
does with a decomposition once it has one.
"""

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from specweaver.core.flow.engine.models import PipelineStep, StepAction, StepTarget
from specweaver.core.flow.engine.state import StepStatus
from specweaver.core.flow.handlers.base import RunContext
from specweaver.core.flow.handlers.decompose import OrchestrateComponentsHandler
from specweaver.core.flow.handlers.registry import StepHandlerRegistry


class TestDagOrchestratorIntegration:
    """Tests the interaction between OrchestrateComponentsHandler, TopologyGraph, and dynamically spawned PipelineRunners."""

    @pytest.mark.asyncio()
    async def test_integration_starvation_and_dependency_bubble_up(self, tmp_path: Path) -> None:
        """Integration Story 2: Failures in dynamic sub-pipelines properly starve dependents and bubble."""
        from specweaver.core.flow.engine.models import PipelineDefinition
        from specweaver.core.flow.engine.runner import PipelineRunner

        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        ctx.run = ctx.run.model_copy(update={"run_id": "parent_run"})

        # Two components: A and B. B depends on A.
        plan_dict = {
            "components": [
                {"component": "service_a", "dependencies": [], "target_modules": ["auth"]},
                {
                    "component": "service_b",
                    "dependencies": ["service_a"],
                    "target_modules": ["api"],
                },
            ]
        }
        ctx.plan_context = ctx.plan_context.model_copy(
            update={"decomposition": json.dumps(plan_dict)}
        )

        # We need a PipelineRunner with a registry. We will mock the runner to fail on 'service_a'
        pipe = PipelineDefinition.model_validate_json(json.dumps({"name": "test", "steps": []}))
        registry = StepHandlerRegistry()
        ctx.run = ctx.run.model_copy(
            update={
                "pipeline_runner": PipelineRunner(pipe, ctx, registry=registry, store=MagicMock())
            }
        )

        # Mock PipelineRunner.run() so we don't actually trigger deep LLM calls

        async def mocked_run(self_runner, parent_run_id=None):
            # If this is service_a, fail it!
            if self_runner._pipeline.name == "auto_service_a":
                return MagicMock(status=StepStatus.FAILED)
            return MagicMock(status=StepStatus.PASSED)

        with patch("specweaver.core.flow.engine.runner.PipelineRunner.run", new=mocked_run):
            handler = OrchestrateComponentsHandler()
            step_def = PipelineStep(
                name="orch", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
            )

            result = await handler.execute(step_def, ctx)

            # Since auto_service_a failed, B must be starved.
            # The parent orchestration must FAIL with a cascading failure message.
            assert result.status == StepStatus.FAILED, "Handler should bubble up failures."
            assert "Cascading failure" in result.error_message
            assert "Ran 1 total pipelines" in result.error_message, (
                "Only Service A should have run!"
            )

    @pytest.mark.asyncio()
    async def test_integration_topological_collision_deferment(self, tmp_path: Path) -> None:
        """Integration Story 1: DAG Orchestrator physically blocks overlapping impact chains."""
        import asyncio

        from specweaver.assurance.graph.topology import TopologyGraph
        from specweaver.core.flow.engine.models import PipelineDefinition
        from specweaver.core.flow.engine.runner import PipelineRunner

        ctx = RunContext(project_path=tmp_path, spec_path=tmp_path / "spec.md")
        ctx.run = ctx.run.model_copy(update={"run_id": "parent_run"})

        # Parallel components logically, no logical strictly defined dependency!
        # BUT they share a target module "auth"
        plan_dict = {
            "components": [
                {"component": "service_a", "dependencies": [], "target_modules": ["auth"]},
                {"component": "service_b", "dependencies": [], "target_modules": ["auth"]},
            ]
        }
        ctx.plan_context = ctx.plan_context.model_copy(
            update={"decomposition": json.dumps(plan_dict)}
        )

        # Mock topology showing collision
        mock_topo = MagicMock(spec=TopologyGraph)
        mock_topo.impact_of.return_value = {"auth"}
        ctx.graph = ctx.graph.model_copy(update={"topology": mock_topo})

        pipe = PipelineDefinition.model_validate_json(json.dumps({"name": "test", "steps": []}))
        ctx.run = ctx.run.model_copy(
            update={
                "pipeline_runner": PipelineRunner(
                    pipe, ctx, registry=MagicMock(), store=MagicMock()
                )
            }
        )

        # We need custom run() locking to prove they don't run *at the same time*.
        running_tasks = set()
        max_concurrent = 0

        async def mocked_run(self_runner, parent_run_id=None):
            nonlocal max_concurrent
            running_tasks.add(self_runner._pipeline.name)
            max_concurrent = max(max_concurrent, len(running_tasks))
            # Sleep briefly to ensure overlap if the engine didn't lock it
            await asyncio.sleep(0.1)
            running_tasks.remove(self_runner._pipeline.name)
            return MagicMock(status=StepStatus.PASSED, run_id="child_run_id")

        with patch("specweaver.core.flow.engine.runner.PipelineRunner.run", new=mocked_run):
            handler = OrchestrateComponentsHandler()
            step_def = PipelineStep(
                name="orch", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
            )

            result = await handler.execute(step_def, ctx)

            # Both should have run successfully
            assert result.status == StepStatus.PASSED
            assert len(result.output["sub_runs"]) == 2

            # The maximum observed concurrency MUST be 1 due to the topology conflict!
            assert max_concurrent == 1, (
                "Topological collision guard failed, tasks ran concurrently!"
            )


@pytest.mark.asyncio
async def test_integration_topological_join_wave_n_deferred() -> None:
    """
    Verifies that OrchestrateComponentsHandler correctly strips `gate: join` steps
    prior to running parallel fan_out pipelines, and correctly executes them identically
    at the end via a synchronised Wave N runner execution.
    """
    from pathlib import Path

    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.state import StepStatus
    from specweaver.core.flow.handlers.base import RunContext

    ctx = RunContext(project_path=Path("/tmp/path"), spec_path=Path("/tmp/path/spec.md"))
    ctx.run = ctx.run.model_copy(update={"run_id": "parent_run"})

    # 1. Provide a plan indicating 2 entirely disconnected components.
    mock_plan = json.dumps(
        {
            "components": [
                {"component": "AlphaFeature", "dependencies": []},
                {"component": "BetaFeature", "dependencies": []},
            ]
        }
    )
    ctx.plan_context = ctx.plan_context.model_copy(update={"decomposition": mock_plan})

    import importlib.resources

    import yaml

    files = importlib.resources.files("specweaver.workflows.pipelines")
    resource = files.joinpath("new_feature.yaml")
    base_yaml = yaml.safe_load(resource.read_text(encoding="utf-8"))

    # Force the last step to be a `join` Gate
    base_yaml["steps"][-1]["gate"] = {"type": "join"}
    custom_yaml_text = yaml.dump(base_yaml)

    handler = OrchestrateComponentsHandler()
    runner = PipelineRunner(
        pipeline=MagicMock(),
        context=ctx,
        registry=MagicMock(),
        store=MagicMock(),
        on_event=MagicMock(),
    )
    ctx.run = ctx.run.model_copy(update={"pipeline_runner": runner})

    original_init = PipelineRunner.__init__
    created_pipelines = []

    def spy_init(self: Any, pipeline: Any, *args: Any, **kwargs: Any) -> None:
        created_pipelines.append(pipeline)
        return original_init(self, pipeline, *args, **kwargs)

    with (
        patch.multiple(
            "specweaver.core.flow.engine.runner.PipelineRunner",
            __init__=spy_init,
            run=AsyncMock(return_value=MagicMock(status=StepStatus.PASSED, run_id="mock-run")),
        ),
        patch.object(importlib.resources, "files") as mock_files,
    ):
        mock_resource = MagicMock()
        mock_resource.joinpath.return_value.read_text.return_value = custom_yaml_text
        mock_files.return_value = mock_resource

        step_def = PipelineStep(
            name="orch", action=StepAction.ORCHESTRATE, target=StepTarget.COMPONENTS
        )
        res = await handler.execute(step_def, ctx)

    assert res.status == StepStatus.PASSED

    assert len(created_pipelines) == 3

    pipe_alpha = next(p for p in created_pipelines if p.name == "auto_AlphaFeature")
    pipe_beta = next(p for p in created_pipelines if p.name == "auto_BetaFeature")
    pipe_join = next(p for p in created_pipelines if "wave_n" in p.name)

    assert len(pipe_alpha.steps) == len(base_yaml["steps"]) - 1
    assert len(pipe_beta.steps) == len(base_yaml["steps"]) - 1

    assert len(pipe_join.steps) == 2
    assert pipe_join.steps[0].params["component"] in ["AlphaFeature", "BetaFeature"]
    assert pipe_join.steps[1].params["component"] in ["AlphaFeature", "BetaFeature"]
    assert pipe_join.steps[0].params["component"] != pipe_join.steps[1].params["component"]
