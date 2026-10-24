# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Lint-fix reflection loop handler."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _now_iso
from specweaver.core.flow.handlers.results import log_step_failure

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

logger = logging.getLogger(__name__)


def _lint_outcome(
    started: str,
    *,
    status: StepStatus,
    reflections: int,
    remaining: int,
    auto_fixed: bool | None = None,
    error: str | None = None,
) -> StepResult:
    """One `StepResult` shape for all five of this handler's exits."""
    output: dict[str, Any] = {
        "reflections_used": reflections,
        "lint_errors_remaining": remaining,
    }
    if auto_fixed is not None:
        output["auto_fixed"] = auto_fixed
    # `error_message` is a required `str` on the model, so a success path must OMIT it rather than
    # pass None — which is what the five inlined literals did, and what this nearly lost.
    extra = {"error_message": error} if error is not None else {}
    return StepResult(
        status=status,
        output=output,
        started_at=started,
        completed_at=_now_iso(),
        **extra,
    )


def _lint_target(step: PipelineStep, context: RunContext) -> str:
    """The step's `target`, else the task's code file relative to the project."""
    from specweaver.core.flow.handlers.archetype_pipelines import relative_to_root
    from specweaver.core.flow.handlers.qa_targets import task_code_file

    if step.params.get("target"):
        return str(step.params["target"])
    code = task_code_file(context)
    return relative_to_root(code, context.project_path) or str(code)


