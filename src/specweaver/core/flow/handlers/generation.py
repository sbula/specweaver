# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Generation step handlers — code gen, test gen, and plan gen."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, ClassVar

from specweaver.commons.lineage import extract_artifact_uuid
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.artifact_lineage import (
    derive_artifact_uuid,
    log_artifact_lineage,
)
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.handlers.mcp_assembler import evaluate_and_fetch_mcp_context
from specweaver.core.flow.handlers.review import _build_tool_dispatcher

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.infrastructure.llm.models import GenerationConfig, TaskType
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

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
        context.model.llm_router.get_for_task(resolved_type) if context.model.llm_router else None
    )
    adapter = routed.adapter if routed else context.model.llm

    if routed:
        config = GenerationConfig(
            model=routed.model,
            temperature=routed.temperature,
            max_output_tokens=routed.max_output_tokens,
            task_type=resolved_type,
            run_id=context.run.run_id or "",
        )
    elif context.model.config is not None:
        config = GenerationConfig(
            model=context.model.config.llm.model,
            temperature=temperature,
            max_output_tokens=context.model.config.llm.max_output_tokens,
            task_type=resolved_type,
            run_id=context.run.run_id or "",
        )
    else:
        # Fallback: no config set (e.g. test harness)
        config = GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=temperature,
            max_output_tokens=4096,
            task_type=resolved_type,
            run_id=context.run.run_id or "",
        )

    return adapter, config


def _pop_findings(context: RunContext, step: PipelineStep) -> dict[str, Any] | None:
    """This step's loop-back findings, consumed exactly once. None when there are none.

    Popping is the point: feedback that is not cleared sticks across retries, so the next attempt
    re-applies a previous round's overrides.
    """
    if not (hasattr(context, "feedback") and context.feedback):
        return None
    step_feedback = context.feedback.pop(step.name, None)
    if not step_feedback or "findings" not in step_feedback:
        return None
    findings: dict[str, Any] = step_feedback["findings"]
    return findings


def _extract_prompt_feedback(
    context: RunContext, step: PipelineStep
) -> tuple[list[str] | None, str | None]:
    """Extract dictator overrides and validation findings from loop-back feedback and clear it.

    The pop is a guard clause rather than a fourth level of nesting, so each half of the return
    reads on its own.
    """
    findings = _pop_findings(context, step)
    if findings is None:
        return None, None

    overrides = (
        [findings["remarks"]]
        if findings.get("hitl_verdict") == "reject" and "remarks" in findings
        else None
    )

    fails = [r for r in findings.get("results", []) if r.get("status") == "FAIL"]
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
    #: Prepended to the spec stem to form the filename (`test_` for tests).
    FILENAME_PREFIX: ClassVar[str] = ""
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

    def _instructions(self) -> str:
        """The instruction block for this artefact. Imported lazily by the subclass."""
        raise NotImplementedError

    async def _generate(self, generator: Any, spec_path: Path, output_path: Path, **kw: Any) -> Any:
        """Invoke the generator method for this artefact."""
        raise NotImplementedError

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        name = type(self).__name__
        if context.model.llm is None:
            logger.error("%s: LLM adapter required but not configured", name)
            return _error_result("LLM adapter required for generate steps", started)

        try:
            from specweaver.workflows.implementation.generator import Generator

            adapter, config = _resolve_generation_routing(context, temperature=0.2)
            generator = Generator(llm=adapter, config=config)

            output_dir = context.output_dir or context.project_path / self.OUTPUT_SUBDIR
            stem = context.spec_path.stem.replace("_spec", "")
            output_path = output_dir / f"{self.FILENAME_PREFIX}{stem}.py"
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
                    context, step, instructions=self._instructions()
                )
            except ValueError as e:
                return _error_result(str(e), started)

            generated = await self._generate(
                generator,
                context.spec_path,
                output_path,
                base_prompt=base_prompt,
                artifact_uuid=artifact_uuid,
                dictator_overrides=dictator_overrides,
                validation_findings=validation_findings,
                environment_context=mcp_env,
            )
            logger.info("%s: %s generated at '%s'", name, self.ARTEFACT, generated)

            await log_artifact_lineage(
                context,
                artifact_uuid,
                self.EVENT_TYPE,
                parent_id=parent_id,
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
            logger.exception("%s: unhandled exception during %s generation", name, self.ARTEFACT)
            detail = str(exc)
            if self.INCLUDE_TRACEBACK:
                import traceback

                detail += "\n" + traceback.format_exc()
            return _error_result(detail, started)


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
    from specweaver.core.flow.handlers.context_assembler import evaluate_and_fetch_skeleton_context

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

    def _instructions(self) -> str:
        from specweaver.workflows.implementation.generator import CODE_GEN_INSTRUCTIONS

        return str(CODE_GEN_INSTRUCTIONS)

    async def _generate(self, generator: Any, spec_path: Path, output_path: Path, **kw: Any) -> Any:
        return await generator.generate_code(spec_path, output_path, **kw)


class GenerateTestsHandler(_GenerationHandler):
    """Handler for generate+tests — LLM test generation."""

    OUTPUT_SUBDIR: ClassVar[str] = "tests"
    FILENAME_PREFIX: ClassVar[str] = "test_"
    EVENT_TYPE: ClassVar[str] = "generated_tests"
    ARTEFACT: ClassVar[str] = "tests"

    def _instructions(self) -> str:
        from specweaver.workflows.implementation.generator import TEST_GEN_INSTRUCTIONS

        return str(TEST_GEN_INSTRUCTIONS)

    async def _generate(self, generator: Any, spec_path: Path, output_path: Path, **kw: Any) -> Any:
        return await generator.generate_tests(spec_path, output_path, **kw)


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
            context.model.llm_router.get_for_task(TaskType.PLAN)
            if context.model.llm_router
            else None
        )
        adapter = routed.adapter if routed else context.model.llm

        if routed:
            config = GenerationConfig(
                model=routed.model,
                temperature=routed.temperature,
                max_output_tokens=routed.max_output_tokens,
                task_type=TaskType.PLAN,
                run_id=context.run.run_id or "",
            )
        elif context.model.config is not None:
            config = GenerationConfig(
                model=context.model.config.llm.model,
                temperature=0.3,
                max_output_tokens=context.model.config.llm.max_output_tokens,
                task_type=TaskType.PLAN,
                run_id=context.run.run_id or "",
            )
        else:
            # Fallback
            config = GenerationConfig(
                model="gemini-3-flash-preview",
                temperature=0.3,
                max_output_tokens=4096,
                task_type=TaskType.PLAN,
                run_id=context.run.run_id or "",
            )

        return adapter, config

    async def _generate_plan_artifact(
        self, planner: Any, context: RunContext, spec_content: str, base_prompt: PromptBuilder
    ) -> tuple[Path, str, Any]:
        import io

        from ruamel.yaml import YAML

        from specweaver.core.flow.handlers.artifact_lineage import (
            derive_artifact_uuid,
            tag_content,
        )

        try:
            if context.model.config and hasattr(context.model.config, "stitch"):
                stitch_mode = context.model.config.stitch.mode
                stitch_api_key = context.model.config.stitch.api_key
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
            base_prompt=base_prompt,
            stitch_mode=stitch_mode,
            stitch_api_key=stitch_api_key,
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
        if context.model.llm is None:
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


