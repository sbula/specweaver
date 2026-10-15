# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Dual pipeline orchestration — runs coding and scenario pipelines in parallel."""

from __future__ import annotations

import asyncio
import importlib.resources
import logging
from typing import TYPE_CHECKING, Any

import yaml

from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.handlers.results import log_step_failure
from specweaver.sandbox.qa_runner.core.atom import container_available

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def _isolation_refusal(context: RunContext) -> str | None:
    """Why the scenario side cannot be kept from the coder here; None when it can (FR-11, FR-18)."""
    from specweaver.commons.prepare_plan import detect_toolchain
    from specweaver.core.flow.handlers.scenario import scenario_store

    if scenario_store(context) is None:
        return (
            "a dual run keeps its scenario tests in the project's store, and this project is not "
            "registered; register it with `sw init` or `sw projects add`"
        )
    if (context.project_path / "scenarios" / "generated").exists():
        return (
            "the project still holds scenario tests in scenarios/, where the coder can read them; "
            "remove that folder — scenario tests now live outside the project"
        )
    if detect_toolchain(context.project_path) not in ("uv", ""):
        return (
            "a dual run is proven for Python projects only; containers for other languages are not"
        )
    return None


class ArbitrateDualPipelineHandler:
    """Handler for orchestrating the dual verification pipeline.

    Fans out the 'new_feature' and 'scenario_validation' pipelines concurrently
    for exactly one component (derived from the spec_path).
    """

    #: Whether a container can run the tests here; a class attribute so tests can stand in for it.
    container_available = staticmethod(container_available)
    #: Why isolation cannot hold for this project; a class attribute for the same reason.
    isolation_refusal = staticmethod(_isolation_refusal)

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.run.pipeline_runner is None:
            return _error_result(
                "pipeline_runner not available in context — cannot fan out dual pipelines",
                started,
            )
        refusal = self.isolation_refusal(context)
        if refusal is not None:
            return StepResult(
                status=StepStatus.FAILED,
                error_message=refusal,
                started_at=started,
                completed_at=_now_iso(),
            )
        if not self.container_available(context.project_path):
            # FR-18: fail closed. Without a container the coder's code could read the scenario
            # tests, so a run that only looks independent never starts.
            return StepResult(
                status=StepStatus.FAILED,
                error_message=(
                    "a dual run needs a container to keep the scenario tests from the coder, and "
                    "no Podman or Docker engine answers here; install one, or run without the "
                    "scenario side"
                ),
                started_at=started,
                completed_at=_now_iso(),
            )
        stem = context.spec_path.stem.replace("_spec", "")
        logger.info("ArbitrateDualPipelineHandler: Starting dual pipeline for component '%s'", stem)

        try:
            coding_runner = self._build_runner("new_feature.yaml", stem, context, "generate_code")
            scenario_runner = self._build_runner(
                "scenario_validation.yaml", stem, context, "generate_scenarios"
            )

            coding_task = asyncio.create_task(coding_runner.run(parent_run_id=context.run.run_id))
            scenario_task = asyncio.create_task(
                scenario_runner.run(parent_run_id=context.run.run_id)
            )

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
            log_step_failure(
                logger, "ArbitrateDualPipelineHandler: unhandled exception in dual pipeline"
            )
            return _error_result(str(exc), started)

    def _build_runner(
        self, pipe_file: str, component: str, context: RunContext, own_step: str
    ) -> Any:
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
            # The fan-out is autonomous by definition — no human channel inside it — and the
            # parent CLI enforces spec-must-exist. A HITL gate (e.g. new_feature.yaml's draft_spec
            # gate) would park the sub-pipeline on every first pass and deadlock the dual step.
            # Downgrade to auto.
            gate_def = step_dict.get("gate")
            if isinstance(gate_def, dict) and gate_def.get("type") == "hitl":
                gate_def["type"] = "auto"
            valid_steps.append(step_dict)

        pipe_data["steps"] = valid_steps
        pipe = PipelineDefinition(**pipe_data)

        # Each side gets only the arbiter's entry for its own step, taken out of the parent so it
        # reaches that side once: nothing the other side wrote or was told crosses over.
        entry = context.feedback.pop(own_step, None)
        own = {own_step: entry} if entry is not None else {}
        return context.run.pipeline_runner.spawn(pipe, feedback=own)
