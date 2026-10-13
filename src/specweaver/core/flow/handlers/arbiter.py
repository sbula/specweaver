# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Arbiter loop for Dual-Pipelines.

Evaluates test failures and assigns fault securely isolating the coding agent
from the existence of the scenario testing engine.
"""

from __future__ import annotations

import enum
import hashlib
import logging
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from specweaver.commons import json
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import StepHandler, _error_result, _now_iso
from specweaver.core.flow.handlers.results import log_step_failure

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.workspace.ast.parsers.interfaces import StackTraceFilterInterface

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
    #: The readings of an unclear clause, for the person who must settle it.
    interpretations: list[str] = []
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
  "scenario_feedback": "<behavioral delta report for scenario agent. MUST NOT contain source code or implementation details.>",
  "interpretations": ["<for spec_ambiguity only: reading A of the clause>", "<reading B>"]
}
"""


#: A frame line: pytest's `path:line:` or a JVM `at ...` line.
_FRAME = re.compile(r"^(?:\S[^\s:]*:\d+:|\s+at\s)")


def code_trace(stacktrace: str, trace_filter: StackTraceFilterInterface) -> str:
    """The lines of a failure's trace that belong to the coder's own code, else "".

    Each line belongs to the frame above it (a header before the first frame belongs to that
    frame); a check's frames and everything they own are dropped. A trace that would still
    name the hidden check is dropped whole.
    """
    lines = stacktrace.splitlines()
    frames = [i for i, line in enumerate(lines) if _FRAME.match(line)]
    if not frames:
        return ""
    kept = []
    for i, line in enumerate(lines):
        owner = max((f for f in frames if f <= i), default=frames[0])
        if not trace_filter.is_scenario_frame(lines[owner]):
            kept.append(line)
    text = "\n".join(kept).strip()
    if not text or any(word.lower() in text.lower() for word in SCENARIO_VOCABULARY):
        return ""
    return text


def _spec_sha(context: RunContext) -> str:
    try:
        return hashlib.sha256(context.spec_path.read_text(encoding="utf-8").encode()).hexdigest()
    except OSError:
        return ""


def _unclear_message(result: ArbitrateResult, context: RunContext) -> str:
    readings = "\n".join(
        f"  {letter}) {text}"
        for letter, text in zip("abcdefgh", result.interpretations, strict=False)
    )
    return (
        f"Spec clause {result.spec_clause or '(unnamed)'} is unclear. It can be read as:\n"
        f"{readings or '  (the arbiter gave no readings) ' + result.reasoning}\n"
        f"Edit that clause in {context.spec_path}, then resume the run."
    )


def _earlier_park(context: RunContext) -> dict[str, Any] | None:
    """This step's own park, when the run was resumed from it."""
    for record in context.run.step_records or []:
        result = record.get("result") or {}
        output = result.get("output") or {}
        if record.get("step_name") == context.run.step_name and "spec_sha" in output:
            return {"output": output, "message": result.get("error_message") or ""}
    return None


def _after_park(context: RunContext, started: str) -> StepResult | None:
    """Resumed from an unclear-clause park: park again if the spec is unchanged, else rerun."""
    park = _earlier_park(context)
    if park is None or "scenario_test_failures" in context.feedback:
        return None
    if park["output"]["spec_sha"] == _spec_sha(context):
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output=park["output"],
            error_message="The spec is unchanged. " + park["message"],
            started_at=started,
            completed_at=_now_iso(),
        )
    return StepResult(
        status=StepStatus.FAILED,
        error_message="The spec was edited; the round runs again with it.",
        started_at=started,
        completed_at=_now_iso(),
    )


def _with_trace(
    feedback: str, failures: list[dict[str, Any]], trace_filter: StackTraceFilterInterface
) -> str:
    """The coder's feedback, with the frames of its own code where it failed."""
    trace = "\n\n".join(
        t for f in failures if (t := code_trace(f.get("stacktrace", ""), trace_filter))
    )
    return f"{feedback}\n\nWhere your code failed:\n{trace}" if trace else feedback


