# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Planner — LLM-driven implementation plan generation from specs.

Reads an approved spec, generates a structured PlanArtifact via LLM,
and validates the JSON output using reflection retry (max N attempts).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from specweaver.commons import json
from specweaver.infrastructure.llm.models import GenerationConfig, Message, Role
from specweaver.workflows.planning.models import PlanArtifact

if TYPE_CHECKING:
    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.models import ToolDispatcherProtocol
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an implementation planner for a Python project. Given a component \
specification, you produce a structured implementation plan as JSON.

Your output must be ONLY valid JSON matching the PlanArtifact schema. \
No markdown fences, no explanation."""

PLAN_GENERATION_INSTRUCTIONS = """\
Generate an implementation plan for the following specification.

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
- tasks (list): sequence_number (int), name, description, files, dependencies, expected_signatures (dict mapping file_path to list of MethodSignature: name, list of parameter strings, return_type)
- test_expectations (list): name, description, function_under_test, input_summary, expected_behavior, category ("happy"|"error"|"boundary")
- reasoning (str): your chain-of-thought
- confidence (int): 0-100

Return ONLY the JSON object."""


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
        config: GenerationConfig | None = None,
        max_retries: int = 3,
        tool_dispatcher: ToolDispatcherProtocol | None = None,
    ) -> None:
        self._llm = llm
        self._max_retries = max_retries
        self._tool_dispatcher = tool_dispatcher
        self._config = config or GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=0.3,
            max_output_tokens=4096,
        )

    async def generate_plan(
        self,
        spec_content: str,
        spec_path: str,
        spec_name: str,
        base_prompt: PromptBuilder,
        *,
        stitch_mode: str = "off",
        stitch_api_key: str = "",
    ) -> PlanArtifact:
        """Generate an implementation plan from spec content.

        Args:
            spec_content: The spec text.
            spec_path: Path to the spec file (stored in the plan).
            spec_name: Human-readable spec name.
            base_prompt: Base prompt builder initialized with context.
            stitch_mode: Optional stitch UI mockup mode.
            stitch_api_key: Optional stitch API key.

        Returns:
            A validated PlanArtifact.

        Raises:
            ValueError: If all retries fail to produce valid JSON.
        """
        spec_hash = hashlib.sha256(spec_content.encode()).hexdigest()

        # Format the instructions with the dynamic spec paths and hash
        formatted_instructions = PLAN_GENERATION_INSTRUCTIONS.format(
            spec_path=spec_path, spec_name=spec_name, spec_hash=spec_hash
        )

        # Base prompt already has instructions (unformatted), so we can just add our context
        # But wait, base prompt has the unformatted PLAN_GENERATION_INSTRUCTIONS!
        # We need to replace or we just pass the formatted ones here instead of the base prompt instructions.
        # Actually, if we pass empty instructions to _build_base_prompt, we can add them here.
        # Let's just assume base_prompt has metadata, constitution, standards. We add the rest.
        builder = base_prompt
        builder.add_context(formatted_instructions, "schema_requirements")
        builder.add_context(spec_content, label="Specification")

        user_prompt = builder.build()

        messages: list[Message] = [
            Message(role=Role.SYSTEM, content=_SYSTEM_PROMPT),
            Message(role=Role.USER, content=user_prompt),
        ]

        for attempt in range(1, self._max_retries + 1):
            logger.debug("Planner: attempt %d/%d", attempt, self._max_retries)

            # Tool loop runs to completion BEFORE retry loop
            if self._tool_dispatcher:
                config = self._config.model_copy(
                    update={"tools": self._tool_dispatcher.available_tools()},
                )
                response = await self._llm.generate_with_tools(
                    messages,
                    config,
                    self._tool_dispatcher,
                )
            else:
                response = await self._llm.generate(messages, self._config)
            raw = self._clean_json(response.text)

            try:
                data = json.loads(raw)
                plan = PlanArtifact.model_validate(data)

                # Check for UI mockups via Stitch if enabled
                if stitch_mode != "off":
                    from specweaver.workflows.planning.stitch import StitchClient
                    from specweaver.workflows.planning.ui_extractor import extract_ui_requirements

                    ui_reqs = extract_ui_requirements(spec_content)
                    if ui_reqs:
                        logger.info("Planner: UI requirements detected, requesting Stitch mockups")
                        stitch_client = StitchClient(api_key=stitch_api_key)
                        mockup_result = stitch_client.generate_mockup(ui_reqs.description)
                        plan.mockups = mockup_result.references

                # Ensure hash and path are correct (LLM may hallucinate)
                plan.spec_hash = spec_hash
                plan.spec_path = spec_path
                plan.spec_name = spec_name
                if not plan.timestamp:
                    plan.timestamp = datetime.now(UTC).isoformat()
                logger.info(
                    "Planner: plan generated (attempt %d, confidence=%d, files=%d)",
                    attempt,
                    plan.confidence,
                    len(plan.file_layout),
                )
                return plan
            except (json.JSONDecodeError, Exception) as exc:
                error_msg = str(exc)
                logger.warning(
                    "Planner: attempt %d failed — %s",
                    attempt,
                    error_msg[:200],
                )
                # Add retry prompt for the next attempt
                messages.append(Message(role=Role.ASSISTANT, content=raw))
                messages.append(
                    Message(
                        role=Role.USER,
                        content=(
                            f"Your previous response was not valid JSON. "
                            f"The error was:\n\n{error_msg}\n\n"
                            f"Please fix the output and return ONLY valid "
                            f"JSON matching the schema."
                        ),
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
            text = text.removeprefix("```json").strip()
        elif text.startswith("```"):
            text = text.removeprefix("```").strip()
        if text.endswith("```"):
            text = text.removesuffix("```").strip()
        return text
