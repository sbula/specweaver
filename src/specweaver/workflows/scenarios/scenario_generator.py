# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ScenarioGenerator — LLM-driven scenario generation from spec + contract.

Reads a spec and its API contract, generates structured YAML scenarios via LLM,
and validates output with Pydantic + reflection retry.

Follows the Planner pattern (prompt → LLM → parse → validate → retry).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from specweaver.commons import json
from specweaver.workflows.scenarios.scenario_models import ScenarioSet

logger = logging.getLogger(__name__)


class ScenarioGenerator:
    """Generate structured YAML scenarios from spec + API contract via LLM.

    Args:
        llm: LLM adapter for scenario generation.
        config: Optional generation config overrides.
        max_retries: Max retries on invalid LLM output.
        tool_dispatcher: Optional read-only file tools over the spec and the contracts.
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
        feedback: str | None = None,
        methods: list[str] | None = None,
        constructors: dict[str, list[str] | None] | None = None,
        earlier: str | None = None,
    ) -> ScenarioSet:
        """Generate scenarios from spec + contract via LLM.

        Args:
            spec_content: Full spec markdown content.
            contract_content: Generated Protocol class content.
            req_ids: Extracted requirement IDs from spec.
            constitution: Optional project constitution.
            project_metadata: Optional project metadata.
            feedback: Optional prior-verdict findings — the arbiter's behavioral
                delta on a regeneration loop. None ⇒ the prompt is identical to a
                first-pass generation.
            methods: The contract's methods, `function` or `Class.method`; None skips the
                method checks.
            constructors: Each class's constructor parameters, None for one taking any key.
            earlier: The set stored for this spec before, if any.

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
            feedback=feedback,
            methods=methods,
            earlier=earlier,
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

            raw = await self._ask(retry_prompt)
            # Real adapters return LLMResponse objects (as in reviewer.py:
            # `response.text`); string returns are the unit-mock convention only.
            raw_text = raw.text if hasattr(raw, "text") else raw
            scenario_set, last_error = self._parse(raw_text)
            if scenario_set is not None:
                last_error = mismatch(scenario_set, req_ids, methods, constructors)
            if last_error or scenario_set is None:
                logger.warning("ScenarioGenerator: %s (attempt %d)", last_error, attempt)
                continue
            logger.info("ScenarioGenerator: generated %d scenarios", len(scenario_set.scenarios))
            return scenario_set

        msg = (
            f"ScenarioGenerator: failed after {self._max_retries} retries. Last error: {last_error}"
        )
        logger.error(msg)
        raise ValueError(msg)

    async def _ask(self, prompt: str) -> Any:
        """One answer; with tools, the model may read the specs and contracts first."""
        if self._tool_dispatcher is None or self._config is None:
            return await self._llm.generate(prompt, config=self._config)
        from specweaver.infrastructure.llm.models import Message, Role

        config = self._config.model_copy(update={"tools": self._tool_dispatcher.available_tools()})
        messages = [Message(role=Role.USER, content=prompt)]
        return await self._llm.generate_with_tools(messages, config, self._tool_dispatcher)

    @classmethod
    def _parse(cls, raw_text: str) -> tuple[ScenarioSet | None, str | None]:
        """The scenario set in one answer, or why the answer is not one."""
        try:
            data = json.loads(cls._clean_json(raw_text))
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON: {exc}"
        try:
            return ScenarioSet.model_validate(data), None
        except Exception as exc:
            return None, f"Pydantic validation failed: {exc}"

    @staticmethod
    def _extract_req_ids(spec_content: str) -> list[str]:
        """Extract FR-X and NFR-X tags from spec text.

        A lettered id such as `FR-5a` is its own requirement.

        Returns:
            Deduplicated list of requirement IDs.
        """
        matches = re.findall(r"\b(?:N)?FR-\d+[a-z]?\b", spec_content)
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
        feedback: str | None = None,
        methods: list[str] | None = None,
        earlier: str | None = None,
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
        if methods is not None:
            parts.extend(
                [
                    "## Contract Methods",
                    "Name each scenario's function_under_test exactly as one of these, and call "
                    "every one. For a Class.method, give the constructor's values in "
                    "constructor_inputs.",
                    ", ".join(methods) or "(none)",
                    "",
                ]
            )
        if earlier:
            parts.extend(["## Your Earlier Scenarios For This Spec", earlier, ""])
        if constitution:
            parts.extend(["## Project Constitution", constitution, ""])
        if feedback:
            # The arbiter's spec-clause-anchored behavioral delta
            # from the previous verification round — placed before the schema
            # instructions so the fix intent frames the regeneration.
            parts.extend(
                [
                    "## Prior Verdict Feedback (your previous scenarios were judged incorrect — fix these)",
                    feedback,
                    "",
                ]
            )

        parts.extend(
            [
                "",
                "If the spec or the contract has a problem — a contradiction, a gap, an unclear "
                "rule — name it in problems. Never change the contract.",
                "Respond with a JSON object matching this schema:",
                '{"spec_path": "...", "contract_path": "...", "scenarios": [...], '
                '"reasoning": "...", "problems": ["..."]}',
                "Each scenario: {name, description, function_under_test, req_id, category, "
                "preconditions, input_summary, inputs, constructor_inputs, expected_behavior, "
                "expected_output}",
            ]
        )

        return "\n".join(parts)


def mismatch(
    scenario_set: ScenarioSet,
    req_ids: list[str],
    methods: list[str] | None,
    constructors: dict[str, list[str] | None] | None,
) -> str | None:
    """Why a scenario set does not match the spec and the contract; None when it does."""
    scenarios = scenario_set.scenarios
    if not scenarios:
        return "the answer has no scenario"
    unknown_ids = sorted({s.req_id for s in scenarios} - set(req_ids))
    if unknown_ids:
        return f"req_id {', '.join(unknown_ids)} is not in the spec; use one of {req_ids}"
    if methods is None:
        return None
    return _method_mismatch(scenarios, methods, constructors or {})


def _method_mismatch(
    scenarios: list[Any], methods: list[str], constructors: dict[str, list[str] | None]
) -> str | None:
    called = [s.function_under_test for s in scenarios]
    unknown = sorted(set(called) - set(methods))
    if unknown:
        return f"{', '.join(unknown)} is not a contract method; use one of {methods}"
    uncalled = [m for m in methods if m not in called]
    if uncalled:
        return f"no scenario calls {', '.join(uncalled)}"
    for s in scenarios:
        problem = _constructor_mismatch(s.function_under_test, s.constructor_inputs, constructors)
        if problem:
            return problem
    return None


def _constructor_mismatch(
    method: str, values: dict[str, Any], constructors: dict[str, list[str] | None]
) -> str | None:
    if "." not in method:
        return f"{method} is a function; it takes no constructor_inputs" if values else None
    owner = method.split(".")[0]
    allowed = constructors.get(owner, [])
    unknown = sorted(set(values) - set(allowed)) if allowed is not None else []
    return f"{owner}'s constructor has no {', '.join(unknown)}" if unknown else None