class LintFixHandler:
    """Handler for lint_fix+code — lint-fix reflection loop.

    Runs the linter on generated code. If errors are found, feeds them
    to the LLM to generate fixes, then re-lints. Repeats up to
    ``max_reflections`` times (from ``step.params``).

    Inspired by Aider's ``max_reflections`` pattern.

    Step params:
        target: str — file or directory to lint (default: the task's code file).
        max_reflections: int — max fix cycles (default: 3).
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        max_reflections: int = step.params.get("max_reflections", 3)
        target = _lint_target(step, context)
        logger.debug(
            "LintFixHandler: starting lint-fix loop (target=%s, max_reflections=%d)",
            target,
            max_reflections,
        )

        atom = self._get_atom(context)
        reflections_used = 0
        last_error_count = 0

        run_kwargs: dict[str, Any] = {"intent": "run_linter", "target": target}

        # Initial lint
        lint_result = atom.run(run_kwargs)
        last_error_count = lint_result.exports.get("error_count", 0) if lint_result.exports else 0
        logger.debug("LintFixHandler: initial lint found %d errors", last_error_count)

        # Clean on first run → done
        if last_error_count == 0:
            logger.info("LintFixHandler: code is clean — no lint errors")
            return _lint_outcome(
                started, status=StepStatus.PASSED, reflections=0, remaining=0, auto_fixed=False
            )

        # Phase 1: the linter's own fix first (cheaper than the LLM)
        logger.info(
            "LintFixHandler: attempting the linter's auto-fix on %d errors", last_error_count
        )
        fix_kwargs = dict(run_kwargs)
        fix_kwargs["fix"] = True
        atom.run(fix_kwargs)

        # Re-lint to see what remains after auto-fix
        lint_result = atom.run(run_kwargs)
        last_error_count = lint_result.exports.get("error_count", 0) if lint_result.exports else 0
        logger.debug("LintFixHandler: after auto-fix, %d errors remain", last_error_count)

        if last_error_count == 0:
            logger.info("LintFixHandler: all errors resolved by the linter's auto-fix")
            return _lint_outcome(
                started, status=StepStatus.PASSED, reflections=0, remaining=0, auto_fixed=True
            )

        # Phase 2: LLM reflection loop for remaining errors
        for _ in range(max_reflections):
            # No LLM → can't fix
            if context.model.llm_router is None:
                return _lint_outcome(
                    started,
                    status=StepStatus.FAILED,
                    reflections=reflections_used,
                    remaining=last_error_count,
                    error="Lint errors found but no LLM configured for auto-fix",
                )

            # Find code to fix
            code_file, refused = self._file_to_fix(context, target)
            if code_file is None:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=refused,
                    output={
                        "reflections_used": reflections_used,
                        "lint_errors_remaining": last_error_count,
                    },
                    started_at=started,
                    completed_at=_now_iso(),
                )

            # Ask LLM to fix
            try:
                logger.debug(
                    "LintFixHandler: LLM reflection %d/%d on '%s'",
                    reflections_used + 1,
                    max_reflections,
                    code_file.name,
                )
                await self._llm_fix(
                    code_file,
                    lint_result.exports.get("errors", []) if lint_result.exports else [],
                    context=context,
                )
            except Exception as exc:
                log_step_failure(
                    logger, "LintFixHandler: LLM fix failed on reflection %d", reflections_used + 1
                )
                return _lint_outcome(
                    started,
                    status=StepStatus.ERROR,
                    reflections=reflections_used,
                    remaining=last_error_count,
                    error=str(exc),
                )

            reflections_used += 1

            # Re-lint
            lint_result = atom.run(run_kwargs)
            last_error_count = (
                lint_result.exports.get("error_count", 0) if lint_result.exports else 0
            )

            if last_error_count == 0:
                return _lint_outcome(
                    started, status=StepStatus.PASSED, reflections=reflections_used, remaining=0
                )

        # Exhausted
        logger.warning(
            "LintFixHandler: exhausted after %d reflections, %d errors remain",
            reflections_used,
            last_error_count,
        )
        return StepResult(
            status=StepStatus.FAILED,
            output={
                "reflections_used": reflections_used,
                "lint_errors_remaining": last_error_count,
            },
            error_message=f"Lint-fix exhausted after {reflections_used} reflections, "
            f"{last_error_count} errors remain",
            started_at=started,
            completed_at=_now_iso(),
        )

    def _get_atom(self, context: RunContext) -> QARunnerAtom:
        """Lazily create a QARunnerAtom for the project."""
        from specweaver.core.flow.handlers.coder_sandbox import coder_sandbox
        from specweaver.sandbox.qa_runner.core.atom import QARunnerAtom

        return QARunnerAtom(
            cwd=context.project_path,
            language=context.isolation.language,
            sandbox_settings=coder_sandbox(context),
        )

    def _file_to_fix(self, context: RunContext, target: str) -> tuple[Path | None, str]:
        """`_fix_file`, and what to say when there is none."""
        try:
            found = self._fix_file(context, target)
        except ValueError as exc:
            return None, str(exc)
        return found, "No code files found to fix"

    def _fix_file(self, context: RunContext, target: str) -> Path | None:
        """The file the LLM fixes: `target` when it names a file inside the project, else the
        task's code file; None when there is none. Raises `ValueError` for a target outside."""
        from specweaver.core.flow.handlers.qa_targets import resolve_inside, task_code_file

        candidate = resolve_inside(context.project_path, target)
        if candidate.is_file():
            return candidate
        code = task_code_file(context)
        return code if code.is_file() else None

    async def _llm_fix(
        self,
        code_path: Path,
        lint_errors: list[dict[str, object]],
        *,
        context: RunContext,
    ) -> None:
        """Ask the LLM to fix lint errors in the given file, in the run's language."""
        from specweaver.core.flow.engine.task_files import task_files_for
        from specweaver.infrastructure.llm.models import Message, Role, TaskType
        from specweaver.workflows.implementation.generator import strip_fences
        from specweaver.workflows.implementation.languages import language_guide

        code = code_path.read_text(encoding="utf-8")
        from specweaver.commons.lineage import extract_artifact_uuid, wrap_artifact_tag
        from specweaver.core.flow.handlers.artifact_lineage import (
            log_artifact_lineage,
            tag_content,
        )

        # Never `derive_artifact_uuid` here: this file's identity was minted when it was generated,
        # and the LLM is being asked to preserve it. Minting one would fork the lineage.
        artifact_uuid = extract_artifact_uuid(code)
        language = task_files_for(
            context.project_path, context.spec_path, context.isolation.language
        ).language
        name = language_guide(language, context.project_path).name

        error_summary = "\n".join(
            f"- {e.get('file', '?')}:{e.get('line', '?')} [{e.get('code', '?')}] {e.get('message', '')}"
            for e in lint_errors
        )

        prompt = (
            f"Fix the following lint errors in this {name} file.\n\n"
            f"## Lint Errors\n{error_summary}\n\n"
            f"## Current Code\n```{language}\n{code}\n```\n\n"
            f"Return ONLY the fixed {name} code, no explanations."
        )

        if artifact_uuid:
            tag_str = wrap_artifact_tag(artifact_uuid, language)
            if tag_str:
                prompt += f"\n\nIMPORTANT: You MUST include the exact string '{tag_str}' physically at the very top of your output file."

        messages = [Message(role=Role.USER, content=prompt)]

        from specweaver.core.flow.handlers._llm import llm_for

        adapter, config = llm_for(context, TaskType.CHECK)

        response = await adapter.generate(messages, config)

        fixed_code = strip_fences(response.text)
        # Safety fallback: the prompt asked the LLM to reproduce the tag, and it may not have.
        if artifact_uuid:
            fixed_code = tag_content(fixed_code, artifact_uuid, language)

        code_path.write_text(fixed_code, encoding="utf-8")

        if artifact_uuid:
            await log_artifact_lineage(
                context,
                artifact_uuid,
                "lint_fixed",
                model_id=config.model if config else "unknown",
            )
