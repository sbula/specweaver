# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ScenarioGenerator — LLM-driven scenario generation from spec + contract.

Reads a spec and its API contract, generates structured YAML scenarios via LLM,
and validates output with Pydantic + reflection retry.

Follows the Planner pattern (prompt → LLM → parse → validate → retry).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from specweaver.workflows.scenarios.scenario_models import ScenarioSet

logger = logging.getLogger(__name__)



class ScenarioGenerator:
    """Generate structured YAML scenarios from spec + API contract via LLM.

    Args:
        llm: LLM adapter for scenario generation.
        config: Optional generation config overrides.
        max_retries: Max retries on invalid LLM output.
        tool_dispatcher: Optional tool dispatcher (reserved for future use).
    """

    def __init__(
        self,
        llm: Any,
        *,
        config: Any = None,
        max_retries: int = 3,
        tool_dispatcher: Any = None,
    ) -> None:
        self._llm = llm
        self._config = config
        self._max_retries = max_retries
        self._tool_dispatcher = tool_dispatcher

    async def generate_scenarios(
        self,
        spec_content: str,
        contract_content: str,
        req_ids: list[str],
        *,
        constitution: str | None = None,
        project_metadata: Any = None,
    ) -> ScenarioSet:
        """Generate scenarios from spec + contract via LLM.

        Args:
            spec_content: Full spec markdown content.
            contract_content: Generated Protocol class content.
            req_ids: Extracted requirement IDs from spec.
            constitution: Optional project constitution.
            project_metadata: Optional project metadata.

        Returns:
            ScenarioSet with validated scenario definitions.

        Raises:
            ValueError: If LLM output cannot be parsed after max_retries.
        """
        # Extract relevant sections from spec
        contract_section = self._extract_section(spec_content, "Contract") or ""
        scenarios_section = self._extract_section(spec_content, "Scenarios") or ""
        fr_section = self._extract_section(spec_content, "Functional Requirements") or ""
        nfr_section = self._extract_section(spec_content, "Non-Functional Requirements") or ""

        prompt = self._build_prompt(
            contract_section=contract_section,
            scenarios_section=scenarios_section,
            fr_section=fr_section,
            nfr_section=nfr_section,
            contract_content=contract_content,
            req_ids=req_ids,
            constitution=constitution,
        )

        last_error: str | None = None
        for attempt in range(1, self._max_retries + 1):
            logger.info(
                "ScenarioGenerator: attempt %d/%d",
                attempt,
                self._max_retries,
            )

            if last_error:
                retry_prompt = (
                    f"{prompt}\n\n"
                    f"Your previous output was invalid: {last_error}\n"
                    "Please fix the JSON and try again."
                )
            else:
                retry_prompt = prompt

            raw = await self._llm.generate(retry_prompt, config=self._config)
            cleaned = self._clean_json(raw)

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError as exc:
                last_error = f"Invalid JSON: {exc}"
                logger.warning("ScenarioGenerator: %s (attempt %d)", last_error, attempt)
                continue

            try:
                scenario_set = ScenarioSet.model_validate(data)
                logger.info(
                    "ScenarioGenerator: generated %d scenarios",
                    len(scenario_set.scenarios),
                )
                return scenario_set
            except Exception as exc:
                last_error = f"Pydantic validation failed: {exc}"
                logger.warning("ScenarioGenerator: %s (attempt %d)", last_error, attempt)
                continue

        msg = f"ScenarioGenerator: failed after {self._max_retries} retries. Last error: {last_error}"
        logger.error(msg)
        raise ValueError(msg)

    @staticmethod
    def _extract_req_ids(spec_content: str) -> list[str]:
        """Extract FR-X and NFR-X tags from spec text.

        Uses same regex as C09: r"\\b(?:N)?FR-\\d+\\b"

        Returns:
            Deduplicated list of requirement IDs.
        """
        matches = re.findall(r"\b(?:N)?FR-\d+\b", spec_content)
        # Deduplicate while preserving order
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            if m not in seen:
                seen.add(m)
                result.append(m)
        return result

    @staticmethod
    def _extract_section(spec_text: str, heading: str) -> str | None:
        """Extract a ## section from spec text by heading name.

        Handles both ``## Heading`` and ``## N. Heading`` formats.

        Returns:
            Content between the heading and the next ``##`` heading, or None.
        """
        pattern = re.compile(
            rf"^##\s+(?:\d+\.\s+)?{re.escape(heading)}\s*$",
            re.MULTILINE | re.IGNORECASE,
        )
        match = pattern.search(spec_text)
        if not match:
            return None
        start = match.end()
        next_header = re.search(r"^##\s+", spec_text[start:], re.MULTILINE)
        if next_header:
            return spec_text[start : start + next_header.start()]
        return spec_text[start:]

    @staticmethod
    def _clean_json(text: str) -> str:
        """Remove markdown code fences if present."""
        cleaned = text.strip()
        # Strip ```json or ``` fences
        cleaned = re.sub(r"^\s*```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?\s*```\s*$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def _build_prompt(
        *,
        contract_section: str,
        scenarios_section: str,
        fr_section: str,
        nfr_section: str,
        contract_content: str,
        req_ids: list[str],
        constitution: str | None = None,
    ) -> str:
        """Build the LLM prompt for scenario generation."""
        parts = [
            "Generate structured test scenarios for the following specification.",
            "Each scenario MUST reference a req_id from the list below.",
            "Generate ≥1 scenario per public method covering happy, error, and boundary paths.",
            "",
            "## Requirement IDs",
            ", ".join(req_ids) if req_ids else "(none found)",
            "",
        ]

        if fr_section:
            parts.extend(["## Functional Requirements", fr_section, ""])
        if nfr_section:
            parts.extend(["## Non-Functional Requirements", nfr_section, ""])
        if contract_section:
            parts.extend(["## Contract (from spec)", contract_section, ""])
        if scenarios_section:
            parts.extend(["## Scenario Hints (from spec)", scenarios_section, ""])
        if contract_content:
            parts.extend(["## API Contract (Protocol class)", contract_content, ""])
        if constitution:
            parts.extend(["## Project Constitution", constitution, ""])

        parts.extend([
            "",
            "Respond with a JSON object matching this schema:",
            '{"spec_path": "...", "contract_path": "...", "scenarios": [...], "reasoning": "..."}',
            "Each scenario: {name, description, function_under_test, req_id, category, "
            "preconditions, input_summary, inputs, expected_behavior, expected_output}",
        ])

        return "\n".join(parts)
