# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Generation step handlers — code gen, test gen, and plan gen."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow._base import RunContext, _error_result, _now_iso
from specweaver.core.flow._review import _build_tool_dispatcher
from specweaver.core.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.models import PipelineStep
    from specweaver.infrastructure.llm.models import GenerationConfig, TaskType

logger = logging.getLogger(__name__)


def _resolve_generation_routing(
    context: RunContext,
    *,
    temperature: float = 0.2,
    task_type: TaskType | None = None,
) -> tuple[Any, GenerationConfig]:
    """Resolve the adapter and config from RunContext, routing if enabled, else default."""
    from specweaver.infrastructure.llm.models import GenerationConfig
    from specweaver.infrastructure.llm.models import TaskType as _TaskType

    resolved_type = task_type if task_type is not None else _TaskType.IMPLEMENT

    routed = (
        context.llm_router.get_for_task(resolved_type)
        if getattr(context, "llm_router", None)
        else None
    )
    adapter = routed.adapter if routed else context.llm

    if routed:
        config = GenerationConfig(
            model=routed.model,
            temperature=routed.temperature,
            max_output_tokens=routed.max_output_tokens,
            task_type=resolved_type,
            run_id=getattr(context, "run_id", "") or "",
        )
    elif context.config is not None:
        config = GenerationConfig(
            model=context.config.llm.model,
            temperature=temperature,
            max_output_tokens=context.config.llm.max_output_tokens,
            task_type=resolved_type,
            run_id=getattr(context, "run_id", "") or "",
        )
    else:
        # Fallback: no config set (e.g. test harness)
        config = GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=temperature,
            max_output_tokens=4096,
            task_type=resolved_type,
            run_id=getattr(context, "run_id", "") or "",
        )

    return adapter, config


class GenerateCodeHandler:
    """Handler for generate+code — LLM code generation."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            logger.error("GenerateCodeHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for generate steps", started)

        try:
            from specweaver.workflows.implementation.generator import Generator

            adapter, config = _resolve_generation_routing(context, temperature=0.2)
            generator = Generator(llm=adapter, config=config)
            output_dir = context.output_dir or context.project_path / "src"
            output_path = output_dir / f"{context.spec_path.stem.replace('_spec', '')}.py"
            logger.debug(
                "GenerateCodeHandler: generating code to '%s' from spec '%s'",
                output_path,
                context.spec_path.name,
            )

            import uuid

            from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

            parent_id = None
            if context.spec_path.exists():
                parent_id = extract_artifact_uuid(context.spec_path.read_text(encoding="utf-8"))
            if not parent_id:
                parent_id = getattr(context, "run_id", "") or ""

            artifact_uuid = None
            if output_path.exists():
                artifact_uuid = extract_artifact_uuid(output_path.read_text(encoding="utf-8"))
            if not artifact_uuid:
                artifact_uuid = str(uuid.uuid4())

            generated = await generator.generate_code(
                context.spec_path,
                output_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
                plan=context.plan,
                project_metadata=context.project_metadata,
                artifact_uuid=artifact_uuid,
            )
            logger.info("GenerateCodeHandler: code generated at '%s'", generated)

            if getattr(context, "db", None) and hasattr(context.db, "log_artifact_event"):
                context.db.log_artifact_event(
                    artifact_id=artifact_uuid,
                    parent_id=parent_id,
                    run_id=getattr(context, "run_id", "") or "",
                    event_type="generated_code",
                    model_id=config.model,
                )

            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(generated)},
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            logger.exception("GenerateCodeHandler: unhandled exception during code generation")
            return _error_result(str(exc), started)


class GenerateTestsHandler:
    """Handler for generate+tests — LLM test generation."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            logger.error("GenerateTestsHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for generate steps", started)

        try:
            from specweaver.workflows.implementation.generator import Generator

            adapter, config = _resolve_generation_routing(context, temperature=0.2)
            generator = Generator(llm=adapter, config=config)
            output_dir = context.output_dir or context.project_path / "tests"
            output_path = output_dir / f"test_{context.spec_path.stem.replace('_spec', '')}.py"
            logger.debug(
                "GenerateTestsHandler: generating tests to '%s' from spec '%s'",
                output_path,
                context.spec_path.name,
            )

            import uuid

            from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

            parent_id = None
            if context.spec_path.exists():
                parent_id = extract_artifact_uuid(context.spec_path.read_text(encoding="utf-8"))
            if not parent_id:
                parent_id = getattr(context, "run_id", "") or ""

            artifact_uuid = None
            if output_path.exists():
                artifact_uuid = extract_artifact_uuid(output_path.read_text(encoding="utf-8"))
            if not artifact_uuid:
                artifact_uuid = str(uuid.uuid4())

            generated = await generator.generate_tests(
                context.spec_path,
                output_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
                plan=context.plan,
                project_metadata=context.project_metadata,
                artifact_uuid=artifact_uuid,
            )
            logger.info("GenerateTestsHandler: tests generated at '%s'", generated)

            if getattr(context, "db", None) and hasattr(context.db, "log_artifact_event"):
                context.db.log_artifact_event(
                    artifact_id=artifact_uuid,
                    parent_id=parent_id,
                    run_id=getattr(context, "run_id", "") or "",
                    event_type="generated_tests",
                    model_id=config.model,
                )

            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(generated)},
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            logger.exception("GenerateTestsHandler: unhandled exception during test generation")
            return _error_result(str(exc), started)


