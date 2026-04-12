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
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from specweaver.infrastructure.llm.models import GenerationConfig, Message, ProjectMetadata, Role

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from specweaver.assurance.graph.topology import TopologyContext
    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention
    from specweaver.infrastructure.llm.models import ToolDispatcherProtocol

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
    confidence: int = 0
    below_threshold: bool = False


class ReviewResult(BaseModel):
    """Result of an LLM review."""

    verdict: ReviewVerdict
    summary: str = ""
    findings: list[ReviewFinding] = Field(default_factory=list)
    raw_response: str = ""

    @property
    def above_threshold_findings(self) -> list[ReviewFinding]:
        """Return only findings that are at or above the confidence threshold."""
        return [f for f in self.findings if not f.below_threshold]


# Instruction constants — extracted for reuse and testability
SPEC_REVIEW_INSTRUCTIONS = """\
You are a senior software architect reviewing a component specification.
Your job is to evaluate whether this spec is CLEAR, COMPLETE, and IMPLEMENTABLE.

## Review Criteria:
1. **Clarity**: Is every term defined? Are there ambiguous statements?
2. **Completeness**: Does it cover happy path AND error paths?
3. **Implementability**: Can a developer write code from this spec WITHOUT guessing?
4. **Testability**: Can tests be written from the Contract section alone?
5. **Single Responsibility**: Does it describe ONE component doing ONE thing?

## Output Format:
Start your response with either "VERDICT: ACCEPTED" or "VERDICT: DENIED".
Then list your findings, each on a new line starting with "- ".
For each finding, append a confidence score: [confidence: N] where N is 0-100.
End with a one-line summary."""

CODE_REVIEW_INSTRUCTIONS = """\
You are a senior software engineer reviewing generated code against its source specification.

## Review Criteria:
1. **Spec Compliance**: Does the code implement what the spec describes?
2. **Contract Match**: Do function signatures match the spec's Contract section?
3. **Error Handling**: Are all error cases from the spec's Policy section handled?
4. **No Hallucination**: Does the code add behavior NOT in the spec?
5. **Test Coverage**: If tests are included, do they cover the spec's examples?

## Output Format:
Start your response with either "VERDICT: ACCEPTED" or "VERDICT: DENIED".
Then list your findings, each on a new line starting with "- ".
For each finding, append a confidence score: [confidence: N] where N is 0-100.
End with a one-line summary."""


class Reviewer:
    """LLM-based semantic reviewer for specs and code."""

    def __init__(
        self,
        llm: LLMAdapter,
        config: GenerationConfig | None = None,
        confidence_threshold: int = 80,
        tool_dispatcher: ToolDispatcherProtocol | None = None,
    ) -> None:
        self._llm = llm
        self._config = config or GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=0.3,
            max_output_tokens=4096,
        )
        self._confidence_threshold = confidence_threshold
        self._tool_dispatcher = tool_dispatcher

    async def review_spec(
        self,
        spec_path: Path,
        *,
        topology_contexts: list[TopologyContext] | None = None,
        constitution: str | None = None,
        standards: str | None = None,
        mentioned_files: list[ResolvedMention] | None = None,
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
        project_metadata: ProjectMetadata | None = None,
    ) -> ReviewResult:
        """Review a spec file for quality and completeness.

        Args:
            spec_path: Path to the spec markdown file.
            topology_contexts: Optional topology context from the project graph.
            constitution: Optional constitution content to inject.
            standards: Optional project standards to inject.
            mentioned_files: Optional auto-detected file mentions from a prior
                pipeline step, injected as reference context (priority 4).

        Returns:
            ReviewResult with verdict and findings.
        """
        from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

        builder = (
            PromptBuilder()
            .add_instructions(SPEC_REVIEW_INSTRUCTIONS)
            .add_project_metadata(project_metadata)
            .add_file(spec_path, priority=1, role="target")
        )
        if constitution:
            builder.add_constitution(constitution)
            logger.debug("review_spec: constitution injected (%d chars)", len(constitution))
        if standards:
            builder.add_standards(standards)
            logger.debug("review_spec: standards injected (%d chars)", len(standards))
        if topology_contexts:
            builder.add_topology(topology_contexts)
        if mentioned_files:
            builder.add_mentioned_files(mentioned_files)
            logger.debug("review_spec: %d mentioned files injected", len(mentioned_files))
        prompt = builder.build()
        logger.info("review_spec: reviewing %s", spec_path)
        return await self._execute_review(prompt)

    async def review_code(
        self,
        code_path: Path,
        spec_path: Path,
        *,
        topology_contexts: list[TopologyContext] | None = None,
        constitution: str | None = None,
        standards: str | None = None,
        mentioned_files: list[ResolvedMention] | None = None,
        on_tool_round: Callable[[int, list[Message]], None] | None = None,
        project_metadata: ProjectMetadata | None = None,
    ) -> ReviewResult:
        """Review generated code against its source spec.

        Args:
            code_path: Path to the generated code file.
            spec_path: Path to the source spec file.
            topology_contexts: Optional topology context from the project graph.
            constitution: Optional constitution content to inject.
            standards: Optional project standards to inject.
            mentioned_files: Optional auto-detected file mentions from a prior
                pipeline step, injected as reference context (priority 4).

        Returns:
            ReviewResult with verdict and findings.
        """
        from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

        builder = (
            PromptBuilder()
            .add_instructions(CODE_REVIEW_INSTRUCTIONS)
            .add_project_metadata(project_metadata)
            .add_file(spec_path, priority=1, label="specification", role="reference")
            .add_file(code_path, priority=2, label="generated_code", role="target")
        )
        if constitution:
            builder.add_constitution(constitution)
            logger.debug("review_code: constitution injected (%d chars)", len(constitution))
        if standards:
            builder.add_standards(standards)
            logger.debug("review_code: standards injected (%d chars)", len(standards))
        if topology_contexts:
            builder.add_topology(topology_contexts)
        if mentioned_files:
            builder.add_mentioned_files(mentioned_files)
            logger.debug("review_code: %d mentioned files injected", len(mentioned_files))
        prompt = builder.build()
        logger.info("review_code: reviewing %s against %s", code_path, spec_path)
        return await self._execute_review(prompt)

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

        # Determine verdict
        upper_text = raw.upper()
        if "VERDICT: ACCEPTED" in upper_text:
            verdict = ReviewVerdict.ACCEPTED
        elif "VERDICT: DENIED" in upper_text:
            verdict = ReviewVerdict.DENIED
        else:
            # If no clear verdict, treat as denied (conservative)
            verdict = ReviewVerdict.DENIED

        # Extract findings (lines starting with "- ")
        findings: list[ReviewFinding] = []
        lines = raw.split("\n")
        summary_line = ""

        for line in lines:
            line = line.strip()
            if line.startswith("- "):
                message = line[2:].strip()
                confidence = self._extract_confidence(message)
                # Strip the confidence tag from the message
                message = _re.sub(r"\s*\[confidence:\s*\d+\]", "", message).strip()
                findings.append(
                    ReviewFinding(
                        message=message,
                        confidence=confidence,
                        below_threshold=confidence < self._confidence_threshold,
                    )
                )
            elif line and not line.startswith("VERDICT"):
                summary_line = line  # Last non-empty, non-finding line = summary

        return ReviewResult(
            verdict=verdict,
            summary=summary_line,
            findings=findings,
            raw_response=raw,
        )

    @staticmethod
    def _extract_confidence(text: str) -> int:
        """Extract confidence score from [confidence: N] tag in text."""
        match = _re.search(r"\[confidence:\s*(\d+)\]", text)
        return int(match.group(1)) if match else 0
