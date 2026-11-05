# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The arbiter step of a dual run: checks the evidence, asks the arbitration workflow who is at
fault, and routes its report to that side.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.engine.step_outputs import RESULTS, VERDICT
from specweaver.core.flow.handlers.base import StepHandler, _error_result, _now_iso
from specweaver.core.flow.handlers.dual_pipeline import side_step
from specweaver.core.flow.run_state.failures import log_step_failure
from specweaver.core.flow.run_state.feedback import SCENARIO_EVIDENCE, send_findings
from specweaver.workflows.arbitration.verdict import (
    ARBITRATE_INSTRUCTIONS,
    ArbitrateVerdict,
    UnreadableVerdictError,
    arbitrate,
    evidence_text,
    guard_coding_feedback,
    scenario_safe,
    with_trace,
)

if TYPE_CHECKING:
    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.run_state.run_context import RunContext
    from specweaver.workflows.arbitration.verdict import ArbitrateResult
    from specweaver.workspace.ast.parsers.interfaces import StackTraceFilterInterface

logger = logging.getLogger(__name__)


def _spec_sha(context: RunContext) -> str:
    from specweaver.core.flow.handlers.reviewed_spec import spec_sha

    return spec_sha(context.spec_path)


def _changed_spec(context: RunContext, started: str) -> StepResult | None:
    """A park when the spec is not the reviewed one: a verdict would judge the wrong spec."""
    from specweaver.core.flow.handlers.reviewed_spec import review_refusal

    refusal = review_refusal(context, without_store=None)
    if refusal is None:
        return None
    return StepResult(
        status=StepStatus.WAITING_FOR_INPUT,
        output={"spec_review": "changed"},
        error_message=f"Not arbitrated: {refusal}.",
        started_at=started,
        completed_at=_now_iso(),
    )


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
    if park is None or SCENARIO_EVIDENCE in context.feedback:
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


def _code_bug(
    context: RunContext, from_step: str, clause: str, feedback: str, started: str
) -> StepResult:
    """Send the coder back to work with its feedback; the evidence is used up."""
    context.feedback.pop(SCENARIO_EVIDENCE, None)  # terminal verdict
    send_findings(
        context,
        side_step("coder"),
        from_step,
        {
            VERDICT: "code_bug",
            RESULTS: [{"status": "FAIL", "rule_id": clause, "message": feedback}],
        },
    )
    return StepResult(
        status=StepStatus.FAILED,
        error_message=f"Arbiter assigned: {feedback}",
        started_at=started,
        completed_at=_now_iso(),
    )


def _not_arbitrable(context: RunContext, started: str) -> StepResult | None:
    """The step's result when there is nothing to arbitrate: a changed spec, a resumed park, or
    no evidence."""
    changed = _changed_spec(context, started)
    if changed is not None:
        return changed
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
    if SCENARIO_EVIDENCE not in context.feedback:
        return (
            "scenario evidence missing — feedback['scenario_test_failures'] was never "
            "published (wiring defect between run_scenario_tests and the arbiter), or the "
            "run was resumed across sessions (scenario evidence is not persisted — re-run "
            "the pipeline)"
        )

    evidence = context.feedback[SCENARIO_EVIDENCE]
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


def _nothing_ran(started: str) -> StepResult:
    """A zero-collected run leaked through the continue-gate: nothing was verified.

    The evidence is kept (not a terminal verdict); a loop-back publishes fresh evidence.
    """
    return StepResult(
        status=StepStatus.FAILED,
        error_message=(
            "No scenario tests executed — nothing to arbitrate; the behavioral "
            "verification cannot pass on an empty run."
        ),
        started_at=started,
        completed_at=_now_iso(),
    )


def _no_failures(context: RunContext, evidence: dict[str, Any], started: str) -> StepResult:
    """Verification green: no arbitration needed, no model call spent."""
    total = evidence.get("total", 0)
    logger.info(
        "ArbitrateVerdictHandler: %d/%d scenario tests green — no arbitration", total, total
    )
    context.feedback.pop(SCENARIO_EVIDENCE, None)
    from specweaver.core.flow.handlers.reviewed_spec import keep_set

    keep_set(context)
    return StepResult(
        status=StepStatus.PASSED,
        output={VERDICT: "no_failures", "passed": evidence.get("passed", total), "total": total},
        started_at=started,
        completed_at=_now_iso(),
    )


