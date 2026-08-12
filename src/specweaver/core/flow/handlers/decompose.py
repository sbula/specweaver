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
            # INT-US-21 FR-5: derive the feature name from the spec when the step does not name
            # one. The bundled feature_decomposition.yaml passes no params, so the old
            # "unknown_feature" fallback was what every real run got.
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

            # INT-US-21 FR-5/D1: mode="json" is REQUIRED, not stylistic. `model_dump()` leaves
            # `proposed_dal` as a DALLevel enum and ruamel raises RepresenterError on it — and the
            # field is mandatory on every component, so the python-mode dump fails on 100% of real
            # plans. mode="json" also makes this byte-identical to the hydrated
            # `context.plan_context.decomposition`, so the on-disk and in-memory halves of this AD-4-frozen seam
            # agree. Generalised by TECH-016.
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


class OrchestrateComponentsHandler(StepHandler):
    """Executes fan_out on the runner for each mapped component."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:  # noqa: C901
        logger.info("Executing ORCHESTRATE COMPONENTS for %s", context.run.run_id)
        import asyncio
        import graphlib
        import importlib.resources

        import yaml

        from specweaver.commons import json
        from specweaver.core.flow.engine.models import PipelineDefinition

        # INT-US-24 FR-1 (AD-1): "dual_pipeline" mode is a plan-less orchestration —
        # it must branch BEFORE the DecompositionPlan guard below.
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
            # INT-US-21 AD-1: reads plan_context.decomposition, NOT plan_context.plan. The latter is the
            # implementation PlanArtifact consumed by the generation handlers; sharing one field
            # for both concepts was a latent type bug. Populated by the runner's
            # hydrate_plan_context hook after a decompose+feature step passes.
            if not context.plan_context.decomposition:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=(
                        "No DecompositionPlan found in context.plan_context.decomposition — a "
                        "decompose+feature step must run (and pass) earlier in this pipeline."
                    ),
                    started_at="",
                    completed_at="",
                )

            plan_data = json.loads(context.plan_context.decomposition)
            components = plan_data.get("components", [])

            if not components:
                return StepResult(
                    status=StepStatus.PASSED,
                    output={"sub_runs": []},
                    started_at="",
                    completed_at="",
                )

            if not context.run.pipeline_runner:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message="pipeline_runner not found in context. Cannot orchestrate.",
                    started_at="",
                    completed_at="",
                )

            graph: dict[str, set[str]] = {}
            comp_by_name = {}

            for comp in components:
                name = comp.get("component")
                if not name or not COMPONENT_NAME_PATTERN.match(name):
                    return StepResult(
                        status=StepStatus.FAILED,
                        error_message=f"Invalid or malicious component name detected: '{name}'. Aborting fan_out to prevent path traversal.",
                        started_at="",
                        completed_at="",
                    )
                deps = set(comp.get("dependencies", []))
                graph[name] = deps
                comp_by_name[name] = comp

            try:
                sorter = graphlib.TopologicalSorter(graph)
                sorter.prepare()
            except graphlib.CycleError as e:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Circular dependency detected: {e}",
                    started_at="",
                    completed_at="",
                )

            # Preload yaml to avoid I/O in the loop
            files = importlib.resources.files("specweaver.workflows.pipelines")
            resource = files.joinpath("new_feature.yaml")
            base_pipe_yaml = resource.read_text(encoding="utf-8")

            active_tasks: dict[str, asyncio.Task[Any]] = {}
            pending_dispatch: set[str] = set()
            sub_runs = []
            deferred_joins = []
            has_failed = False

            while sorter.is_active():
                for node in sorter.get_ready():
                    pending_dispatch.add(node)

                running_impacts = set()
                for rn in active_tasks:
                    running_impacts.add(rn)
                    if context.graph.topology:
                        for tm in comp_by_name[rn].get("target_modules", []):
                            running_impacts.update(context.graph.topology.impact_of(tm))

                dispatched_this_round = []
                for node in list(pending_dispatch):
                    node_impacts = {node}
                    if context.graph.topology:
                        for tm in comp_by_name[node].get("target_modules", []):
                            node_impacts.update(context.graph.topology.impact_of(tm))

                    if not node_impacts.intersection(running_impacts):
                        pending_dispatch.remove(node)
                        dispatched_this_round.append(node)
                        running_impacts.update(node_impacts)

                        pipe_data = yaml.safe_load(base_pipe_yaml)
                        pipe_data["name"] = f"auto_{node}"
                        valid_steps = []
                        for step_dict in pipe_data.get("steps", []):
                            if "params" not in step_dict:
                                step_dict["params"] = {}
                            step_dict["params"]["component"] = node

                            gate_def = step_dict.get("gate")
                            gate_type = gate_def.get("type") if isinstance(gate_def, dict) else ""

                            if gate_type == "join":
                                deferred_joins.append(step_dict)
                            else:
                                valid_steps.append(step_dict)

                        pipe_data["steps"] = valid_steps
                        pipe = PipelineDefinition(**pipe_data)

                        # We use PipelineRunner.run dynamically
                        from specweaver.core.flow.engine.runner import PipelineRunner

                        isolated_runner = PipelineRunner(
                            pipeline=pipe,
                            context=context.run.pipeline_runner._context,
                            registry=context.run.pipeline_runner._registry,
                            store=context.run.pipeline_runner._store,
                            on_event=context.run.pipeline_runner._on_event,
                        )

                        task = asyncio.create_task(
                            isolated_runner.run(parent_run_id=context.run.run_id)
                        )
                        active_tasks[node] = task

                if active_tasks:
                    done, _ = await asyncio.wait(
                        list(active_tasks.values()), return_when=asyncio.FIRST_COMPLETED
                    )

                    for node, task in list(active_tasks.items()):
                        if task in done:
                            del active_tasks[node]
                            result = task.result()
                            sub_runs.append(result)
                            # Assume any run not evaluating to PASSED or string "completed" is a failure
                            if getattr(result, "status", None) not in (
                                StepStatus.PASSED,
                                "completed",
                            ):
                                has_failed = True
                            else:
                                sorter.done(node)  # Unlocks dependents
                else:
                    if pending_dispatch:
                        return StepResult(
                            status=StepStatus.FAILED,
                            error_message="Deadlock: Components ready but cannot start due to graph/topology collision.",
                            started_at="",
                            completed_at="",
                        )
                    else:
                        break  # Starvation: some nodes failed, dependents cannot start. End DAG execution.

            if has_failed:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Cascading failure: pipeline execution halted for dependent components. Ran {len(sub_runs)} total pipelines.",
                    started_at="",
                    completed_at="",
                )

            if deferred_joins:
                logger.info("Executing Wave N with %d deferred JOIN steps", len(deferred_joins))
                wave_n_pipe = PipelineDefinition(
                    name=f"auto_wave_n_{context.run.run_id}",
                    steps=deferred_joins,
                )

                from specweaver.core.flow.engine.runner import PipelineRunner

                wave_n_runner = PipelineRunner(
                    pipeline=wave_n_pipe,
                    context=context.run.pipeline_runner._context,
                    registry=context.run.pipeline_runner._registry,
                    store=context.run.pipeline_runner._store,
                    on_event=context.run.pipeline_runner._on_event,
                )

                wave_res = await wave_n_runner.run(parent_run_id=context.run.run_id)
                sub_runs.append(wave_res)

                if getattr(wave_res, "status", None) not in (StepStatus.PASSED, "completed"):
                    return StepResult(
                        status=StepStatus.FAILED,
                        error_message=f"Cascading failure: Wave N deferred join execution failed. Ran {len(sub_runs)} total pipelines.",
                        started_at="",
                        completed_at="",
                    )

            return StepResult(
                status=StepStatus.PASSED,
                output={"sub_runs": [getattr(r, "run_id", "unknown") for r in sub_runs]},
                started_at="",
                completed_at="",
            )

        except Exception as e:
            logger.exception("Failed to orchestrate components")
            return StepResult(
                status=StepStatus.ERROR, error_message=str(e), started_at="", completed_at=""
            )
