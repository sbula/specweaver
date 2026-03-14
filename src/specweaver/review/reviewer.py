# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM-based reviewer — semantic evaluation of specs and code.

Sends structured prompts to the LLM, parses ACCEPTED/DENIED with findings.
Used for both spec review (F4) and code review (F7) with different prompts.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from specweaver.llm.models import GenerationConfig, Message, Role

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.llm.adapter import LLMAdapter


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
End with a one-line summary."""


class Reviewer:
    """LLM-based semantic reviewer for specs and code."""

    def __init__(
        self,
        llm: LLMAdapter,
        config: GenerationConfig | None = None,
    ) -> None:
        self._llm = llm
        self._config = config or GenerationConfig(
            model="gemini-2.5-flash",
            temperature=0.3,  # Lower temperature for more consistent reviews
        )

    async def review_spec(self, spec_path: Path) -> ReviewResult:
        """Review a spec file for quality and completeness.

        Args:
            spec_path: Path to the spec markdown file.

        Returns:
            ReviewResult with verdict and findings.
        """
        from specweaver.llm.prompt_builder import PromptBuilder

        prompt = (
            PromptBuilder()
            .add_instructions(SPEC_REVIEW_INSTRUCTIONS)
            .add_file(spec_path, priority=1)
            .build()
        )
        return await self._execute_review(prompt)

    async def review_code(self, code_path: Path, spec_path: Path) -> ReviewResult:
        """Review generated code against its source spec.

        Args:
            code_path: Path to the generated code file.
            spec_path: Path to the source spec file.

        Returns:
            ReviewResult with verdict and findings.
        """
        from specweaver.llm.prompt_builder import PromptBuilder

        prompt = (
            PromptBuilder()
            .add_instructions(CODE_REVIEW_INSTRUCTIONS)
            .add_file(spec_path, priority=1, label="specification")
            .add_file(code_path, priority=2, label="generated_code")
            .build()
        )
        return await self._execute_review(prompt)

    async def _execute_review(self, prompt: str) -> ReviewResult:
        """Send a review prompt to the LLM and parse the response."""
        messages = [
            Message(
                role=Role.SYSTEM,
                content="You are a code review expert. Be thorough but fair.",
            ),
            Message(role=Role.USER, content=prompt),
        ]

        try:
            response = await self._llm.generate(messages, self._config)
        except Exception as exc:
            return ReviewResult(
                verdict=ReviewVerdict.ERROR,
                summary=f"Review failed: {exc}",
                raw_response="",
            )

        return self._parse_response(response.text)

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
                findings.append(ReviewFinding(message=line[2:].strip()))
            elif line and not line.startswith("VERDICT"):
                summary_line = line  # Last non-empty, non-finding line = summary

        return ReviewResult(
            verdict=verdict,
            summary=summary_line,
            findings=findings,
            raw_response=raw,
        )
