# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""LLM-based reviewer — semantic evaluation of specs and code.

Sends structured prompts to the LLM, parses ACCEPTED/DENIED with findings.
Used for both spec review (F4) and code review (F7) with different prompts.
"""

from __future__ import annotations

import enum
import logging
import re as _re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from specweaver.infrastructure.llm.budget import BudgetExceededError
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention
    from specweaver.infrastructure.llm.models import ToolDispatcherProtocol
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class ReviewVerdict(enum.StrEnum):
    """Review outcome."""

    ACCEPTED = "accepted"
    DENIED = "denied"
    ERROR = "error"


class ReviewFinding(BaseModel):
    """A single finding from the review."""

    category: str = ""
    message: str = ""
    severity: str = "info"
    suggestion: str = ""


class ReviewResult(BaseModel):
    """Result of an LLM review."""

    verdict: ReviewVerdict
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)
    raw_response: str = ""


#: How the response must be shaped for `_parse` to read it. This is engine contract, not
#: judgment: a project that could edit it would break the parser, and the failure would surface
#: as a wrong verdict rather than as a broken rubric. The criteria it is appended to are content
#: and live in `assurance/validation/rubrics/`.
REVIEW_OUTPUT_CONTRACT = """\
## Output Format:
Start your response with either "VERDICT: ACCEPTED" or "VERDICT: DENIED".
Then list your findings, each on a new line starting with "- ".
End with a one-line summary."""


def review_instructions(criteria: str) -> str:
    """Join a rubric's criteria to the output contract the parser depends on."""
    return f"{criteria.rstrip()}\n\n{REVIEW_OUTPUT_CONTRACT}"


_VERDICT_LINE = _re.compile(
    r"^[\s#*_>]*VERDICT:\s*(ACCEPTED|DENIED)\b[*_.]*(?:\s+[-\u2014\u2013(].*)?\s*$",
    _re.IGNORECASE | _re.MULTILINE,
)


def _verdict_of(text: str) -> ReviewVerdict:
    """The first verdict line's verdict; DENIED when there is none."""
    match = _VERDICT_LINE.search(text)
    if match and match.group(1).upper() == "ACCEPTED":
        return ReviewVerdict.ACCEPTED
    return ReviewVerdict.DENIED


