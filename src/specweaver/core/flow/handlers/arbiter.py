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

        # INT-US-24 FR-2: the evidence contract. run_scenario_tests ALWAYS publishes
        # the raw QA export under this reserved key for scenario runs — its absence
        # means the wire is broken and must fail LOUD, never green. The key is
        # consumed ON VERDICT (popped only on terminal branches) so a spec_ambiguity
        # park can resume and re-arbitrate, and an ERROR retry re-reads it.
        if "scenario_test_failures" not in context.feedback:
            return _error_result(
                "scenario evidence missing — feedback['scenario_test_failures'] was never "
                "published (wiring defect between run_scenario_tests and the arbiter)",
                started,
            )
        evidence = context.feedback["scenario_test_failures"]
        counts_ok = isinstance(evidence, dict) and all(
            isinstance(evidence.get(k, 0), int) for k in ("total", "failed", "errors")
        )
        failures = evidence.get("failures", []) if isinstance(evidence, dict) else None
        if (
            not counts_ok
            or not isinstance(failures, list)
            or any(not isinstance(f, dict) for f in failures)
        ):
            return _error_result(
                "malformed scenario evidence under feedback['scenario_test_failures'] — "
                "expected the QA export shape (total/failed/errors ints, failures list of dicts)",
                started,
            )

        total = evidence.get("total", 0)
        failed = evidence.get("failed", 0)
        errors = evidence.get("errors", 0)

        if total == 0:
            # A zero-collected run leaked through the continue-gate — there is
            # nothing to arbitrate and nothing was verified. Evidence retained
            # (not a terminal verdict); a loop-back re-publishes fresh evidence.
            return StepResult(
                status=StepStatus.FAILED,
                error_message=(
                    "No scenario tests executed — nothing to arbitrate; the behavioral "
                    "verification cannot pass on an empty run."
                ),
                started_at=started,
                completed_at=_now_iso(),
            )

        if failed == 0 and errors == 0:
            # Verification green: no arbitration needed, no LLM call spent.
            logger.info("ArbitrateVerdictHandler: %d/%d scenario tests green — no arbitration", total, total)
            context.feedback.pop("scenario_test_failures", None)
            return StepResult(
                status=StepStatus.PASSED,
                output={
                    "verdict": "no_failures",
                    "passed": evidence.get("passed", total),
                    "total": total,
                },
                started_at=started,
                completed_at=_now_iso(),
            )

        if not context.llm:
            return _error_result("LLM not configured in context", started)

        try:
            # Compose the raw evidence text from the real TestFailure payloads.
            raw_tracing = ""
            for f in failures:
                raw_tracing += (
                    f"{f.get('nodeid', '')}: {f.get('message', '')}\n{f.get('stacktrace', '')}\n\n"
                )
            if not raw_tracing.strip():
                # errors-only runs (e.g. collection/import crash) carry no per-test
                # failure entries — arbitrate on the aggregate signal instead.
                raw_tracing = (
                    f"{errors} collection/execution error(s) out of {total} scenario tests; "
                    "no per-test failure details available."
                )

            # Dynamically filter framework trace lines using the unified Filter Interface
            from specweaver.sandbox.language.core.stack_trace_filter_factory import (
                create_stack_trace_filter,
            )

            filter_impl = create_stack_trace_filter(context.project_path)
            filtered_trace = filter_impl.filter(raw_tracing)

            from specweaver.core.flow.handlers._profiles import ARBITER, resolve_profile
            from specweaver.core.flow.handlers.base import _build_base_prompt

            try:
                profile = resolve_profile(step.params.get("render_profile"), default=ARBITER)
            except ValueError as e:
                return _error_result(str(e), started)

            base_prompt = await _build_base_prompt(context, ARBITRATE_INSTRUCTIONS, profile=profile)
            base_prompt.add_context(filtered_trace, label="Failures")

            prompt = base_prompt.build()
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
                context.feedback.pop("scenario_test_failures", None)  # terminal verdict
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
                context.feedback.pop("scenario_test_failures", None)  # terminal verdict
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
