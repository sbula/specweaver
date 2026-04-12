# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Handlers for Feature Decomposition and Component Orchestration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.flow._base import RunContext, StepHandler
from specweaver.core.flow.state import StepResult, StepStatus
from specweaver.workflows.planning.decomposer import FeatureDecomposer

if TYPE_CHECKING:
    from specweaver.core.flow.models import PipelineStep

logger = logging.getLogger(__name__)

class DecomposeFeatureHandler(StepHandler):
    """Generates the DecompositionPlan via FeatureDecomposer."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.info("Executing DECOMPOSE FEATURE for %s", context.run_id)

        try:
            # Reconstruct the feature name from step params if passed, or derived
            feature_name = step.params.get("feature_name", "unknown_feature")

            # Use the LLM and the Decomposer
            decomposer = FeatureDecomposer(llm=context.llm, context_provider=context.context_provider)

            # Read spec content if exists
            spec_content = ""
            if context.spec_path.exists():
                spec_content = context.spec_path.read_text(encoding="utf-8")

            plan = await decomposer.decompose(
                feature_name=feature_name,
                spec_content=spec_content,
                topology_contexts=[context.topology] if context.topology else None,
                project_metadata=context.project_metadata,
            )

            # FR-5 Coverage Assertion Bounds
            if plan.coverage_score < 1.0:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Coverage Assert Failed: Coverage score {plan.coverage_score} is below 1.0 threshold.",
                    started_at=context.project_metadata.date_iso if context.project_metadata else "",
                    completed_at="", # Runner will fill
                )

            # Return the plan as a serialized JSON dictionary in the output
            return StepResult(
                status=StepStatus.PASSED,
                output=plan.model_dump(),
                started_at=context.project_metadata.date_iso if context.project_metadata else "",
                completed_at="",
            )

        except Exception as e:
            logger.exception("Failed to decompose feature")
            return StepResult(
                status=StepStatus.ERROR,
                error_message=str(e),
                started_at="",
                completed_at="",
            )

class OrchestrateComponentsHandler(StepHandler):
    """Executes fan_out on the runner for each mapped component."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:  # noqa: C901
        logger.info("Executing ORCHESTRATE COMPONENTS for %s", context.run_id)
        import json

        from specweaver.core.flow.models import PipelineDefinition

        try:
            if not context.plan:
                return StepResult(status=StepStatus.FAILED, error_message="No DecompositionPlan found in context.", started_at="", completed_at="")

            plan_data = json.loads(context.plan)
            components = plan_data.get("components", [])

            if not components:
                # No sub-components to orchestrate
                return StepResult(status=StepStatus.PASSED, output={"sub_runs": []}, started_at="", completed_at="")

            import importlib.resources
            import re

            import yaml  # type: ignore

            sub_pipes = []
            name_pattern = re.compile(r"^[a-zA-Z0-9_\-]+$")

            for comp in components:
                name = comp.get("component")
                if not name or not name_pattern.match(name):
                    return StepResult(status=StepStatus.FAILED, error_message=f"Invalid or malicious component name detected: '{name}'. Aborting fan_out to prevent path traversal.", started_at="", completed_at="")

                try:
                    files = importlib.resources.files("specweaver.workflows.pipelines")
                    resource = files.joinpath("new_feature.yaml")
                    text = resource.read_text(encoding="utf-8")
                    pipe_data = yaml.safe_load(text)

                    pipe_data["name"] = f"auto_{name}"

                    for step_dict in pipe_data.get("steps", []):
                        if "params" not in step_dict:
                            step_dict["params"] = {}
                        step_dict["params"]["component"] = name

                    pipe = PipelineDefinition(**pipe_data)
                    sub_pipes.append(pipe)
                except Exception as e:
                    logger.exception("Failed to load new_feature.yaml template for component %s", name)
                    return StepResult(status=StepStatus.FAILED, error_message=f"Failed to load new_feature.yaml template: {e}", started_at="", completed_at="")

            if not context.pipeline_runner:
                return StepResult(status=StepStatus.FAILED, error_message="pipeline_runner not found in context. Cannot fan_out.", started_at="", completed_at="")

            logger.info("Fanning out %d sub-pipelines for run %s", len(sub_pipes), context.run_id)
            run_results = await context.pipeline_runner.fan_out(sub_pipes, parent_run_id=context.run_id)

            failed = [r for r in run_results if r.status != StepStatus.PASSED and getattr(r, "status", None) != "completed"]

            if failed:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"{len(failed)} sub-pipelines failed.",
                    started_at="",
                    completed_at=""
                )

            return StepResult(
                status=StepStatus.PASSED,
                output={"sub_runs": [r.run_id for r in run_results]},
                started_at="",
                completed_at=""
            )

        except Exception as e:
            logger.exception("Failed to orchestrate components")
            return StepResult(status=StepStatus.ERROR, error_message=str(e), started_at="", completed_at="")
