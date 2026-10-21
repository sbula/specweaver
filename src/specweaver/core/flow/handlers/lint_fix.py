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


class LintFixHandler:
    """Handler for lint_fix+code — lint-fix reflection loop.

    Runs the linter on generated code. If errors are found, feeds them
    to the LLM to generate fixes, then re-lints. Repeats up to
    ``max_reflections`` times (from ``step.params``).

    Inspired by Aider's ``max_reflections`` pattern.

    Step params:
        target: str — file or directory to lint (default: "src/").
        max_reflections: int — max fix cycles (default: 3).
    """

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        max_reflections: int = step.params.get("max_reflections", 3)
        target: str = step.params.get("target", "src/")
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

        # Phase 1: Try ruff auto-fix first (cheaper than LLM)
        logger.info("LintFixHandler: attempting ruff auto-fix on %d errors", last_error_count)
        fix_kwargs = dict(run_kwargs)
        fix_kwargs["fix"] = True
        atom.run(fix_kwargs)

        # Re-lint to see what remains after auto-fix
        lint_result = atom.run(run_kwargs)
        last_error_count = lint_result.exports.get("error_count", 0) if lint_result.exports else 0
        logger.debug("LintFixHandler: after auto-fix, %d errors remain", last_error_count)

        if last_error_count == 0:
            logger.info("LintFixHandler: all errors resolved by ruff auto-fix")
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
            code_files = self._find_code_files(context, target)
            if not code_files:
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message="No code files found to fix",
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
                    code_files[0].name,
                )
                await self._llm_fix(
                    code_files[0],
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

    def _find_code_files(self, context: RunContext, target: str | None = None) -> list[Path]:
        """Find the Python file(s) to fix.

        An explicit ``target`` (the generated ``src/<stem>.py``) is
        authoritative — resolved against ``project_path`` and required to stay inside it
        (no traversal) — so the LLM reflection loop can locate the file when ``output_dir``
        is unset. A non-file target (e.g. the default ``"src/"`` directory) or no target
        falls back to the legacy ``output_dir`` glob.
        """
        if target and getattr(context, "project_path", None):
            base = context.project_path.resolve()
            candidate = (context.project_path / target).resolve()
            try:
                candidate.relative_to(base)
            except ValueError:  # expected: a target outside the project root is refused
                return []
            if candidate.is_file():
                return [candidate]

        if context.output_dir and context.output_dir.exists():
            return list(context.output_dir.glob("*.py"))
        return []

    async def _llm_fix(
        self,
        code_path: Path,
        lint_errors: list[dict[str, object]],
        *,
        context: RunContext,
    ) -> None:
        """Ask the LLM to fix lint errors in the given file."""
        from specweaver.infrastructure.llm.models import Message, Role, TaskType

        code = code_path.read_text(encoding="utf-8")
        from specweaver.commons.lineage import extract_artifact_uuid, wrap_artifact_tag
        from specweaver.core.flow.handlers.artifact_lineage import (
            log_artifact_lineage,
            tag_content,
        )

        # Never `derive_artifact_uuid` here: this file's identity was minted when it was generated,
        # and the LLM is being asked to preserve it. Minting one would fork the lineage.
        artifact_uuid = extract_artifact_uuid(code)

        error_summary = "\n".join(
            f"- {e.get('file', '?')}:{e.get('line', '?')} [{e.get('code', '?')}] {e.get('message', '')}"
            for e in lint_errors
        )

        prompt = (
            f"Fix the following lint errors in this Python file.\n\n"
            f"## Lint Errors\n{error_summary}\n\n"
            f"## Current Code\n```python\n{code}\n```\n\n"
            f"Return ONLY the fixed Python code, no explanations."
        )

        if artifact_uuid:
            tag_str = wrap_artifact_tag(artifact_uuid, "python")
            if tag_str:
                prompt += f"\n\nIMPORTANT: You MUST include the exact string '{tag_str}' physically at the very top of your output file."

        messages = [Message(role=Role.USER, content=prompt)]

        from specweaver.core.flow.handlers._llm import llm_for

        adapter, config = llm_for(context, TaskType.CHECK)

        response = await adapter.generate(messages, config)

        fixed_code = response.text.strip()
        # Strip markdown fences if present
        if fixed_code.startswith("```"):
            lines = fixed_code.split("\n")
            lines = [line for line in lines if not line.startswith("```")]
            fixed_code = "\n".join(lines)

        # Safety fallback: the prompt asked the LLM to reproduce the tag, and it may not have.
        if artifact_uuid:
            fixed_code = tag_content(fixed_code, artifact_uuid, "python")

        code_path.write_text(fixed_code + "\n", encoding="utf-8")

        if artifact_uuid:
            await log_artifact_lineage(
                context,
                artifact_uuid,
                "lint_fixed",
                model_id=config.model if config else "unknown",
            )
