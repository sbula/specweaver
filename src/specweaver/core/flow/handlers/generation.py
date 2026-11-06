# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Generation step handlers — code and tests. The plan (`plan_spec`) and the contract (`contract`)
have modules of their own."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from specweaver.commons.lineage import extract_artifact_uuid
from specweaver.commons.spec_names import module_stem
from specweaver.core.flow.engine.autonomy import ExecutionMode, resolve_execution_mode
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.engine.step_outputs import FILES_TOUCHED, RESULTS, touched
from specweaver.core.flow.handlers.agentic_coder import declare_rust_module, run_coder
from specweaver.core.flow.handlers.artifact_lineage import (
    derive_artifact_uuid,
    log_artifact_lineage,
)
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.handlers.mcp_assembler import evaluate_and_fetch_mcp_context
from specweaver.core.flow.run_state.failures import log_step_failure
from specweaver.core.flow.run_state.feedback import pop_findings

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.run_state.run_context import RunContext
    from specweaver.infrastructure.llm.models import GenerationConfig
    from specweaver.workflows.implementation.frameworks import FrameworkChoice
    from specweaver.workflows.implementation.languages import LanguageGuide
    from specweaver.workflows.implementation.task_files import TaskFiles

logger = logging.getLogger(__name__)


def _resolve_generation_routing(
    context: RunContext, step: PipelineStep
) -> tuple[Any, GenerationConfig]:
    """The adapter and settings for a generation step, in the role the step table gives it."""
    from specweaver.core.flow.handlers._llm import llm_for_step

    return llm_for_step(context, step)


def _extract_prompt_feedback(
    context: RunContext, step: PipelineStep
) -> tuple[list[str] | None, str | None]:
    """Extract dictator overrides and validation findings from loop-back feedback and clear it.

    The pop is a guard clause rather than a fourth level of nesting, so each half of the return
    reads on its own.
    """
    findings = pop_findings(context, step.name)
    if findings is None:
        return None, None

    overrides = (
        [findings["remarks"]]
        if findings.get("hitl_verdict") == "reject" and "remarks" in findings
        else None
    )

    fails = [r for r in findings.get(RESULTS, []) if r.get("status") == "FAIL"]
    validation = (
        "\n".join(f"[{r.get('rule_id', 'UNKNOWN')}] {r.get('message', '')}" for r in fails)
        if fails
        else None
    )

    return overrides, validation


class _GenerationHandler:
    """Generate one artefact from a spec with the LLM, then record its lineage.

    `GenerateCodeHandler` and `GenerateTestsHandler` share these eighty lines and differ in six
    places, five of them data — where the file goes, what it is called, which instructions the
    prompt carries, which generator method runs, and which lineage event is emitted. The sixth is
    `INCLUDE_TRACEBACK`, and it stays a flag rather than being unified because it
    changes what a failing step reports; see there.
    """

    #: Directory under the project root when the run does not supply one.
    OUTPUT_SUBDIR: ClassVar[str]
    #: Lineage event recorded for the artefact this handler writes.
    EVENT_TYPE: ClassVar[str]
    #: What the log lines call the thing being produced.
    ARTEFACT: ClassVar[str]
    #: Whether a crash appends its traceback to the step's error message.
    #:
    #: The code handler does and the tests handler does not. That looks like drift rather than a
    #: decision -- these two were otherwise the same method -- but it changes what a failed run
    #: shows the user, so it is preserved as a flag rather than quietly unified.
    INCLUDE_TRACEBACK: ClassVar[bool] = False

    #: Which section of the language and framework files this artefact takes.
    SECTION: ClassVar[str]

    def _instructions(self, guide: LanguageGuide, framework: FrameworkChoice | None) -> str:
        """The language's instructions for this artefact, then the framework's, if any."""
        text = str(getattr(guide, self.SECTION))
        if framework is None:
            return text
        return f"{text}\n\n{getattr(framework.guide, self.SECTION)}"

    async def _generate(self, generator: Any, spec_path: Path, output_path: Path, **kw: Any) -> Any:
        """Invoke the generator method for this artefact."""
        raise NotImplementedError

    def _files(self, context: RunContext) -> TaskFiles:
        from specweaver.core.flow.engine.run_profile import run_task_files

        return run_task_files(context)

    def _output_path(self, context: RunContext) -> Path:
        """Where this step writes: the task's file. Python code alone keeps a run's `output_dir`;
        tests always go where the merge and `run_tests` look for them."""
        files = self._files(context)
        if self.OUTPUT_SUBDIR != "src":
            return context.project_path / files.tests
        if files.code.endswith(".py") and context.output_dir is not None:
            return context.output_dir / f"{module_stem(context.spec_path)}.py"
        return context.project_path / files.code

    def _extra_files(self, context: RunContext) -> list[str]:
        """Files the code step may also change: Rust's module declaration."""
        return list(self._files(context).extra) if self.OUTPUT_SUBDIR == "src" else []

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        name = type(self).__name__
        if context.model.llm_router is None:
            logger.error("%s: LLM adapter required but not configured", name)
            return _error_result("LLM adapter required for generate steps", started)

        try:
            from specweaver.core.flow.engine.run_profile import run_profile
            from specweaver.workflows.implementation.frameworks import project_framework
            from specweaver.workflows.implementation.generator import Generator
            from specweaver.workflows.implementation.languages import language_guide
            from specweaver.workflows.implementation.task_files import task_brief

            files = self._files(context)
            guide = language_guide(files.language, context.project_path)
            framework = project_framework(
                context.project_path,
                context.project_path / files.code,
                files.language,
                run_profile(context).framework,
            )
            adapter, config = _resolve_generation_routing(context, step)
            generator = Generator(llm=adapter, config=config, guide=guide)

            output_path = self._output_path(context)
            logger.debug(
                "%s: generating %s to '%s' from spec '%s'",
                name,
                self.ARTEFACT,
                output_path,
                context.spec_path.name,
            )

            parent_id = _spec_lineage_id(context)
            artifact_uuid = derive_artifact_uuid(output_path)

            dictator_overrides, validation_findings = _extract_prompt_feedback(context, step)
            mcp_env = await evaluate_and_fetch_mcp_context(context)

            try:
                base_prompt = await _generation_prompt(
                    context, step, instructions=self._instructions(guide, framework)
                )
            except ValueError as e:
                return _error_result(str(e), started)

            prompt_parts = {
                "artifact_uuid": artifact_uuid,
                "dictator_overrides": dictator_overrides,
                "validation_findings": validation_findings,
                "environment_context": mcp_env,
                "language": files.language,
                "brief": task_brief(files, context.project_path),
            }
            decision = resolve_execution_mode(step, context)
            if decision.mode is ExecutionMode.AGENTIC:
                refused = await run_coder(
                    step,
                    context,
                    output_path,
                    self._extra_files(context),
                    adapter,
                    config,
                    base_prompt,
                    prompt_parts,
                    role=guide.coder_role,
                )
                if refused:
                    return _failed_result(refused, started)
                generated = output_path
            else:
                generated = await self._generate(
                    generator,
                    context.spec_path,
                    output_path,
                    base_prompt=base_prompt,
                    **prompt_parts,
                )
            logger.info("%s: %s generated at '%s'", name, self.ARTEFACT, generated)
            if self.OUTPUT_SUBDIR == "src" and files.language == "rust":
                declare_rust_module(context.project_path, files)

            await log_artifact_lineage(
                context,
                artifact_uuid,
                self.EVENT_TYPE,
                parent_id=parent_id,
                model_id=config.model,
            )

            output: dict[str, Any] = {
                "generated_path": str(generated),
                FILES_TOUCHED: touched(output_path, context.project_path),
            }
            if decision.reason:
                output["agentic_refused"] = decision.reason
            return StepResult(
                status=StepStatus.PASSED,
                output=output,
                started_at=started,
                completed_at=_now_iso(),
                artifact_uuid=artifact_uuid,
            )
        except Exception as exc:
            log_step_failure(
                logger, "%s: unhandled exception during %s generation", name, self.ARTEFACT
            )
            detail = str(exc)
            if self.INCLUDE_TRACEBACK:
                import traceback

                detail += "\n" + traceback.format_exc()
            return _error_result(detail, started)


