# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Review step handlers — LLM-based spec and code review."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING, Any

from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.handlers.base import _error_result, _now_iso
from specweaver.core.flow.handlers.mcp_assembler import evaluate_and_fetch_mcp_context
from specweaver.core.flow.handlers.results import log_step_failure

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineStep
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention
    from specweaver.infrastructure.llm.models import GenerationConfig, Message
    from specweaver.sandbox.dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)


def _resolve_review_routing(context: RunContext) -> tuple[Any, GenerationConfig]:
    """The adapter and settings for review."""
    from specweaver.core.flow.handlers._llm import llm_for
    from specweaver.infrastructure.llm.models import TaskType

    return llm_for(context, TaskType.REVIEW)


def _build_tool_dispatcher(context: RunContext, role: str, adapter: Any) -> ToolDispatcher | None:
    """Build a ToolDispatcher from RunContext if workspace boundaries exist.

    Returns None when research tools should not be available: no workspace boundary, or an LLM
    without tool use.
    """
    from specweaver.sandbox.dispatcher import ToolDispatcher
    from specweaver.sandbox.security import WorkspaceBoundary

    # Only when the step's adapter actually supports tool use.
    if not hasattr(adapter, "generate_with_tools"):
        return None

    try:
        boundary = WorkspaceBoundary.from_run_context(context)
    except (ValueError, AttributeError) as exc:
        logger.warning("The reviewer gets no file tools: no workspace boundary (%s)", exc)
        return None

    search_key = context.model.llm_router.search_key
    allowed_tools = ["fs", "ast", "web"] if search_key else ["fs", "ast"]

    return ToolDispatcher.create_standard_set(
        boundary,
        role=role,
        allowed_tools=allowed_tools,
        analyzer_factory=context.analysis.analyzer_factory,
        topology=context.graph.topology,
        search_key=search_key,
    )


def _inject_resolved_mentions(messages: list[Any], context: RunContext) -> None:
    """Append the contents of any files the assistant @-mentioned, as extra USER turns.

    Shared by `ReviewSpecHandler` and `ReviewCodeHandler`, which is the point: as two copies they
    drift, and one such copy used `\\n` (a literal backslash and an n) where the other used `\n`,
    feeding the model a single run-on line with visible `\n` characters instead
    of a fenced block. Unifying fixes that by construction.

    Never raises: an unreadable resolved path is suppressed, because losing one auto-attached file
    must not fail a review that has otherwise succeeded.
    """

    from specweaver.infrastructure.llm.mention_scanner.scanner import extract_mentions
    from specweaver.infrastructure.llm.models import Message, Role

    last_msg = messages[-1]
    if last_msg.role != Role.ASSISTANT:
        return

    candidates = extract_mentions(last_msg.content)
    if not candidates:
        return

    resolved = _resolve_mentions(
        candidates,
        context.project_path,
    )
    for r in resolved or []:
        with contextlib.suppress(OSError):
            messages.append(
                Message(
                    role=Role.USER,
                    content=(
                        f"Auto-resolved file `{r.original}`:\n\n"
                        f"```\n{r.resolved_path.read_text('utf-8')}\n```"
                    ),
                )
            )


def resolve_review_instructions(context: RunContext, rubric_id: str) -> tuple[str, Any]:
    """Load the criteria that should judge this run and join them to the parser's contract; also
    give back the rubric, so the verdict can name it.

    The project's own `.specweaver/rubrics/` wins over the shipped defaults, and the run's DAL
    selects a stricter variant where one exists. A rubric that cannot be found is not silently
    replaced by empty criteria — an unjudged review that reports a verdict is worse than a
    failure.
    """
    from specweaver.workflows.review.reviewer import review_instructions

    rubric = _load_review_rubric(context, rubric_id)
    return review_instructions(rubric.criteria), rubric


def _load_review_rubric(context: RunContext, rubric_id: str) -> Any:
    """The rubric that judges this run: the project's own first, then the run DAL's variant."""
    from specweaver.assurance.validation.rubrics import load_rubric

    rubric = load_rubric(
        rubric_id,
        project_dir=context.project_path,
        dal=context.isolation.dal_level,
    )
    logger.debug(
        "Review rubric %s v%s (%s) from %s",
        rubric.id,
        rubric.version,
        rubric.checksum[:12],
        rubric.source,
    )
    return rubric


def _rubric_record(rubric: Any) -> dict[str, str]:
    """Which criteria judged a verdict, saved beside it."""
    return {
        "id": rubric.id,
        "version": rubric.version,
        "checksum": rubric.checksum,
        "source": str(rubric.source),
    }


