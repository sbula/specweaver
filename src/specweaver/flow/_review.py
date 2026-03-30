# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Review step handlers — LLM-based spec and code review."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.flow._base import RunContext, _error_result, _now_iso
from specweaver.flow.state import StepResult, StepStatus

if TYPE_CHECKING:
    from specweaver.flow.models import PipelineStep
    from specweaver.llm.mention_scanner.models import ResolvedMention
    from specweaver.llm.models import GenerationConfig, Message
    from specweaver.loom.dispatcher import ToolDispatcher

logger = logging.getLogger(__name__)


def _resolve_review_routing(context: RunContext) -> tuple[Any, GenerationConfig]:
    """Resolve the adapter and config for review, routing if enabled, else default."""
    from specweaver.llm.models import GenerationConfig, TaskType

    routed = (
        context.llm_router.get_for_task(TaskType.REVIEW)
        if getattr(context, "llm_router", None)
        else None
    )
    adapter = routed.adapter if routed else context.llm

    if routed:
        config = GenerationConfig(
            model=routed.model,
            temperature=routed.temperature,
            max_output_tokens=routed.max_output_tokens,
            task_type=TaskType.REVIEW,
            run_id=getattr(context, "run_id", "") or "",
        )
    elif context.config is not None:
        config = GenerationConfig(
            model=context.config.llm.model,
            temperature=0.3,
            max_output_tokens=context.config.llm.max_output_tokens,
            task_type=TaskType.REVIEW,
            run_id=getattr(context, "run_id", "") or "",
        )
    else:
        config = GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=0.3,
            max_output_tokens=4096,
            task_type=TaskType.REVIEW,
            run_id=getattr(context, "run_id", "") or "",
        )

    return adapter, config


