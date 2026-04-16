# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Dual pipeline orchestration — runs coding and scenario pipelines in parallel."""

from __future__ import annotations

import asyncio
import importlib.resources
import logging
from typing import TYPE_CHECKING, Any

import yaml

from specweaver.core.flow._base import _error_result, _now_iso
from specweaver.core.flow.models import PipelineDefinition
from specweaver.core.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.core.flow._base import RunContext
    from specweaver.core.flow.models import PipelineStep

logger = logging.getLogger(__name__)


class ArbitrateDualPipelineHandler:
    """Handler for orchestrating the dual verification pipeline.

    Fans out the 'new_feature' and 'scenario_validation' pipelines concurrently
    for exactly one component (derived from the spec_path).
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        stem = context.spec_path.stem.replace("_spec", "")
        logger.info("ArbitrateDualPipelineHandler: Starting dual pipeline for component '%s'", stem)

        try:
            coding_runner = self._build_runner("new_feature.yaml", stem, context)
            scenario_runner = self._build_runner("scenario_validation.yaml", stem, context)

            coding_task = asyncio.create_task(coding_runner.run(parent_run_id=context.run_id))
            scenario_task = asyncio.create_task(scenario_runner.run(parent_run_id=context.run_id))

            _done, _ = await asyncio.wait(
                [coding_task, scenario_task], return_when=asyncio.ALL_COMPLETED
            )

            coding_result = coding_task.result()
            scenario_result = scenario_task.result()

            logger.info(
                "ArbitrateDualPipelineHandler: Completed. Coding=%s, Scenario=%s",
                getattr(coding_result, "status", "unknown"),
                getattr(scenario_result, "status", "unknown"),
            )

            if getattr(coding_result, "status", None) not in (StepStatus.PASSED, "completed"):
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Coding pipeline failed: {getattr(coding_result, 'error_message', 'Unknown')}",
                    started_at=started,
                    completed_at=_now_iso(),
                )

            if getattr(scenario_result, "status", None) not in (StepStatus.PASSED, "completed"):
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Scenario pipeline failed: {getattr(scenario_result, 'error_message', 'Unknown')}",
                    started_at=started,
                    completed_at=_now_iso(),
                )

            return StepResult(
                status=StepStatus.PASSED,
                output={"component": stem, "status": "dual_completed"},
                started_at=started,
                completed_at=_now_iso(),
            )

        except Exception as exc:
            logger.exception("ArbitrateDualPipelineHandler: unhandled exception in dual pipeline")
            return _error_result(str(exc), started)

    def _build_runner(self, pipe_file: str, component: str, context: RunContext) -> Any:
        files = importlib.resources.files("specweaver.workflows.pipelines")
        resource = files.joinpath(pipe_file)
        base_pipe_yaml = resource.read_text(encoding="utf-8")

        pipe_data = yaml.safe_load(base_pipe_yaml)
        pipe_data["name"] = f"auto_dual_{pipe_file.replace('.yaml', '')}_{component}"

        valid_steps = []
        for step_dict in pipe_data.get("steps", []):
            if "params" not in step_dict:
                step_dict["params"] = {}
            step_dict["params"]["component"] = component
            valid_steps.append(step_dict)

        pipe_data["steps"] = valid_steps
        pipe = PipelineDefinition(**pipe_data)

        from specweaver.core.flow.runner import PipelineRunner

        return PipelineRunner(
            pipeline=pipe,
            context=context.pipeline_runner._context,
            registry=context.pipeline_runner._registry,
            store=context.pipeline_runner._store,
            on_event=context.pipeline_runner._on_event,
        )