def _failed_result(message: str, started: str) -> StepResult:
    return StepResult(
        status=StepStatus.FAILED, error_message=message, started_at=started, completed_at=_now_iso()
    )


def _spec_lineage_id(context: RunContext) -> str:
    """The spec's artifact uuid, falling back to the run id when the spec carries none."""
    if context.spec_path.exists():
        parent_id = extract_artifact_uuid(context.spec_path.read_text(encoding="utf-8"))
        if parent_id:
            return parent_id
    return context.run.run_id or ""


async def _generation_prompt(context: RunContext, step: PipelineStep, *, instructions: str) -> Any:
    """The prompt both generators build: base + skeletons + plan + topology.

    Raises `ValueError` when the step names a render profile that does not exist -- the caller
    turns that into an error result rather than a crash.
    """
    from specweaver.core.flow.handlers._profiles import FULL, resolve_profile
    from specweaver.core.flow.handlers.base import _build_base_prompt
    from specweaver.core.flow.handlers.skeleton_assembler import evaluate_and_fetch_skeleton_context

    targets = list(context.graph.api_contract_paths or [])
    s_files = await asyncio.to_thread(evaluate_and_fetch_skeleton_context, context, targets)

    profile = resolve_profile(step.params.get("render_profile"), default=FULL)
    base_prompt = await _build_base_prompt(
        context, instructions, profile=profile, skeleton_files=s_files
    )
    if context.plan_context.plan:
        base_prompt.add_plan(context.plan_context.plan)
    if context.graph.topology:
        base_prompt.add_topology([context.graph.topology])
    return base_prompt


class GenerateCodeHandler(_GenerationHandler):
    """Handler for generate+code — LLM code generation."""

    OUTPUT_SUBDIR: ClassVar[str] = "src"
    EVENT_TYPE: ClassVar[str] = "generated_code"
    ARTEFACT: ClassVar[str] = "code"
    INCLUDE_TRACEBACK: ClassVar[bool] = True
    SECTION: ClassVar[str] = "code"

    async def _generate(self, generator: Any, spec_path: Path, output_path: Path, **kw: Any) -> Any:
        return await generator.generate_code(spec_path, output_path, **kw)


class GenerateTestsHandler(_GenerationHandler):
    """Handler for generate+tests — LLM test generation."""

    OUTPUT_SUBDIR: ClassVar[str] = "tests"
    EVENT_TYPE: ClassVar[str] = "generated_tests"
    ARTEFACT: ClassVar[str] = "tests"
    SECTION: ClassVar[str] = "tests"

    async def _generate(self, generator: Any, spec_path: Path, output_path: Path, **kw: Any) -> Any:
        return await generator.generate_tests(spec_path, output_path, **kw)