class GenerateContractHandler:
    """Handler for generate+contract — extracts API Protocol from spec Contract section.
    This is a mechanical (non-LLM) extraction generating a Protocol class file at contracts/{stem}_contract.py.
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        """Execute contract generation from spec."""

        started = _now_iso()
        try:
            from specweaver.core.flow.handlers.contract_renderers import (
                contract_extension,
                extract_contract,
                extract_docstrings,
                extract_signatures,
                render_contract,
            )

            spec_text = context.spec_path.read_text(encoding="utf-8")
            contract_section = extract_contract(spec_text)
            if contract_section is None:
                return _error_result("No ## Contract section found in spec", started)

            signatures = extract_signatures(contract_section)
            if not signatures:
                return _error_result(
                    "No Python function signatures found in Contract code blocks",
                    started,
                )

            docstrings = extract_docstrings(contract_section)

            contracts_dir = context.project_path / "contracts"
            contracts_dir.mkdir(parents=True, exist_ok=True)
            stem = context.spec_path.stem.replace("_spec", "")
            class_name = stem.replace("_", " ").title().replace(" ", "")

            # Language-agnostic dispatch using Atom Proxy
            from specweaver.sandbox.language.core.atom import LanguageAtom

            atom = LanguageAtom(cwd=context.project_path)
            res = atom.run({"intent": "detect_language"})
            exports = res.exports or {}
            language = exports.get("language", "python")

            contract_content = render_contract(language, class_name, signatures, docstrings)
            ext = contract_extension(language)
            output_path = contracts_dir / f"{stem}_contract.{ext}"

            output_path.write_text(contract_content, encoding="utf-8")
            logger.info("GenerateContractHandler: contract written to '%s'", output_path)

            # Wire contract path into RunContext for downstream consumption (SF-B)
            # Frozen, so this is a rebuild-and-replace rather than an append.
            context.graph = context.graph.model_copy(
                update={
                    "api_contract_paths": [
                        *(context.graph.api_contract_paths or []),
                        str(output_path),
                    ]
                }
            )

            return StepResult(
                status=StepStatus.PASSED,
                output={"generated_path": str(output_path), "signature_count": len(signatures)},
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("GenerateContractHandler: unhandled exception")
            return _error_result(str(exc), started)

    @staticmethod
    def _extract_contract(text: str) -> str | None:
        from specweaver.core.flow.handlers.contract_renderers import extract_contract

        return extract_contract(text)

    @staticmethod
    def _extract_signatures(contract_text: str) -> list[str]:
        from specweaver.core.flow.handlers.contract_renderers import extract_signatures

        return extract_signatures(contract_text)

    @staticmethod
    def _extract_docstrings(contract_text: str) -> dict[str, str]:
        from specweaver.core.flow.handlers.contract_renderers import extract_docstrings

        return extract_docstrings(contract_text)