async def _build_review_prompt(
    context: RunContext,
    step: PipelineStep,
    rubric_id: str,
    *,
    extra_targets: list[str] | None = None,
) -> tuple[Any, Any]:
    """Assemble what a review step sends — skeleton context, criteria, topology — and the rubric
    whose criteria it carries.

    Raises `ValueError` when the step names a render profile that does not exist; the caller turns
    that into a step failure.
    """
    from specweaver.core.flow.handlers._profiles import FULL, resolve_profile
    from specweaver.core.flow.handlers.base import _build_base_prompt
    from specweaver.core.flow.handlers.context_assembler import (
        evaluate_and_fetch_skeleton_context,
    )

    targets: list[str] = list(context.graph.api_contract_paths or [])
    for target in extra_targets or []:
        if target not in targets:
            targets.append(target)
    skeleton_files = await asyncio.to_thread(evaluate_and_fetch_skeleton_context, context, targets)

    instructions, rubric = resolve_review_instructions(context, rubric_id)
    base_prompt = await _build_base_prompt(
        context,
        instructions,
        profile=resolve_profile(step.params.get("render_profile"), default=FULL),
        skeleton_files=skeleton_files,
    )
    if context.graph.topology:
        base_prompt.add_topology([context.graph.topology])
    return base_prompt, rubric