def _code_bug(context: RunContext, clause: str, feedback: str, started: str) -> StepResult:
    """Send the coder back to work with its feedback; the evidence is used up."""
    context.feedback.pop("scenario_test_failures", None)  # terminal verdict
    context.feedback["generate_code"] = {
        "from_step": "arbitrate_verdict",
        "findings": {
            "verdict": "code_bug",
            "results": [{"status": "FAIL", "rule_id": clause, "message": feedback}],
        },
    }
    return StepResult(
        status=StepStatus.FAILED,
        error_message=f"Arbiter assigned: {feedback}",
        started_at=started,
        completed_at=_now_iso(),
    )


def _not_arbitrable(context: RunContext, started: str) -> StepResult | None:
    """The step's result when there is nothing to arbitrate: a resumed park, or no evidence."""
    resumed = _after_park(context, started)
    if resumed is not None:
        return resumed
    evidence_error = _evidence_error(context)
    return _error_result(evidence_error, started) if evidence_error is not None else None


def _evidence_error(context: RunContext) -> str | None:
    """Why the scenario evidence cannot be arbitrated, or None when it can.

    The evidence contract: `run_scenario_tests` ALWAYS publishes the raw QA export
    under this reserved key for scenario runs, so its absence means the wire is broken and must
    fail LOUD, never green. The key is consumed ON VERDICT (popped only on terminal branches) so a
    `spec_ambiguity` park can resume and re-arbitrate, and an ERROR retry re-reads it.
    """
    if "scenario_test_failures" not in context.feedback:
        return (
            "scenario evidence missing — feedback['scenario_test_failures'] was never "
            "published (wiring defect between run_scenario_tests and the arbiter), or the "
            "run was resumed across sessions (scenario evidence is not persisted — re-run "
            "the pipeline)"
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
        return (
            "malformed scenario evidence under feedback['scenario_test_failures'] — "
            "expected the QA export shape (total/failed/errors ints, failures list of dicts)"
        )
    return None


class ArbitrateVerdictHandler(StepHandler):
    """Diagnose test failures and route feedback to the offending party."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:  # noqa: C901
        started = _now_iso()
        logger.info("Executing ARBITRATE VERDICT for %s", context.run.run_id)

        # The evidence contract. run_scenario_tests ALWAYS publishes
        # the raw QA export under this reserved key for scenario runs — its absence
        # means the wire is broken and must fail LOUD, never green. The key is
        # consumed ON VERDICT (popped only on terminal branches) so a spec_ambiguity
        # park can resume and re-arbitrate, and an ERROR retry re-reads it.
        early = _not_arbitrable(context, started)
        if early is not None:
            return early
        evidence = context.feedback["scenario_test_failures"]
        # Shape already validated above, so this is a plain read rather than a second guard.
        failures = evidence.get("failures", [])

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
            logger.info(
                "ArbitrateVerdictHandler: %d/%d scenario tests green — no arbitration", total, total
            )
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

        if context.model.llm_router is None:
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

            from specweaver.core.flow.handlers._llm import llm_for
            from specweaver.infrastructure.llm.models import Message, Role, TaskType

            adapter, config = llm_for(context, TaskType.REVIEW)
            prompt = base_prompt.build()
            response = await adapter.generate([Message(role=Role.USER, content=prompt)], config)
            # Normalize the adapter's LLMResponse (string returns are the unit-mock convention
            # only).
            raw_response = response.text if hasattr(response, "text") else response

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

            safe_coding_feedback = _with_trace(safe_coding_feedback, failures, filter_impl)
            if result.verdict == ArbitrateVerdict.CODE_BUG:
                logger.info("Arbitrate Verdict: CODE_BUG (%s)", result.spec_clause)
                return _code_bug(context, result.spec_clause, safe_coding_feedback, started)

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
                    output={**result.model_dump(), "spec_sha": _spec_sha(context)},
                    error_message=_unclear_message(result, context),
                    started_at=started,
                    completed_at=_now_iso(),
                )

            return _error_result(f"Unknown verdict type {result.verdict}", started)

        except Exception as exc:
            log_step_failure(logger, "ArbitrateVerdictHandler: unhandled error")
            return _error_result(str(exc), started)