def _build_tool_dispatcher(context: RunContext, role: str) -> ToolDispatcher | None:
    """Build a ToolDispatcher from RunContext if workspace boundaries exist.

    Returns None when research tools should not be available, preserving
    backwards compatibility with contexts that don't set workspace roots
    or when the LLM doesn't support tool use.
    """
    import os

    from specweaver.loom.dispatcher import ToolDispatcher
    from specweaver.loom.security import WorkspaceBoundary

    # Only enable when the LLM actually supports tool use
    if not hasattr(context.llm, "generate_with_tools"):
        return None

    try:
        boundary = WorkspaceBoundary.from_run_context(context)
    except (ValueError, AttributeError):
        return None

    allowed_tools = ["fs"]
    if bool(os.environ.get("SEARCH_API_KEY")):
        allowed_tools.append("web")

    return ToolDispatcher.create_standard_set(boundary, role=role, allowed_tools=allowed_tools)


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

            adapter, config = _resolve_review_routing(context)
            reviewer = Reviewer(
                llm=adapter,
                config=config,
                tool_dispatcher=_build_tool_dispatcher(context, role="reviewer"),
            )

            def on_tool_round(round_num: int, messages: list[Message]) -> None:
                from specweaver.llm.mention_scanner import extract_mentions
                from specweaver.llm.models import Message, Role

                last_msg = messages[-1]
                if last_msg.role == Role.ASSISTANT:
                    candidates = extract_mentions(last_msg.content)
                    if candidates:
                        resolved = _resolve_mentions(
                            candidates,
                            context.project_path,
                            workspace_roots=(
                                [context.project_path / r for r in context.workspace_roots]
                                if context.workspace_roots
                                else None
                            ),
                        )
                        if resolved:
                            for r in resolved:
                                with contextlib.suppress(OSError):
                                    messages.append(
                                        Message(
                                            role=Role.USER,
                                            content=f"Auto-resolved file `{r.original}`:\\n\\n```\\n{r.resolved_path.read_text('utf-8')}\\n```",
                                        )
                                    )

            result = await reviewer.review_spec(
                context.spec_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
                standards=context.standards,
                mentioned_files=_get_prior_mentions(context),
                on_tool_round=on_tool_round,
                project_metadata=context.project_metadata,
            )
            logger.info(
                "ReviewSpecHandler: verdict=%s, findings=%d",
                result.verdict.value,
                len(result.findings),
            )

            # 3.11: Scan LLM response for file mentions
            _scan_and_store_mentions(result.raw_response, context)

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

            target_param = step.params.get("target_path") if step.params else None
            code_path = Path(target_param) if target_param else self._find_code_path(context)

            if code_path is None:
                return _error_result("No code file found for review", started)

            adapter, config = _resolve_review_routing(context)
            reviewer = Reviewer(
                llm=adapter,
                config=config,
                tool_dispatcher=_build_tool_dispatcher(context, role="reviewer"),
            )

            def on_tool_round(round_num: int, messages: list[Message]) -> None:
                from specweaver.llm.mention_scanner import extract_mentions
                from specweaver.llm.models import Message, Role

                last_msg = messages[-1]
                if last_msg.role == Role.ASSISTANT:
                    candidates = extract_mentions(last_msg.content)
                    if candidates:
                        resolved = _resolve_mentions(
                            candidates,
                            context.project_path,
                            workspace_roots=(
                                [context.project_path / r for r in context.workspace_roots]
                                if context.workspace_roots
                                else None
                            ),
                        )
                        if resolved:
                            for r in resolved:
                                with contextlib.suppress(OSError):
                                    messages.append(
                                        Message(
                                            role=Role.USER,
                                            content=f"Auto-resolved file `{r.original}`:\\n\\n```\\n{r.resolved_path.read_text('utf-8')}\\n```",
                                        )
                                    )

            result = await reviewer.review_code(
                code_path,
                context.spec_path,
                topology_contexts=([context.topology] if context.topology else None),
                constitution=context.constitution,
                standards=context.standards,
                mentioned_files=_get_prior_mentions(context),
                on_tool_round=on_tool_round,
                project_metadata=context.project_metadata,
            )
            logger.info(
                "ReviewCodeHandler: verdict=%s, findings=%d",
                result.verdict.value,
                len(result.findings),
            )

            # 3.11: Scan LLM response for file mentions
            _scan_and_store_mentions(result.raw_response, context)

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
    ``context.project_path`` (or ``context.workspace_roots``) are included.
    """
    from specweaver.llm.mention_scanner import extract_mentions

    candidates = extract_mentions(raw_response)
    if not candidates:
        return

    resolved = _resolve_mentions(
        candidates,
        context.project_path,
        workspace_roots=(
            [context.project_path / r for r in context.workspace_roots]
            if context.workspace_roots
            else None
        ),
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
    workspace_roots: list[Path] | None = None,
    max_files: int = 5,
) -> list[ResolvedMention]:
    """Resolve candidate path strings to actual files on disk.

    Only files within the project or workspace boundaries are included.
    Spec files (kind="spec") are prioritized over other kinds.
    """
    from specweaver.llm.mention_scanner.models import ResolvedMention

    roots = [project_path]
    if workspace_roots:
        roots.extend(workspace_roots)

    resolved: list[ResolvedMention] = []
    seen_paths: set[Path] = set()

    for candidate in candidates:
        for root in roots:
            candidate_path = root / candidate
            try:
                # Resolve symlinks and normalize
                resolved_path = candidate_path.resolve(strict=False)
            except (OSError, ValueError):
                continue

            # Workspace boundary check: must be within a root
            if not any(_is_within(resolved_path, r) for r in roots):
                continue

            if resolved_path.is_file() and resolved_path not in seen_paths:
                seen_paths.add(resolved_path)
                kind = ResolvedMention.classify(resolved_path)
                resolved.append(
                    ResolvedMention(
                        original=candidate,
                        resolved_path=resolved_path,
                        kind=kind,
                    ),
                )
                break  # Found a match for this candidate; next candidate

    # Prioritize specs, then cap
    resolved.sort(key=lambda m: 0 if m.kind == "spec" else 1)
    return resolved[:max_files]


def _is_within(path: Path, root: Path) -> bool:
    """Check if path is within root directory."""
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True
