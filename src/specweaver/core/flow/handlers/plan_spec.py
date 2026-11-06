# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The plan step (`plan+spec`): an implementation plan from the spec, saved beside it."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.commons.spec_names import module_stem
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.engine.step_outputs import PLAN_PATH
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.handlers.review import _build_tool_dispatcher
from specweaver.core.flow.run_state.failures import log_step_failure

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.run_state.run_context import RunContext
    from specweaver.infrastructure.llm.models import GenerationConfig
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class PlanSpecHandler:
    """Handler for plan+spec — generates an implementation plan from a spec.

    Uses the Planner to generate a PlanArtifact, then saves it as YAML
    alongside the spec. The plan path is stored in step output for
    downstream consumption via the runner's post-step hook.

    Step params (optional):
        max_retries: int — max reflection retries on JSON validation
            failure (default: 3).
    """

    def _resolve_routing(
        self, context: RunContext, step: PipelineStep
    ) -> tuple[Any, GenerationConfig]:
        """The adapter and settings for planning."""
        from specweaver.core.flow.handlers._llm import llm_for_step

        return llm_for_step(context, step)

    async def _generate_plan_artifact(
        self, planner: Any, context: RunContext, spec_content: str, base_prompt: PromptBuilder
    ) -> tuple[Path, str, Any]:
        import io

        from ruamel.yaml import YAML

        from specweaver.commons.lineage import tag_content
        from specweaver.core.flow.handlers.artifact_lineage import derive_artifact_uuid

        plan_artifact = await planner.generate_plan(
            spec_content=spec_content,
            spec_path=str(context.spec_path),
            spec_name=module_stem(context.spec_path).replace("_", " ").title(),
            base_prompt=base_prompt,
        )

        plan_path = context.spec_path.with_name(context.spec_path.stem + "_plan.yaml")

        artifact_uuid = derive_artifact_uuid(plan_path)

        yaml = YAML()
        yaml.default_flow_style = False
        buf = io.StringIO()
        yaml.dump(plan_artifact.model_dump(mode="json"), buf)

        content = tag_content(buf.getvalue(), artifact_uuid, "yaml")

        plan_path.write_text(content, encoding="utf-8")
        logger.info(
            "PlanSpecHandler: plan saved to '%s' (confidence=%d)",
            plan_path,
            plan_artifact.confidence,
        )
        return plan_path, artifact_uuid, plan_artifact

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        if context.model.llm_router is None:
            logger.error("PlanSpecHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for plan steps", started)

        if not context.spec_path.exists():
            logger.error("PlanSpecHandler: spec file not found: %s", context.spec_path)
            return _error_result(
                f"Spec file not found: {context.spec_path}",
                started,
            )

        try:
            from specweaver.core.flow.engine.run_profile import run_task_files
            from specweaver.workflows.implementation.languages import language_guide
            from specweaver.workflows.planning.planner import Planner

            max_retries: int = step.params.get("max_retries", 3)
            adapter, config = self._resolve_routing(context, step)
            language = run_task_files(context).language
            planner = Planner(
                llm=adapter,
                config=config,
                language=language_guide(language, context.project_path).name,
                max_retries=max_retries,
                tool_dispatcher=_build_tool_dispatcher(context, role="planner", adapter=adapter),
            )

            spec_content = context.spec_path.read_text(encoding="utf-8")
            logger.debug(
                "PlanSpecHandler: generating plan for '%s' (max_retries=%d)",
                context.spec_path.name,
                max_retries,
            )

            from specweaver.core.flow.handlers._profiles import FULL, resolve_profile
            from specweaver.core.flow.handlers.base import _build_base_prompt

            # Note: Planner defines its own instruction string internally, so we don't pass one here
            # (or we could extract it later). For now pass empty string or planner specific.
            # Planner currently uses PLAN_GENERATION_INSTRUCTIONS which is inside planner.py.
            # Let's import it.
            from specweaver.workflows.planning.planner import PLAN_GENERATION_INSTRUCTIONS

            try:
                profile = resolve_profile(step.params.get("render_profile"), default=FULL)
            except ValueError as e:
                return _error_result(str(e), started)

            base_prompt = await _build_base_prompt(
                context, PLAN_GENERATION_INSTRUCTIONS, profile=profile, skeleton_files=None
            )

            plan_path, artifact_uuid, plan_artifact = await self._generate_plan_artifact(
                planner, context, spec_content, base_prompt
            )

            from specweaver.commons.lineage import extract_artifact_uuid

            parent_id = None
            if context.spec_path.exists():
                parent_id = extract_artifact_uuid(context.spec_path.read_text(encoding="utf-8"))
            if not parent_id:
                parent_id = context.run.run_id or ""

            from specweaver.core.flow.handlers.artifact_lineage import log_artifact_lineage

            await log_artifact_lineage(
                context, artifact_uuid, "generated_plan", parent_id=parent_id, model_id=config.model
            )

            return StepResult(
                status=StepStatus.PASSED,
                output={
                    PLAN_PATH: str(plan_path),
                    "confidence": plan_artifact.confidence,
                    "file_count": len(plan_artifact.file_layout),
                },
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            log_step_failure(logger, "PlanSpecHandler: unhandled exception during plan generation")
            return _error_result(str(exc), started)