def _scenario_error(
    context: RunContext, from_step: str, result: ArbitrateResult, started: str
) -> StepResult:
    """Send the scenario side back with a words-only report; the evidence is used up."""
    context.feedback.pop(SCENARIO_EVIDENCE, None)  # terminal verdict
    safe_scenario_feedback = scenario_safe(result.scenario_feedback, result.spec_clause)
    send_findings(
        context,
        side_step("scenario"),
        from_step,
        {
            VERDICT: "scenario_error",
            RESULTS: [
                {"status": "FAIL", "rule_id": result.spec_clause, "message": safe_scenario_feedback}
            ],
        },
    )
    return StepResult(
        status=StepStatus.FAILED,
        error_message=f"Arbiter assigned: {safe_scenario_feedback}",
        started_at=started,
        completed_at=_now_iso(),
    )


def _route(
    context: RunContext,
    from_step: str,
    result: ArbitrateResult,
    failures: list[dict[str, Any]],
    trace_filter: StackTraceFilterInterface,
    started: str,
) -> StepResult:
    """The step's result for the verdict, with the report sent to the side at fault."""
    if result.verdict == ArbitrateVerdict.CODE_BUG:
        logger.info("Arbitrate Verdict: CODE_BUG (%s)", result.spec_clause)
        feedback = with_trace(guard_coding_feedback(result.coding_feedback), failures, trace_filter)
        return _code_bug(context, from_step, result.spec_clause, feedback, started)
    if result.verdict == ArbitrateVerdict.SCENARIO_ERROR:
        logger.info("Arbitrate Verdict: SCENARIO_ERROR (%s)", result.spec_clause)
        return _scenario_error(context, from_step, result, started)
    if result.verdict == ArbitrateVerdict.SPEC_AMBIGUITY:
        logger.warning("Arbitrate Verdict: SPEC_AMBIGUITY! Pausing for HITL %s", result.spec_clause)
        return StepResult(
            status=StepStatus.WAITING_FOR_INPUT,
            output={**result.model_dump(), "spec_sha": _spec_sha(context)},
            error_message=_unclear_message(result, context),
            started_at=started,
            completed_at=_now_iso(),
        )
    return _error_result(f"Unknown verdict type {result.verdict}", started)


class ArbitrateVerdictHandler(StepHandler):
    """Diagnose test failures and route feedback to the offending party."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        started = _now_iso()
        logger.info("Executing ARBITRATE VERDICT for %s", context.run.run_id)

        # The evidence is consumed on verdict (popped only on terminal branches), so a
        # spec_ambiguity park can resume and re-arbitrate, and an ERROR retry re-reads it.
        early = _not_arbitrable(context, started)
        if early is not None:
            return early
        # Shape already validated above, so these are plain reads rather than a second guard.
        evidence = context.feedback[SCENARIO_EVIDENCE]
        if evidence.get("total", 0) == 0:
            return _nothing_ran(started)
        if evidence.get("failed", 0) == 0 and evidence.get("errors", 0) == 0:
            return _no_failures(context, evidence, started)
        if context.model.llm_router is None:
            return _error_result("LLM not configured in context", started)

        try:
            return await self._judge(step, context, evidence, started)
        except Exception as exc:
            log_step_failure(logger, "ArbitrateVerdictHandler: unhandled error")
            return _error_result(str(exc), started)

    async def _judge(
        self, step: PipelineStep, context: RunContext, evidence: dict[str, Any], started: str
    ) -> StepResult:
        """Ask the arbitration workflow for a verdict on the filtered evidence, then route it."""
        failures = evidence.get("failures", [])
        raw_tracing = evidence_text(failures, evidence.get("errors", 0), evidence.get("total", 0))

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

        from specweaver.core.flow.handlers._llm import llm_for_step

        adapter, config = llm_for_step(context, step)
        try:
            result = await arbitrate(adapter, config, base_prompt.build())
        except UnreadableVerdictError as exc:  # expected: the step fails, quoting the raw verdict
            return _error_result(str(exc), started)
        return _route(context, step.name, result, failures, filter_impl, started)