class ReviewSpecHandler:
    """Handler for review+spec — LLM-based spec review."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        if context.model.llm_router is None:
            logger.error("ReviewSpecHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for review steps", started)

        logger.debug("ReviewSpecHandler: reviewing spec '%s'", context.spec_path.name)
        try:
            from specweaver.workflows.review.reviewer import Reviewer

            adapter, config = _resolve_review_routing(context)
            reviewer = Reviewer(
                llm=adapter,
                config=config,
                tool_dispatcher=_build_tool_dispatcher(context, role="reviewer", adapter=adapter),
            )

            mcp_env = await evaluate_and_fetch_mcp_context(context)

            try:
                base_prompt, rubric = await _build_review_prompt(context, step, "spec_review")
            except ValueError as e:
                return _error_result(str(e), started)
            from specweaver.core.flow.handlers.spec_map import signature_conflicts, spec_map

            base_prompt.add_context(spec_map(context), "other_specs")
            clashes = signature_conflicts(context)
            if clashes:
                base_prompt.add_context("\n".join(clashes), "known_conflicts")

            result = await reviewer.review_spec(
                context.spec_path,
                base_prompt=base_prompt,
                mentioned_files=_get_prior_mentions(context),
                on_tool_round=lambda rn, msgs: self._inject_mentions(rn, msgs, context),
                environment_context=mcp_env,
            )
            logger.info(
                "ReviewSpecHandler: verdict=%s, findings=%d",
                result.verdict.value,
                len(result.findings),
            )

            # 3.11: Scan LLM response for file mentions
            _scan_and_store_mentions(result.raw_response, context)

            result = _judge_conflicts(result, clashes, context)
            if result.verdict.value == "accepted":
                from specweaver.core.flow.handlers.reviewed_spec import record_review

                record_review(context)
            return _review_step_result(result, started, rubric)
        except Exception as exc:
            log_step_failure(logger, "ReviewSpecHandler: unhandled exception during spec review")
            return _error_result(str(exc), started)

    @staticmethod
    def _inject_mentions(round_num: int, messages: list[Any], context: RunContext) -> None:
        """Kept as a method: it is referenced directly by the `on_tool_round` lambda above."""
        del round_num
        _inject_resolved_mentions(messages, context)


class ReviewCodeHandler:
    """Handler for review+code — LLM-based code review."""

    async def execute(self, step: PipelineStep, context: RunContext) -> StepResult:
        logger.debug("Executing %s", self.__class__.__name__)
        started = _now_iso()
        if context.model.llm_router is None:
            logger.error("ReviewCodeHandler: LLM adapter required but not configured")
            return _error_result("LLM adapter required for review steps", started)

        try:
            from specweaver.core.flow.handlers.qa_targets import step_file
            from specweaver.workflows.review.reviewer import Reviewer

            try:
                code_path = step_file(step, context)
            except ValueError as exc:
                return _error_result(str(exc), started)
            if code_path is None:
                return _error_result("No code file found for review", started)

            adapter, config = _resolve_review_routing(context)
            reviewer = Reviewer(
                llm=adapter,
                config=config,
                tool_dispatcher=_build_tool_dispatcher(context, role="reviewer", adapter=adapter),
            )

            def on_tool_round(round_num: int, messages: list[Message]) -> None:
                del round_num
                _inject_resolved_mentions(messages, context)

            mcp_env = await evaluate_and_fetch_mcp_context(context)

            try:
                base_prompt, rubric = await _build_review_prompt(
                    context,
                    step,
                    "code_review",
                    extra_targets=[str(code_path)] if code_path else None,
                )
            except ValueError as e:
                return _error_result(str(e), started)

            result = await reviewer.review_code(
                code_path,
                context.spec_path,
                base_prompt=base_prompt,
                mentioned_files=_get_prior_mentions(context),
                on_tool_round=on_tool_round,
                environment_context=mcp_env,
            )
            logger.info(
                "ReviewCodeHandler: verdict=%s, findings=%d",
                result.verdict.value,
                len(result.findings),
            )

            # 3.11: Scan LLM response for file mentions
            _scan_and_store_mentions(result.raw_response, context)

            return _review_step_result(result, started, rubric)
        except Exception as exc:
            log_step_failure(logger, "ReviewCodeHandler: unhandled exception during code review")
            return _error_result(str(exc), started)


# ---------------------------------------------------------------------------
# 3.11 — Mention scanning helpers
# ---------------------------------------------------------------------------


def _get_prior_mentions(context: RunContext) -> list[ResolvedMention] | None:
    """Read auto-detected file mentions stored by a prior pipeline step.

    Returns None if no prior step stored mentions.
    """
    mentions = context.feedback.get("mention_scanner:resolved")
    if mentions and isinstance(mentions, list):
        return mentions  # type: ignore[no-any-return]
    return None


def _scan_and_store_mentions(
    raw_response: str,
    context: RunContext,
) -> None:
    """Scan LLM response for file mentions and store in context.feedback.

    Resolution respects workspace boundaries: only files within
    ``context.project_path`` are included.
    """
    from specweaver.infrastructure.llm.mention_scanner.scanner import extract_mentions

    candidates = extract_mentions(raw_response)
    if not candidates:
        return

    resolved = _resolve_mentions(
        candidates,
        context.project_path,
    )

    if resolved:
        context.feedback["mention_scanner:resolved"] = resolved
        names = [m.resolved_path.name for m in resolved]
        logger.info(
            "Auto-detected %d file mentions: %s",
            len(resolved),
            ", ".join(names),
        )


def _resolve_mentions(
    candidates: list[str],
    project_path: Path,
    *,
    max_files: int = 5,
) -> list[ResolvedMention]:
    """Resolve candidate path strings to actual files on disk.

    Only files within the project are included.
    Spec files (kind="spec") are prioritized over other kinds.
    """
    from specweaver.core.flow.engine.project_paths import ProjectPathError, project_file
    from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention

    resolved: list[ResolvedMention] = []
    seen_paths: set[Path] = set()

    for candidate in candidates:
        try:
            resolved_path = project_file(project_path, candidate)
        except ProjectPathError:
            logger.debug("Mention %r is outside the project", candidate)
            continue
        if resolved_path.is_file() and resolved_path not in seen_paths:
            seen_paths.add(resolved_path)
            resolved.append(
                ResolvedMention(
                    original=candidate,
                    resolved_path=resolved_path,
                    kind=ResolvedMention.classify(resolved_path),
                ),
            )

    # Prioritize specs, then cap
    resolved.sort(key=lambda m: 0 if m.kind == "spec" else 1)
    return resolved[:max_files]


def _judge_conflicts(result: Any, clashes: list[str], context: RunContext) -> Any:
    """A proven conflict, or a contract clash the check found, denies; an unproven one only warns."""
    from specweaver.core.flow.handlers.spec_map import is_conflict, proven
    from specweaver.workflows.review.reviewer import ReviewFinding, ReviewVerdict

    if not clashes and not any(is_conflict(f.message) for f in result.findings):
        return result
    findings, denies = [], bool(clashes)
    for finding in result.findings:
        if is_conflict(finding.message) and not proven(finding.message, context):
            finding = finding.model_copy(update={"message": f"UNPROVEN {finding.message}"})
        elif is_conflict(finding.message):
            denies = True
        findings.append(finding)
    findings += [ReviewFinding(category="conflict", message=clash) for clash in clashes]
    verdict = result.verdict
    if denies and verdict == ReviewVerdict.ACCEPTED:
        verdict = ReviewVerdict.DENIED
    return result.model_copy(update={"findings": findings, "verdict": verdict})


def _review_step_result(result: Any, started: str, rubric: Any) -> StepResult:
    """Accepted passes, denied fails; a review that could not run is an error that says why."""
    verdict = result.verdict.value
    status = {"accepted": StepStatus.PASSED, "error": StepStatus.ERROR}.get(
        verdict, StepStatus.FAILED
    )
    return StepResult(
        status=status,
        output={
            "verdict": verdict,
            "summary": result.summary,
            "findings_count": len(result.findings),
            # The finding TEXTS, not just a count: the inline report and the loop_back
            # feedback to the re-draft both need them.
            "findings": [f.model_dump() for f in result.findings],
            "rubric": _rubric_record(rubric),
        },
        error_message="" if status is StepStatus.PASSED else _failure_reason(verdict, result),
        started_at=started,
        completed_at=_now_iso(),
    )


def _failure_reason(verdict: str, result: Any) -> str:
    if verdict == "error":
        return result.summary or "the review could not run"
    return f"review {verdict}: {result.summary}" if result.summary else f"review {verdict}"