class Reviewer:
    """LLM-based semantic reviewer for specs and code."""

    def __init__(
        self,
        llm: LLMAdapter,
        config: GenerationConfig,
        tool_dispatcher: ToolDispatcherProtocol | None = None,
    ) -> None:
        self._llm = llm
        self._config = config
        self._tool_dispatcher = tool_dispatcher

    async def review_spec(
        self,
        spec_path: Path,
        base_prompt: PromptBuilder,
        *,
        mentioned_files: list[ResolvedMention] | None = None,
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
        environment_context: str | None = None,
    ) -> ReviewResult:
        """Review a spec file for quality and completeness.

        Args:
            spec_path: Path to the spec markdown file.
            base_prompt: Base prompt builder initialized with context.
            mentioned_files: Optional auto-detected file mentions from a prior
                pipeline step, injected as reference context (priority 4).
            on_tool_round: Optional callback for tool execution rounds.
            environment_context: Optional mapped string extracting physical MCP bounds.

        Returns:
            ReviewResult with verdict and findings.
        """
        builder = base_prompt
        builder.add_file(spec_path, priority=1, role="target")
        if mentioned_files:
            builder.add_mentioned_files(mentioned_files)
            logger.debug("review_spec: %d mentioned files injected", len(mentioned_files))
        if environment_context:
            builder.add_context(environment_context, "environment_context")
            logger.debug("review_spec: MCP env injected (%d chars)", len(environment_context))
        prompt = builder.build()
        logger.info("review_spec: reviewing %s", spec_path)
        return await self._execute_review(prompt, on_tool_round)

    async def review_code(
        self,
        code_path: Path,
        spec_path: Path,
        base_prompt: PromptBuilder,
        *,
        mentioned_files: list[ResolvedMention] | None = None,
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
        environment_context: str | None = None,
    ) -> ReviewResult:
        """Review generated code against its source spec.

        Args:
            code_path: Path to the generated code file.
            spec_path: Path to the source spec file.
            base_prompt: Base prompt builder initialized with context.
            mentioned_files: Optional auto-detected file mentions from a prior
                pipeline step, injected as reference context (priority 4).
            on_tool_round: Optional callback for tool execution rounds.
            environment_context: Optional mapped string extracting physical MCP bounds.

        Returns:
            ReviewResult with verdict and findings.
        """
        builder = base_prompt
        builder.add_file(spec_path, priority=1, label="specification", role="reference")
        builder.add_file(code_path, priority=2, label="generated_code", role="target")

        if mentioned_files:
            builder.add_mentioned_files(mentioned_files)
            logger.debug("review_code: %d mentioned files injected", len(mentioned_files))
        if environment_context:
            builder.add_context(environment_context, "environment_context")
            logger.debug("review_code: MCP env injected (%d chars)", len(environment_context))
        prompt = builder.build()
        logger.info("review_code: reviewing %s against %s", code_path, spec_path)
        return await self._execute_review(prompt, on_tool_round)

    async def _execute_review(
        self,
        prompt: str,
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
    ) -> ReviewResult:
        """Send a review prompt to the LLM and parse the response."""
        messages = [
            Message(
                role=Role.SYSTEM,
                content="You are a code review expert. Be thorough but fair.",
            ),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            if self._tool_dispatcher:
                config = self._config.model_copy(
                    update={"tools": self._tool_dispatcher.available_tools()},
                )
                response = await self._llm.generate_with_tools(
                    messages,
                    config,
                    self._tool_dispatcher,
                    on_tool_round=on_tool_round,
                )
            else:
                response = await self._llm.generate(messages, self._config)
        except BudgetExceededError:
            # A verdict of ERROR reads as "the review found problems". Out of budget is not a
            # review outcome, and burying it here would let the pipeline continue past a
            # tripped breaker.
            raise
        except Exception as exc:
            logger.debug("Review LLM call failed: %s", str(exc))
            return ReviewResult(
                verdict=ReviewVerdict.ERROR,
                summary=f"Review failed: {exc}",
                raw_response="",
            )

        result = self._parse_response(response.text)
        logger.info(
            "Review result: verdict=%s, findings=%d",
            result.verdict,
            len(result.findings),
        )
        return result

    def _parse_response(self, text: str) -> ReviewResult:
        """Parse LLM response into a ReviewResult."""
        raw = text.strip()

        verdict = _verdict_of(raw)

        # Extract findings (lines starting with "- ")
        findings: list[ReviewFinding] = []
        lines = raw.split("\n")
        summary_line = ""

        for line in lines:
            line = line.strip()
            if line.startswith("- "):
                findings.append(ReviewFinding(message=line[2:].strip()))
            elif line and not line.startswith("VERDICT"):
                summary_line = line  # Last non-empty, non-finding line = summary

        return ReviewResult(
            verdict=verdict,
            summary=summary_line,
            findings=findings,
            raw_response=raw,
        )


def result_from_run(run_state: Any) -> ReviewResult:
    """The `ReviewResult` a finished review run produced, or an ERROR result if it produced none.

    A pipeline that failed before its handler ran leaves no result to read, and that is not the
    same as a review that returned ERROR — hence the distinct summary.
    """
    last_record = run_state.step_records[-1] if run_state.step_records else None
    if not (last_record and last_record.result):
        return ReviewResult(
            verdict=ReviewVerdict.ERROR,
            summary="Review failed: pipeline did not produce a valid result.",
        )

    out = last_record.result.output
    try:
        verdict = ReviewVerdict(out.get("verdict", "error"))
    except ValueError:
        verdict = ReviewVerdict.ERROR

    return ReviewResult(
        verdict=verdict,
        summary=out.get("summary", last_record.result.error_message),
        findings=[
            ReviewFinding(**f) if isinstance(f, dict) else f for f in out.get("findings", [])
        ],
    )