class PlanSpecHandler:
    """Handler for plan+spec — generates an implementation plan from a spec.

    Uses the Planner to generate a PlanArtifact, then saves it as YAML
    alongside the spec. The plan path is stored in step output for
    downstream consumption via the runner's post-step hook.

    Step params (optional):
        max_retries: int — max reflection retries on JSON validation
            failure (default: 3).
    """

    def _resolve_routing(self, context: RunContext) -> tuple[Any, GenerationConfig]:
        """Resolve adapter and build GenerationConfig for plan, with routing."""
        from specweaver.infrastructure.llm.models import GenerationConfig, TaskType

        routed = (
            context.llm_router.get_for_task(TaskType.PLAN)
            if getattr(context, "llm_router", None)
            else None
        )
        adapter = routed.adapter if routed else context.llm

        if routed:
            config = GenerationConfig(
                model=routed.model,
                temperature=routed.temperature,
                max_output_tokens=routed.max_output_tokens,
                task_type=TaskType.PLAN,
                run_id=getattr(context, "run_id", "") or "",
            )
        elif context.config is not None:
            config = GenerationConfig(
                model=context.config.llm.model,
                temperature=0.3,
                max_output_tokens=context.config.llm.max_output_tokens,
                task_type=TaskType.PLAN,
                run_id=getattr(context, "run_id", "") or "",
            )
        else:
            # Fallback
            config = GenerationConfig(
                model="gemini-3-flash-preview",
                temperature=0.3,
                max_output_tokens=4096,
                task_type=TaskType.PLAN,
                run_id=getattr(context, "run_id", "") or "",
            )

        return adapter, config

    async def _generate_plan_artifact(
        self, planner: Any, context: RunContext, spec_content: str
    ) -> tuple[Path, str, Any]:
        """Helper to generate and save the plan artifact."""
        import io
        import uuid

        from ruamel.yaml import YAML

        from specweaver.infrastructure.llm.lineage import extract_artifact_uuid, wrap_artifact_tag

        try:
            if context.config and hasattr(context.config, "stitch"):
                stitch_mode = context.config.stitch.mode
                stitch_api_key = context.config.stitch.api_key
            else:
                stitch_mode = "off"
                stitch_api_key = ""
        except Exception:
            stitch_mode = "off"
            stitch_api_key = ""

        plan_artifact = await planner.generate_plan(
            spec_content=spec_content,
            spec_path=str(context.spec_path),
            spec_name=context.spec_path.stem.replace("_spec", "").replace("_", " ").title(),
            constitution=context.constitution,
            standards=context.standards,
            stitch_mode=stitch_mode,
            stitch_api_key=stitch_api_key,
            project_metadata=context.project_metadata,
        )

        plan_path = context.spec_path.with_name(context.spec_path.stem + "_plan.yaml")

        artifact_uuid = None
        if plan_path.exists():
            artifact_uuid = extract_artifact_uuid(plan_path.read_text(encoding="utf-8"))
        if not artifact_uuid:
            artifact_uuid = str(uuid.uuid4())

        yaml = YAML()
        yaml.default_flow_style = False
        buf = io.StringIO()
        yaml.dump(plan_artifact.model_dump(), buf)

        content = buf.getvalue()
        tag_str = wrap_artifact_tag(artifact_uuid, "yaml")
        if tag_str:
            content = tag_str + "\n" + content

        plan_path.write_text(content, encoding="utf-8")
        logger.info(
            "PlanSpecHandler: plan saved to '%s' (confidence=%d)",
            plan_path,
            plan_artifact.confidence,
        )
        return plan_path, artifact_uuid, plan_artifact

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            logger.error("PlanSpecHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for plan steps", started)

        if not context.spec_path.exists():
            logger.error("PlanSpecHandler: spec file not found: %s", context.spec_path)
            return _error_result(
                f"Spec file not found: {context.spec_path}",
                started,
            )

        try:
            from specweaver.workflows.planning.planner import Planner

            max_retries: int = step.params.get("max_retries", 3)
            adapter, config = self._resolve_routing(context)
            planner = Planner(
                llm=adapter,
                config=config,
                max_retries=max_retries,
                tool_dispatcher=_build_tool_dispatcher(context, role="implementer"),
            )

            spec_content = context.spec_path.read_text(encoding="utf-8")
            logger.debug(
                "PlanSpecHandler: generating plan for '%s' (max_retries=%d)",
                context.spec_path.name,
                max_retries,
            )

            plan_path, artifact_uuid, plan_artifact = await self._generate_plan_artifact(
                planner, context, spec_content
            )

            from specweaver.infrastructure.llm.lineage import extract_artifact_uuid

            parent_id = None
            if context.spec_path.exists():
                parent_id = extract_artifact_uuid(context.spec_path.read_text(encoding="utf-8"))
            if not parent_id:
                parent_id = getattr(context, "run_id", "") or ""

            if getattr(context, "db", None) and hasattr(context.db, "log_artifact_event"):
                context.db.log_artifact_event(
                    artifact_id=artifact_uuid,
                    parent_id=parent_id,
                    run_id=getattr(context, "run_id", "") or "",
                    event_type="generated_plan",
                    model_id=config.model,
                )

            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "plan_path": str(plan_path),
                    "confidence": plan_artifact.confidence,
                    "file_count": len(plan_artifact.file_layout),
                },
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            logger.exception("PlanSpecHandler: unhandled exception during plan generation")
            return _error_result(str(exc), started)
