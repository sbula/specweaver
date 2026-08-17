# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Handlers for Feature Decomposition and Component Orchestration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.hydration import DECOMPOSITION_PLAN_KEY
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import StepHandler, _error_result, _now_iso
from specweaver.core.flow.handlers.decomposition_artifacts import (
    COMPONENT_NAME_PATTERN,
    build_dal_summary,
    feature_name_from_spec,
    log_decomposition_lineage,
    persist_decomposition,
    write_component_stubs,
)
from specweaver.workflows.planning.decomposer import FeatureDecomposer

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


class DecomposeFeatureHandler(StepHandler):
    """Generates the DecompositionPlan via FeatureDecomposer."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.info("Executing DECOMPOSE FEATURE for %s", context.run.run_id)
        started = _now_iso()

        try:
            # Derive the feature name from the spec when the step does not name one. The bundled
            # feature_decomposition.yaml passes no params, so an "unknown_feature" fallback is what
            # every real run would get.
            feature_name = step.params.get("feature_name") or feature_name_from_spec(
                context.spec_path
            )

            # Use the LLM and the Decomposer
            decomposer = FeatureDecomposer(
                llm=context.model.llm, context_provider=context.context_provider
            )

            # Read spec content if exists
            spec_content = ""
            if context.spec_path.exists():
                spec_content = context.spec_path.read_text(encoding="utf-8")

            from specweaver.core.flow.handlers._profiles import MINIMAL, resolve_profile
            from specweaver.core.flow.handlers.base import _build_base_prompt

            try:
                profile = resolve_profile(step.params.get("render_profile"), default=MINIMAL)
            except ValueError as e:
                return _error_result(str(e), started)

            base_prompt = await _build_base_prompt(context, instructions="", profile=profile)

            plan = await decomposer.decompose(
                feature_name=feature_name,
                spec_content=spec_content,
                base_prompt=base_prompt,
                topology_contexts=[context.graph.topology] if context.graph.topology else None,
            )

            # FR-5 Coverage Assertion Bounds
            if plan.coverage_score < 1.0:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Coverage Assert Failed: Coverage score {plan.coverage_score} is below 1.0 threshold.",
                    started_at=context.project_metadata.date_iso
                    if context.project_metadata
                    else "",
                    completed_at="",  # Runner will fill
                )

            # mode="json" is REQUIRED, not stylistic. `model_dump()` leaves
            # `proposed_dal` as a DALLevel enum and ruamel raises RepresenterError on it — and the
            # field is mandatory on every component, so the python-mode dump fails on 100% of real
            # plans. mode="json" also makes this byte-identical to the hydrated
            # `context.plan_context.decomposition`, so the on-disk and in-memory halves of this
            # frozen seam agree.
            dumped = plan.model_dump(mode="json")
            started_at = context.project_metadata.date_iso if context.project_metadata else ""

            try:
                artifact_path, artifact_uuid = persist_decomposition(dumped, context)
            except OSError as exc:
                # D6: fail loud, but never discard an expensive LLM decomposition — keeping the
                # plan in `output` lets a resume re-persist without another LLM round.
                logger.exception("Failed to persist the decomposition artifact")
                return StepResult(
                    status=StepStatus.FAILED,
                    output={DECOMPOSITION_PLAN_KEY: dumped},
                    error_message=f"Failed to write the decomposition artifact: {exc}",
                    started_at=started_at,
                    completed_at=_now_iso(),
                )

            await log_decomposition_lineage(context, artifact_uuid)
            component_specs = write_component_stubs(dumped, context, feature_name)
            summary = build_dal_summary(dumped, artifact_path, component_specs)

            # The plan is NESTED so `decomposition_path` cannot leak into the frozen seam:
            # `hydrate_plan_context` unwraps `output["plan"]`, keeping `plan_context.decomposition`
            # canonical DecompositionPlan JSON (AD-4).
            return StepResult(
                status=StepStatus.PASSED,
                output={
                    DECOMPOSITION_PLAN_KEY: dumped,
                    "decomposition_path": str(artifact_path),
                    "component_specs": component_specs,
                    "summary": summary,
                },
                started_at=started_at,
                completed_at="",
                artifact_uuid=artifact_uuid,
            )

        except Exception as e:
            logger.exception("Failed to decompose feature")
            return StepResult(
                status=StepStatus.ERROR,
                error_message=str(e),
                started_at="",
                completed_at="",
            )


class _OrchestrationRefusedError(Exception):
    """A condition that stops the fan-out with a FAILED result rather than an ERROR.

    `execute` otherwise needs **seven** early `return StepResult(FAILED, ...)` sites, each one a
    branch — a large share of its complexity is then the shape of reporting failure rather than the
    orchestration itself. Raising lets the steps below read as a straight line and keeps every
    message and status identical, because `execute` converts this back into the same
    `StepResult` the inline returns produced.

    Distinct from the bare `Exception` handler, which reports ERROR: these are *expected* refusals
    (a bad component name, a dependency cycle, a failed sub-run), not crashes.
    """


def _failed(message: str) -> StepResult:
    return StepResult(
        status=StepStatus.FAILED, error_message=message, started_at="", completed_at=""
    )


def _components_of(context: RunContext) -> list[dict[str, Any]]:
    """The decomposition plan's components, or a refusal explaining what is missing."""
    # Reads plan_context.decomposition, NOT plan_context.plan. The latter is the implementation
    # PlanArtifact consumed by the generation handlers; one field for both concepts is a type bug
    # waiting to happen. Populated by the runner's hydrate_plan_context hook after a
    # decompose+feature step passes.
    if not context.plan_context.decomposition:
        raise _OrchestrationRefusedError(
            "No DecompositionPlan found in context.plan_context.decomposition — a "
            "decompose+feature step must run (and pass) earlier in this pipeline."
        )

    from specweaver.commons import json

    plan_data = json.loads(context.plan_context.decomposition)
    return list(plan_data.get("components", []))


