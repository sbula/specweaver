# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Dual pipeline orchestration — runs coding and scenario pipelines in parallel."""

from __future__ import annotations

import asyncio
import importlib.resources
import logging
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import yaml

from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.handlers.results import log_step_failure
from specweaver.core.flow.handlers.reviewed_spec import review_refusal
from specweaver.sandbox.qa_runner.core.atom import container_available

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def _isolation_refusal(context: RunContext) -> str | None:
    """Why the scenario side cannot be kept from the coder here; None when it can (FR-11, FR-18)."""
    from specweaver.commons.prepare_plan import detect_toolchain
    from specweaver.core.flow.handlers.scenario_store import scenario_store

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


#: Each side's pipeline and the step its arbiter feedback is for.
_SIDES = {
    "coder": ("new_feature.yaml", "generate_code"),
    "scenario": ("scenario_validation.yaml", "generate_scenarios"),
}
#: A side that was right last round: its output stays as it is.
_KEPT = SimpleNamespace(status="completed", step_records=())


def _model_check(context: RunContext) -> tuple[dict[str, str], str | None]:
    """What the run summary says about the two sides' models, and a refusal when they share one
    that the settings could have kept apart."""
    from specweaver.infrastructure.llm.models import TaskType

    router = context.model.llm_router
    if not (hasattr(router, "model_of") and hasattr(router, "named_models")):
        return {"models": "unknown"}, None
    coder, scenario = router.model_of(TaskType.IMPLEMENT), router.model_of(TaskType.SCENARIO)
    if coder != scenario:
        return {}, None
    if len(router.named_models()) >= 2:
        return {}, (
            f"both sides of the dual run would use {coder}, though the settings name other models; "
            "set roles.implement and roles.scenario to different models"
        )
    logger.warning("ArbitrateDualPipelineHandler: both sides use one model, %s", coder)
    return {"one_model": coder}, None


def _sides_to_run(feedback: dict[str, Any]) -> set[str]:
    """The sides a verdict sent back; on a first round, or with no verdict, both."""
    sent_back = {side for side, (_, step) in _SIDES.items() if step in feedback}
    if sent_back:
        logger.info("ArbitrateDualPipelineHandler: running again: %s", ", ".join(sorted(sent_back)))
    return sent_back or set(_SIDES)


#: The coding side's steps that draft or review the spec, which a dual run has already reviewed.
_SPEC_STEPS = frozenset({"draft_spec", "review_spec"})


def _why_failed(run: Any) -> str:
    """The error of the step that stopped a side's run, for the person reading the parent run."""
    for record in reversed(getattr(run, "step_records", None) or []):
        if record.result is not None and record.result.error_message:
            return str(record.result.error_message)
    return str(getattr(run, "error_message", None) or "Unknown")


def _problems(run: Any) -> list[str]:
    """The spec or contract problems a side's scenario step named."""
    for record in getattr(run, "step_records", None) or []:
        found = (record.result.output or {}).get("problems") if record.result else None
        if found:
            return [str(problem) for problem in found]
    return []


def side_pipeline(pipe_file: str, component: str, *, coder_side: bool) -> PipelineDefinition:
    """One side's pipeline as a dual run runs it."""
    files = importlib.resources.files("specweaver.workflows.pipelines")
    pipe_data = yaml.safe_load(files.joinpath(pipe_file).read_text(encoding="utf-8"))
    pipe_data["name"] = f"auto_dual_{pipe_file.replace('.yaml', '')}_{component}"

    valid_steps = []
    for step_dict in pipe_data.get("steps", []):
        if coder_side and step_dict.get("name") in _SPEC_STEPS:
            continue  # the spec was reviewed before the dual run; the coder only reads it
        step_dict.setdefault("params", {})["component"] = component
        # The fan-out is autonomous by definition — no human channel inside it — and the
        # parent CLI enforces spec-must-exist. A HITL gate would park the sub-pipeline on every
        # first pass and deadlock the dual step. Downgrade to auto.
        gate_def = step_dict.get("gate")
        if isinstance(gate_def, dict) and gate_def.get("type") == "hitl":
            gate_def["type"] = "auto"
        valid_steps.append(step_dict)
    pipe_data["steps"] = valid_steps
    return PipelineDefinition(**pipe_data)


