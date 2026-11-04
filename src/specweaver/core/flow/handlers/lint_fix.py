# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Lint-fix reflection loop handler."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _now_iso
from specweaver.core.flow.run_state.failures import log_step_failure

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.run_state.run_context import RunContext
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


def _did_not_run(lint_result: Any) -> str | None:
    """Why this lint did not run, or None when it reached a verdict.

    A result with no `error_count` is no verdict either: the atom refused the target or failed
    before linting, and a missing count must not read as zero errors.
    """
    from specweaver.sandbox.language.core.toolchain import did_not_run_reason

    exports = lint_result.exports or {}
    if "error_count" not in exports:
        return lint_result.message or "the lint returned no result"
    return did_not_run_reason(exports.get("errors", []))


def _lint_target(step: PipelineStep, context: RunContext) -> str:
    """The step's `target`, else the task's code file relative to the project."""
    from specweaver.assurance.validation.orchestration.archetype_pipelines import relative_to_root
    from specweaver.core.flow.handlers.qa_targets import task_code_file

    if step.params.get("target"):
        return str(step.params["target"])
    code = task_code_file(context)
    return relative_to_root(code, context.project_path) or str(code)


@dataclass(frozen=True)
class _Loop:
    """What every round of one lint-fix run shares."""

    context: RunContext
    step: PipelineStep
    target: str
    started: str


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
        verdict = self._verdict_without_model(
            lint_result, started, last_error_count, auto_fixed=False
        )
        if verdict:
            return verdict

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
        verdict = self._verdict_without_model(
            lint_result, started, last_error_count, auto_fixed=True
        )
        if verdict:
            return verdict

        # Phase 2: LLM reflection loop for remaining errors
        for _ in range(max_reflections):
            failed = await self._model_fix(
                _Loop(context, step, target, started),
                lint_result,
                reflections_used,
                last_error_count,
            )
            if failed:
                return failed
            reflections_used += 1

            # Re-lint
            lint_result = atom.run(run_kwargs)
            last_error_count = (
                lint_result.exports.get("error_count", 0) if lint_result.exports else 0
            )
            stopped = self._stop_if_not_run(
                lint_result, started, reflections_used, last_error_count
            )
            if stopped:
                return stopped

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

    async def _model_fix(
        self, loop: _Loop, lint_result: Any, reflections: int, remaining: int
    ) -> StepResult | None:
        """One model fix of the lint errors; the step's FAILED or ERROR result when none can run."""
        if loop.context.model.llm_router is None:
            return _lint_outcome(
                loop.started,
                status=StepStatus.FAILED,
                reflections=reflections,
                remaining=remaining,
                error="Lint errors found but no LLM configured for auto-fix",
            )
        code_file, refused = self._file_to_fix(loop.context, loop.target)
        if code_file is None:
            return StepResult(
                status=StepStatus.FAILED,
                error_message=refused,
                output={"reflections_used": reflections, "lint_errors_remaining": remaining},
                started_at=loop.started,
                completed_at=_now_iso(),
            )
        try:
            logger.debug(
                "LintFixHandler: LLM reflection %d on '%s'", reflections + 1, code_file.name
            )
            await self._llm_fix(
                code_file,
                lint_result.exports.get("errors", []) if lint_result.exports else [],
                context=loop.context,
                step=loop.step,
            )
        except Exception as exc:
            log_step_failure(
                logger, "LintFixHandler: LLM fix failed on reflection %d", reflections + 1
            )
            return _lint_outcome(
                loop.started,
                status=StepStatus.ERROR,
                reflections=reflections,
                remaining=remaining,
                error=str(exc),
            )
        return None

    @classmethod
    def _verdict_without_model(
        cls, lint_result: Any, started: str, remaining: int, *, auto_fixed: bool
    ) -> StepResult | None:
        """The step's result when no model is needed: the lint did not run, or it is clean."""
        stopped = cls._stop_if_not_run(lint_result, started, 0, remaining)
        if stopped:
            return stopped
        if remaining:
            return None
        logger.info("LintFixHandler: no lint errors (after the linter's auto-fix: %s)", auto_fixed)
        return _lint_outcome(
            started, status=StepStatus.PASSED, reflections=0, remaining=0, auto_fixed=auto_fixed
        )

    @staticmethod
    def _stop_if_not_run(
        lint_result: Any, started: str, reflections: int, remaining: int
    ) -> StepResult | None:
        """FAILED at once when the lint did not run: no auto-fix or model can fix that."""
        reason = _did_not_run(lint_result)
        if reason is None:
            return None
        logger.warning("LintFixHandler: the linter did not run: %s", reason)
        return _lint_outcome(
            started,
            status=StepStatus.FAILED,
            reflections=reflections,
            remaining=remaining,
            error=f"The linter did not run: {reason}",
        )

    def _get_atom(self, context: RunContext) -> QARunnerAtom:
        """Lazily create a QARunnerAtom for the project."""
        from specweaver.core.flow.handlers.coder_sandbox import coder_sandbox
        from specweaver.sandbox.language.core.runner_factory import qa_atom

        return qa_atom(
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
        step: PipelineStep,
    ) -> None:
        """Ask the LLM to fix lint errors in the given file, in the run's language."""
        from specweaver.commons.lineage import extract_artifact_uuid
        from specweaver.core.flow.engine.run_language import run_task_files
        from specweaver.core.flow.handlers._llm import llm_for_step
        from specweaver.core.flow.handlers.artifact_lineage import log_artifact_lineage
        from specweaver.workflows.implementation.lint_repair import repair_lint

        code = code_path.read_text(encoding="utf-8")
        language = run_task_files(context).language
        adapter, config = llm_for_step(context, step)
        fixed = await repair_lint(
            adapter, config, code, lint_errors, language, context.project_path
        )
        code_path.write_text(fixed, encoding="utf-8")

        artifact_uuid = extract_artifact_uuid(code)
        if artifact_uuid:
            await log_artifact_lineage(
                context,
                artifact_uuid,
                "lint_fixed",
                model_id=config.model if config else "unknown",
            )