def _dependency_graph(
    components: list[dict[str, Any]],
) -> tuple[dict[str, set[str]], dict[str, dict[str, Any]]]:
    """Validate every component name, then map each to its declared dependencies."""
    graph: dict[str, set[str]] = {}
    comp_by_name: dict[str, dict[str, Any]] = {}
    for comp in components:
        name = comp.get("component")
        if not name or not COMPONENT_NAME_PATTERN.match(name):
            raise _OrchestrationRefusedError(
                f"Invalid or malicious component name detected: '{name}'. "
                "Aborting fan_out to prevent path traversal."
            )
        graph[name] = set(comp.get("dependencies", []))
        comp_by_name[name] = comp
    return graph, comp_by_name


def _prepared_sorter(graph: dict[str, set[str]]) -> Any:
    """A prepared topological sorter, or a refusal naming the cycle."""
    import graphlib

    try:
        sorter = graphlib.TopologicalSorter(graph)
        sorter.prepare()
    except graphlib.CycleError as exc:
        raise _OrchestrationRefusedError(f"Circular dependency detected: {exc}") from exc
    return sorter


def _base_pipeline_yaml() -> str:
    """The template every component's sub-pipeline is built from. Read once, not per node."""
    import importlib.resources

    files = importlib.resources.files("specweaver.workflows.pipelines")
    return str(files.joinpath("new_feature.yaml").read_text(encoding="utf-8"))


def _component_pipeline(node: str, base_pipe_yaml: str, deferred_joins: list[Any]) -> Any:
    """Build one component's sub-pipeline, siphoning its `join` gates into Wave N.

    A `join` step cannot run inside a per-component pipeline — it exists to wait for all of them —
    so it is collected here and run once at the end.
    """
    import yaml

    from specweaver.core.flow.engine.models import PipelineDefinition

    pipe_data = yaml.safe_load(base_pipe_yaml)
    pipe_data["name"] = f"auto_{node}"
    valid_steps = []
    for step_dict in pipe_data.get("steps", []):
        step_dict.setdefault("params", {})
        step_dict["params"]["component"] = node

        gate_def = step_dict.get("gate")
        gate_type = gate_def.get("type") if isinstance(gate_def, dict) else ""
        if gate_type == "join":
            deferred_joins.append(step_dict)
        else:
            valid_steps.append(step_dict)

    pipe_data["steps"] = valid_steps
    return PipelineDefinition(**pipe_data)


def _impacts_of(
    node: str, comp_by_name: dict[str, dict[str, Any]], context: RunContext
) -> set[str]:
    """A node plus everything the knowledge graph says its target modules reach."""
    impacts = {node}
    if context.graph.topology:
        for target_module in comp_by_name[node].get("target_modules", []):
            impacts.update(context.graph.topology.impact_of(target_module))
    return impacts


def _succeeded(result: Any) -> bool:
    """Anything not PASSED (or the legacy string "completed") is a failure."""
    return getattr(result, "status", None) in (StepStatus.PASSED, "completed")


class _Fanout:
    """The mutable state one fan-out carries across its dispatch rounds."""

    def __init__(self) -> None:
        self.active: dict[str, Any] = {}
        self.pending: set[str] = set()
        self.sub_runs: list[Any] = []
        self.deferred_joins: list[Any] = []
        self.has_failed = False