def dual_side_pipelines() -> list[PipelineDefinition]:
    """Both sides' pipelines, for checking every role a dual run will use before it starts."""
    return [
        side_pipeline(pipe, "", coder_side=side == "coder") for side, (pipe, _) in _SIDES.items()
    ]


class ArbitrateDualPipelineHandler:
    """Handler for orchestrating the dual verification pipeline.

    Fans out the 'new_feature' and 'scenario_validation' pipelines concurrently
    for exactly one component (derived from the spec_path).
    """

    #: Whether a container can run the tests here; a class attribute so tests can stand in for it.
    container_available = staticmethod(container_available)
    #: Why isolation cannot hold for this project; a class attribute for the same reason.
    isolation_refusal = staticmethod(_isolation_refusal)
    review_refusal = staticmethod(review_refusal)

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
        models, refused_models = _model_check(context)
        if refused_models is not None:
            return StepResult(
                status=StepStatus.FAILED,
                error_message=refused_models,
                started_at=started,
                completed_at=_now_iso(),
            )
        unreviewed = self.review_refusal(context)
        if unreviewed is not None:
            # FR-15: both sides read one reviewed spec.
            return StepResult(
                status=StepStatus.FAILED,
                error_message=f"a dual run needs a reviewed spec: {unreviewed}",
                started_at=started,
                completed_at=_now_iso(),
            )
        # The run holding the dual run is marked, so its handover never reaches task memory.
        context.run = context.run.model_copy(update={"dual_side": "parent"})
        stem = context.spec_path.stem.replace("_spec", "")
        logger.info("ArbitrateDualPipelineHandler: Starting dual pipeline for component '%s'", stem)

        try:
            # Chosen first: building a side's runner takes its feedback entry out.
            sides = _sides_to_run(context.feedback)
            tasks = {
                side: asyncio.create_task(
                    self._build_runner(pipe, stem, context, step, coder_side=side == "coder").run(
                        parent_run_id=context.run.run_id
                    )
                )
                for side, (pipe, step) in _SIDES.items()
                if side in sides
            }
            await asyncio.wait(tasks.values(), return_when=asyncio.ALL_COMPLETED)
            coding_result = tasks["coder"].result() if "coder" in tasks else _KEPT
            scenario_result = tasks["scenario"].result() if "scenario" in tasks else _KEPT
            # The scenario agent's spec or contract problems are for the person only.
            problems = {"problems": _problems(scenario_result), **models}

            logger.info(
                "ArbitrateDualPipelineHandler: Completed. Coding=%s, Scenario=%s",
                getattr(coding_result, "status", "unknown"),
                getattr(scenario_result, "status", "unknown"),
            )

            if getattr(coding_result, "status", None) not in (StepStatus.PASSED, "completed"):
                return StepResult(
                    status=StepStatus.FAILED,
                    output=problems,
                    error_message=f"Coding pipeline failed: {_why_failed(coding_result)}",
                    started_at=started,
                    completed_at=_now_iso(),
                )

            if getattr(scenario_result, "status", None) not in (StepStatus.PASSED, "completed"):
                return StepResult(
                    status=StepStatus.FAILED,
                    output=problems,
                    error_message=f"Scenario pipeline failed: {_why_failed(scenario_result)}",
                    started_at=started,
                    completed_at=_now_iso(),
                )

            return StepResult(
                status=StepStatus.PASSED,
                output={"component": stem, "status": "dual_completed", **problems},
                started_at=started,
                completed_at=_now_iso(),
            )

        except Exception as exc:
            log_step_failure(
                logger, "ArbitrateDualPipelineHandler: unhandled exception in dual pipeline"
            )
            return _error_result(str(exc), started)

    def _build_runner(
        self,
        pipe_file: str,
        component: str,
        context: RunContext,
        own_step: str,
        coder_side: bool = False,
    ) -> Any:
        pipe = side_pipeline(pipe_file, component, coder_side=coder_side)

        # Each side gets only the arbiter's entry for its own step, taken out of the parent so it
        # reaches that side once: nothing the other side wrote or was told crosses over.
        entry = context.feedback.pop(own_step, None)
        own = {own_step: entry} if entry is not None else {}
        side = "coder" if coder_side else "scenario"
        return context.run.pipeline_runner.spawn(pipe, feedback=own, side=side)
