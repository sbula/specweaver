# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Review step handlers — LLM-based spec and code review."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.flow._base import RunContext, _error_result, _now_iso
from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.flow.models import PipelineStep

logger = logging.getLogger(__name__)


def _review_config_from_context(context: RunContext) -> object:
    """Build GenerationConfig from RunContext, falling back to defaults."""
    from specweaver.llm.models import GenerationConfig

    if context.config is not None:
        return GenerationConfig(
            model=context.config.llm.model,
            temperature=0.3,
            max_output_tokens=context.config.llm.max_output_tokens,
        )
    return GenerationConfig(
        model="gemini-3-flash-preview",
        temperature=0.3,
        max_output_tokens=4096,
    )


class ReviewSpecHandler:
    """Handler for review+spec — LLM-based spec review."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            logger.error("ReviewSpecHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for review steps", started)

        logger.debug("ReviewSpecHandler: reviewing spec '%s'", context.spec_path.name)
        try:
            from specweaver.review.reviewer import Reviewer

            reviewer = Reviewer(
                llm=context.llm,
                config=_review_config_from_context(context),
            )
            result = await reviewer.review_spec(
                context.spec_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
            )
            logger.info(
                "ReviewSpecHandler: verdict=%s, findings=%d",
                result.verdict.value, len(result.findings),
            )
            return StepResult(
                status=StepStatus.PASSED
                if result.verdict.value == "accepted"
                else StepStatus.FAILED,
                output={
                    "verdict": result.verdict.value,
                    "summary": result.summary,
                    "findings_count": len(result.findings),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("ReviewSpecHandler: unhandled exception during spec review")
            return _error_result(str(exc), started)


class ReviewCodeHandler:
    """Handler for review+code — LLM-based code review."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        if context.llm is None:
            logger.error("ReviewCodeHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for review steps", started)

        try:
            from specweaver.review.reviewer import Reviewer

            code_path = self._find_code_path(context)
            if code_path is None:
                return _error_result("No code file found for review", started)

            reviewer = Reviewer(
                llm=context.llm,
                config=_review_config_from_context(context),
            )
            result = await reviewer.review_code(
                code_path,
                context.spec_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
            )
            logger.info(
                "ReviewCodeHandler: verdict=%s, findings=%d",
                result.verdict.value, len(result.findings),
            )
            return StepResult(
                status=StepStatus.PASSED
                if result.verdict.value == "accepted"
                else StepStatus.FAILED,
                output={
                    "verdict": result.verdict.value,
                    "summary": result.summary,
                    "findings_count": len(result.findings),
                },
                started_at=started,
                completed_at=_now_iso(),
            )
        except Exception as exc:
            logger.exception("ReviewCodeHandler: unhandled exception during code review")
            return _error_result(str(exc), started)

    def _find_code_path(self, context: RunContext) -> Path | None:
        if context.output_dir and context.output_dir.exists():
            py_files = list(context.output_dir.glob("*.py"))
            if py_files:
                return py_files[0]
        return None