def _dispatch_ready(
    state: _Fanout,
    sorter: Any,
    comp_by_name: dict[str, dict[str, Any]],
    context: RunContext,
    base_pipe_yaml: str,
) -> None:
    """Start every pending component whose impact set does not collide with a running one."""
    import asyncio

    for node in sorter.get_ready():
        state.pending.add(node)

    running_impacts: set[str] = set()
    for running in state.active:
        running_impacts.update(_impacts_of(running, comp_by_name, context))

    for node in list(state.pending):
        node_impacts = _impacts_of(node, comp_by_name, context)
        if node_impacts.intersection(running_impacts):
            continue
        state.pending.remove(node)
        running_impacts.update(node_impacts)

        pipe = _component_pipeline(node, base_pipe_yaml, state.deferred_joins)
        runner = context.run.pipeline_runner.spawn(pipe)
        state.active[node] = asyncio.create_task(runner.run(parent_run_id=context.run.run_id))


async def _harvest_finished(state: _Fanout, sorter: Any) -> None:
    """Wait for at least one sub-run, record it, and unlock its dependents if it passed."""
    import asyncio

    done, _ = await asyncio.wait(list(state.active.values()), return_when=asyncio.FIRST_COMPLETED)

    for node, task in list(state.active.items()):
        if task not in done:
            continue
        del state.active[node]
        result = task.result()
        state.sub_runs.append(result)
        if _succeeded(result):
            sorter.done(node)  # unlocks dependents
        else:
            state.has_failed = True


async def _run_dag(
    context: RunContext,
    sorter: Any,
    comp_by_name: dict[str, dict[str, Any]],
    base_pipe_yaml: str,
    state: _Fanout,
) -> None:
    """Dispatch and harvest until the graph is exhausted, starved, or deadlocked."""
    while sorter.is_active():
        _dispatch_ready(state, sorter, comp_by_name, context, base_pipe_yaml)

        if state.active:
            await _harvest_finished(state, sorter)
        elif state.pending:
            raise _OrchestrationRefusedError(
                "Deadlock: Components ready but cannot start due to graph/topology collision."
            )
        else:
            # Starvation: some nodes failed, so their dependents can never start.
            break


async def _run_wave_n(context: RunContext, state: _Fanout) -> None:
    """Run the `join` steps siphoned out of every component pipeline, once, at the end."""
    if not state.deferred_joins:
        return

    from specweaver.core.flow.engine.models import PipelineDefinition

    logger.info("Executing Wave N with %d deferred JOIN steps", len(state.deferred_joins))
    wave_n_pipe = PipelineDefinition(
        name=f"auto_wave_n_{context.run.run_id}", steps=state.deferred_joins
    )
    result = await context.run.pipeline_runner.spawn(wave_n_pipe).run(
        parent_run_id=context.run.run_id
    )
    state.sub_runs.append(result)

    if not _succeeded(result):
        raise _OrchestrationRefusedError(
            "Cascading failure: Wave N deferred join execution failed. "
            f"Ran {len(state.sub_runs)} total pipelines."
        )


class OrchestrateComponentsHandler(StepHandler):
    """Executes fan_out on the runner for each mapped component."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.info("Executing ORCHESTRATE COMPONENTS for %s", context.run.run_id)

        # "dual_pipeline" mode is a plan-less orchestration — it must branch
        # BEFORE the DecompositionPlan guard below.
        mode = step.params.get("mode")
        if mode == "dual_pipeline":
            from specweaver.core.flow.handlers.dual_pipeline import ArbitrateDualPipelineHandler

            logger.info("OrchestrateComponentsHandler: delegating to dual-pipeline mode")
            return await ArbitrateDualPipelineHandler().execute(step, context)
        if mode is not None:
            logger.warning(
                "OrchestrateComponentsHandler: unrecognized orchestrate mode %r — "
                "falling back to decomposition-plan orchestration",
                mode,
            )

        try:
            return await self._orchestrate(context)
        except _OrchestrationRefusedError as refusal:
            return _failed(str(refusal))
        except Exception as exc:
            logger.exception("Failed to orchestrate components")
            return StepResult(
                status=StepStatus.ERROR, error_message=str(exc), started_at="", completed_at=""
            )

    async def _orchestrate(self, context: RunContext) -> StepResult:
        """The fan-out proper: build the graph, run it, then run Wave N."""
        components = _components_of(context)
        if not components:
            return StepResult(
                status=StepStatus.PASSED, output={"sub_runs": []}, started_at="", completed_at=""
            )

        if not context.run.pipeline_runner:
            raise _OrchestrationRefusedError(
                "pipeline_runner not found in context. Cannot orchestrate."
            )

        graph, comp_by_name = _dependency_graph(components)
        sorter = _prepared_sorter(graph)
        state = _Fanout()

        await _run_dag(context, sorter, comp_by_name, _base_pipeline_yaml(), state)

        if state.has_failed:
            raise _OrchestrationRefusedError(
                "Cascading failure: pipeline execution halted for dependent components. "
                f"Ran {len(state.sub_runs)} total pipelines."
            )

        await _run_wave_n(context, state)

        return StepResult(
            status=StepStatus.PASSED,
            output={"sub_runs": [getattr(r, "run_id", "unknown") for r in state.sub_runs]},
            started_at="",
            completed_at="",
        )
