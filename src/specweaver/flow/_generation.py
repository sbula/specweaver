# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Generation step handlers — code gen, test gen, and plan gen."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.flow._base import RunContext, _error_result, _now_iso
from specweaver.flow._review import _build_tool_dispatcher
from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.flow.models import PipelineStep
    from specweaver.llm.models import GenerationConfig, TaskType

logger = logging.getLogger(__name__)


def _gen_config_from_context(
    context: RunContext, *, temperature: float = 0.2,
    task_type: TaskType | None = None,
) -> GenerationConfig:
    """Build GenerationConfig from RunContext, falling back to defaults."""
    from specweaver.llm.models import GenerationConfig, TaskType as _TaskType

    resolved_type = task_type if task_type is not None else _TaskType.IMPLEMENT

    if context.config is not None:
        return GenerationConfig(
            model=context.config.llm.model,
            temperature=temperature,
            max_output_tokens=context.config.llm.max_output_tokens,
            task_type=resolved_type,
        )
    # Fallback: no config set (e.g. test harness)
    return GenerationConfig(
        model="gemini-3-flash-preview",
        temperature=temperature,
        max_output_tokens=4096,
        task_type=resolved_type,
    )


class GenerateCodeHandler:
    """Handler for generate+code — LLM code generation."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            logger.error("GenerateCodeHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for generate steps", started)

        try:
            from specweaver.implementation.generator import Generator

            generator = Generator(
                llm=context.llm,
                config=_gen_config_from_context(context, temperature=0.2),
            )
            output_dir = context.output_dir or context.project_path / "src"
            output_path = output_dir / f"{context.spec_path.stem.replace('_spec', '')}.py"
            logger.debug("GenerateCodeHandler: generating code to '%s' from spec '%s'", output_path, context.spec_path.name)

            generated = await generator.generate_code(
                context.spec_path,
                output_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
                plan=context.plan,
            )
            logger.info("GenerateCodeHandler: code generated at '%s'", generated)
            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(generated)},
                started_at=started,
                completed_at=_now_iso(),
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
            from specweaver.implementation.generator import Generator

            generator = Generator(
                llm=context.llm,
                config=_gen_config_from_context(context, temperature=0.2),
            )
            output_dir = context.output_dir or context.project_path / "tests"
            output_path = output_dir / f"test_{context.spec_path.stem.replace('_spec', '')}.py"
            logger.debug("GenerateTestsHandler: generating tests to '%s' from spec '%s'", output_path, context.spec_path.name)

            generated = await generator.generate_tests(
                context.spec_path,
                output_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
                plan=context.plan,
            )
            logger.info("GenerateTestsHandler: tests generated at '%s'", generated)
            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(generated)},
                started_at=started,
                completed_at=_now_iso(),
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

    def _build_config(self, context: RunContext) -> GenerationConfig:
        """Build GenerationConfig from RunContext, falling back to defaults."""
        from specweaver.llm.models import GenerationConfig, TaskType

        if context.config is not None:
            return GenerationConfig(
                model=context.config.llm.model,
                temperature=0.3,
                max_output_tokens=context.config.llm.max_output_tokens,
                task_type=TaskType.PLAN,
            )
        # Fallback: no config set (e.g. test harness)
        return GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=0.3,
            max_output_tokens=4096,
            task_type=TaskType.PLAN,
        )

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            logger.error("PlanSpecHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for plan steps", started)

        if not context.spec_path.exists():
            logger.error("PlanSpecHandler: spec file not found: %s", context.spec_path)
            return _error_result(
                f"Spec file not found: {context.spec_path}", started,
            )

        try:
            from specweaver.planning.planner import Planner

            max_retries: int = step.params.get("max_retries", 3)
            planner = Planner(
                llm=context.llm,
                config=self._build_config(context),
                max_retries=max_retries,
                tool_dispatcher=_build_tool_dispatcher(context, role="implementer"),
            )

            spec_content = context.spec_path.read_text(encoding="utf-8")
            logger.debug(
                "PlanSpecHandler: generating plan for '%s' (max_retries=%d)",
                context.spec_path.name, max_retries,
            )


            try:
                from specweaver.cli._core import get_db
                from specweaver.config.settings import load_settings

                db = get_db()
                settings = load_settings(db, context.project_path.name)
                stitch_mode = settings.stitch.mode
                stitch_api_key = settings.stitch.api_key
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
            )

            # Save plan YAML alongside the spec
            plan_path = context.spec_path.with_name(
                context.spec_path.stem + "_plan.yaml",
            )
            import io

            from ruamel.yaml import YAML

            yaml = YAML()
            yaml.default_flow_style = False
            buf = io.StringIO()
            yaml.dump(plan_artifact.model_dump(), buf)
            plan_path.write_text(buf.getvalue(), encoding="utf-8")
            logger.info("PlanSpecHandler: plan saved to '%s' (confidence=%d)", plan_path, plan_artifact.confidence)

            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "plan_path": str(plan_path),
                    "confidence": plan_artifact.confidence,
                    "file_count": len(plan_artifact.file_layout),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("PlanSpecHandler: unhandled exception during plan generation")
            return _error_result(str(exc), started)
