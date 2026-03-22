# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Planner — LLM-driven implementation plan generation from specs.

Reads an approved spec, generates a structured PlanArtifact via LLM,
and validates the JSON output using reflection retry (max N attempts).
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from specweaver.llm.models import GenerationConfig, Message, Role
from specweaver.planning.models import PlanArtifact

if TYPE_CHECKING:
    from specweaver.llm.adapters.base import LLMAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

PLAN_SYSTEM_PROMPT = """\
You are an implementation planner for a Python project. Given a component \
specification, you produce a structured implementation plan as JSON.

Your output must be ONLY valid JSON matching the PlanArtifact schema. \
No markdown fences, no explanation."""

# ---------------------------------------------------------------------------
# User prompt template
# ---------------------------------------------------------------------------

PLAN_USER_TEMPLATE = """\
Generate an implementation plan for the following specification.

## Specification
{spec_content}

## Output Schema
Return a JSON object with these fields:
- spec_path (str): "{spec_path}"
- spec_name (str): "{spec_name}"
- spec_hash (str): "{spec_hash}"
- timestamp (str): current ISO-8601 timestamp
- file_layout (list): files to create/modify/delete, each with:
  - path (str), action ("create"|"modify"|"delete"), purpose (str), dependencies (list[str])
- architecture (object|null): module_layout, dependency_direction, archetype, patterns
- tech_stack (list): category, choice, rationale, alternatives_considered
- constraints (list): source, constraint, impact
- tasks (list): name, description, files, dependencies
- test_expectations (list): name, description, function_under_test, input_summary, expected_behavior, category ("happy"|"error"|"boundary")
- reasoning (str): your chain-of-thought
- confidence (int): 0-100

{extra_context}
Return ONLY the JSON object."""

# ---------------------------------------------------------------------------
# Reflection retry prompt
# ---------------------------------------------------------------------------

RETRY_PROMPT_TEMPLATE = """\
Your previous response was not valid JSON. The error was:

{error}

Please fix the output and return ONLY valid JSON matching the schema."""


class Planner:
    """LLM-driven plan generator with reflection retry.

    Args:
        llm: LLM adapter for generation.
        max_retries: Maximum reflection retries on JSON validation failure.
    """

    def __init__(
        self,
        llm: LLMAdapter,
        *,
        max_retries: int = 3,
        config: GenerationConfig | None = None,
    ) -> None:
        self._llm = llm
        self._max_retries = max_retries
        self._config = config or GenerationConfig(
            model="gemini-2.5-flash",
            temperature=0.3,
        )

    async def generate_plan(
        self,
        spec_content: str,
        spec_path: str,
        spec_name: str,
        *,
        constitution: str | None = None,
        standards: str | None = None,
    ) -> PlanArtifact:
        """Generate an implementation plan from spec content.

        Args:
            spec_content: The spec text.
            spec_path: Path to the spec file (stored in the plan).
            spec_name: Human-readable spec name.
            constitution: Optional constitution content.
            standards: Optional project standards.

        Returns:
            A validated PlanArtifact.

        Raises:
            ValueError: If all retries fail to produce valid JSON.
        """
        spec_hash = hashlib.sha256(spec_content.encode()).hexdigest()

        extra_parts: list[str] = []
        if constitution:
            extra_parts.append(f"## Constitution\n{constitution}")
        if standards:
            extra_parts.append(f"## Standards\n{standards}")
        extra_context = "\n\n".join(extra_parts)

        user_prompt = PLAN_USER_TEMPLATE.format(
            spec_content=spec_content,
            spec_path=spec_path,
            spec_name=spec_name,
            spec_hash=spec_hash,
            extra_context=extra_context,
        )

        messages: list[Message] = [
            Message(role=Role.SYSTEM, content=PLAN_SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_prompt),
        ]

        for attempt in range(1, self._max_retries + 1):
            logger.debug("Planner: attempt %d/%d", attempt, self._max_retries)
            response = await self._llm.generate(messages, self._config)
            raw = self._clean_json(response.text)

            try:
                data = json.loads(raw)
                plan = PlanArtifact.model_validate(data)
                # Ensure hash and path are correct (LLM may hallucinate)
                plan.spec_hash = spec_hash
                plan.spec_path = spec_path
                plan.spec_name = spec_name
                if not plan.timestamp:
                    plan.timestamp = datetime.now(UTC).isoformat()
                logger.info(
                    "Planner: plan generated (attempt %d, confidence=%d, files=%d)",
                    attempt, plan.confidence, len(plan.file_layout),
                )
                return plan
            except (json.JSONDecodeError, Exception) as exc:
                error_msg = str(exc)
                logger.warning(
                    "Planner: attempt %d failed — %s",
                    attempt, error_msg[:200],
                )
                # Add retry prompt for the next attempt
                messages.append(Message(role=Role.ASSISTANT, content=raw))
                messages.append(
                    Message(
                        role=Role.USER,
                        content=RETRY_PROMPT_TEMPLATE.format(error=error_msg),
                    ),
                )

        msg = f"Plan generation failed after {self._max_retries} attempts"
        logger.error("Planner: %s", msg)
        raise ValueError(msg)

    @staticmethod
    def _clean_json(text: str) -> str:
        """Remove markdown code fences if present."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[len("```json"):].strip()
        elif text.startswith("```"):
            text = text[3:].strip()
        if text.endswith("```"):
            text = text[:-3].strip()
        return text
