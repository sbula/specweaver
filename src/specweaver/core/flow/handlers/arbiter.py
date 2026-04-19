# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Arbiter loop for Dual-Pipelines.

Evaluates test failures and assigns fault securely isolating the coding agent
from the existence of the scenario testing engine.
"""

from __future__ import annotations

import enum
import logging
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel

from specweaver.commons import json
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import StepHandler, _error_result, _now_iso

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.base import RunContext

logger = logging.getLogger(__name__)


class ArbitrateVerdict(enum.StrEnum):
    CODE_BUG = "code_bug"
    SCENARIO_ERROR = "scenario_error"
    SPEC_AMBIGUITY = "spec_ambiguity"
    ERROR = "error"


class ArbitrateResult(BaseModel):
    verdict: ArbitrateVerdict
    reasoning: str = ""
    spec_clause: str = ""
    coding_feedback: str = ""
    scenario_feedback: str = ""
    raw_response: str = ""


SCENARIO_VOCABULARY: frozenset[str] = frozenset(
    {
        "scenario",
        "scenarios/",
        "test_",
        "_scenarios",
        "yaml",
        "parametrize",
        "convert",
        "ScenarioSet",
        "scenario_validation",
        "generate_scenarios",
        "scenario_agent",
        "scenario pipeline",
    }
)


def _guard_coding_feedback(text: str) -> str:
    """Guard strictly against scenario term leakage into the coding agent feedback."""
    if not text:
        return text

    lower_text = text.lower()
    for banned in SCENARIO_VOCABULARY:
        if banned.lower() in lower_text:
            logger.warning(
                "ArbitrateVerdictHandler: Vocabulary leak caught! Banned term '%s' found in string: %s",
                banned,
                text,
            )
            return (
                "The implementation violates the exact behavioral requirement stipulated in the spec. "
                "The provided code does not behave according to the behavioral constraints on the given inputs. "
                "Please review the method definition logic against the specification."
            )
    return text


ARBITRATE_INSTRUCTIONS = """
You are a strict test arbitration agent. Scenario tests have failed for the component described
in the spec below. Your job is to determine WHO is at fault.

## Verdict types
- code_bug: The implementation code does not satisfy the spec's behavioral requirements.
- scenario_error: The scenario test setup is incorrect or tests the wrong behavior.
- spec_ambiguity: The spec clause is ambiguous and both interpretations are valid.

## Output format (JSON only — no other text)
{
  "verdict": "<code_bug|scenario_error|spec_ambiguity>",
  "reasoning": "<internal reasoning>",
  "spec_clause": "<e.g. FR-2 or missing>",
  "coding_feedback": "<spec-flavored feedback for the coding agent. MUST NOT contain the words: scenario, test, yaml, parametrize, convert, or any path. MUST read like a spec compliance behavioral review.>",
  "scenario_feedback": "<behavioral delta report for scenario agent. MUST NOT contain source code or implementation details.>"
}
"""


class ArbitrateVerdictHandler(StepHandler):
    """Diagnose test failures and route feedback to the offending party."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:  # noqa: C901
        started = _now_iso()
        logger.info("Executing ARBITRATE VERDICT for %s", context.run_id)

        if not context.llm:
            return _error_result("LLM not configured in context", started)

        try:
            # Safely recover test failures (which contain the unfiltered exception traces)
            test_results = (
                context.feedback.get("run_scenario_tests", {}).get("output", {}).get("results", [])
            )
            raw_tracing = ""
            for res in test_results:
                if res.get("status") == "FAIL" or res.get("status") == "ERROR":
                    raw_tracing += f"{res.get('message', '')}\n\n"

            # Dynamically filter framework trace lines using the unified Filter Interface
            from specweaver.core.loom.commons.language.stack_trace_filter_factory import (
                create_stack_trace_filter,
            )

            filter_impl = create_stack_trace_filter(context.project_path)
            filtered_trace = filter_impl.filter(raw_tracing)

            spec_content = ""
            if context.spec_path.exists():
                spec_content = context.spec_path.read_text(encoding="utf-8")

            from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

            builder = PromptBuilder()
            builder.add_instructions(ARBITRATE_INSTRUCTIONS)
            builder.add_context(spec_content, label="Spec Definition")
            builder.add_context(filtered_trace, label="Failures")

            prompt = builder.build()
            raw_response = await context.llm.generate(prompt)

            try:
                # Naive JSON extract
                json_str = raw_response
                match = re.search(r"\{.*\}", raw_response, re.DOTALL)
                if match:
                    json_str = match.group(0)
                data = json.loads(json_str)
            except json.JSONDecodeError:
                return _error_result(f"Failed to parse LLM verdict: {raw_response}", started)

            result = ArbitrateResult(**data)
            result.raw_response = raw_response

            safe_coding_feedback = _guard_coding_feedback(result.coding_feedback)

            if result.verdict == ArbitrateVerdict.CODE_BUG:
                logger.info("Arbitrate Verdict: CODE_BUG (%s)", result.spec_clause)
                context.feedback["generate_code"] = {
                    "from_step": "arbitrate_verdict",
                    "findings": {
                        "verdict": "code_bug",
                        "results": [
                            {
                                "status": "FAIL",
                                "rule_id": result.spec_clause,
                                "message": safe_coding_feedback,
                            }
                        ],
                    },
                }
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Arbiter assigned: {safe_coding_feedback}",
                    started_at=started,
                    completed_at=_now_iso(),
                )

            elif result.verdict == ArbitrateVerdict.SCENARIO_ERROR:
                logger.info("Arbitrate Verdict: SCENARIO_ERROR (%s)", result.spec_clause)
                context.feedback["generate_scenarios"] = {
                    "from_step": "arbitrate_verdict",
                    "findings": {
                        "verdict": "scenario_error",
                        "results": [
                            {
                                "status": "FAIL",
                                "rule_id": result.spec_clause,
                                "message": result.scenario_feedback,
                            }
                        ],
                    },
                }
                return StepResult(
                    status=StepStatus.FAILED,
                    error_message=f"Arbiter assigned: {result.scenario_feedback}",
                    started_at=started,
                    completed_at=_now_iso(),
                )

            elif result.verdict == ArbitrateVerdict.SPEC_AMBIGUITY:
                logger.warning(
                    "Arbitrate Verdict: SPEC_AMBIGUITY! Pausing for HITL %s", result.spec_clause
                )
                return StepResult(
                    status=StepStatus.WAITING_FOR_INPUT,
                    output=result.model_dump(),
                    error_message=f"Ambiguity detected on {result.spec_clause}",
                    started_at=started,
                    completed_at=_now_iso(),
                )

            return _error_result(f"Unknown verdict type {result.verdict}", started)

        except Exception as exc:
            logger.exception("ArbitrateVerdictHandler: unhandled error")
            return _error_result(str(exc), started)
