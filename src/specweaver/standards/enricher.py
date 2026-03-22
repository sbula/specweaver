# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Async LLM Enricher for Standards."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from specweaver.llm.models import GenerationConfig, Message, Role

if TYPE_CHECKING:
    from specweaver.llm.adapters.base import LLMAdapter
    from specweaver.standards.analyzer import CategoryResult

logger = logging.getLogger(__name__)


class StandardComparison(BaseModel):
    """Pydantic model representing the LLM's structured comparison response."""
    industry_standard: str
    is_conflict: bool
    conflict_reason: str | None = None


class StandardsEnricher:
    """Enriches codebase standard findings using asynchronous LLM comparisons."""

    def __init__(self, llm_adapter: LLMAdapter):
        self.llm = llm_adapter

    async def enrich(
        self,
        results: list[CategoryResult],
        language: str,
        confidence_threshold: float = 0.9,
        force_compare: bool = False,
    ) -> None:
        """Asynchronously evaluate codebase patterns against industry standards."""
        tasks = []
        for result in results:
            if force_compare or result.confidence < confidence_threshold:
                tasks.append(self._compare_single(result, language))

        if not tasks:
            return

        await asyncio.gather(*tasks)

    async def _compare_single(self, result: CategoryResult, language: str) -> None:
        """Ask the LLM to compare a single category finding."""
        if not self.llm.available():
            logger.warning("LLM adapter unavailable, skipping enrichment for %s", result.category)
            return

        dominant_str = json.dumps(result.dominant)
        prompt = f"""\
You are an expert Software Engineer and Architect grading codebase conventions.
Language: {language}
Category: {result.category}
Dominant Pattern in codebase: {dominant_str}

Compare this dominant pattern against standard industry best practices for {language}.
Respond in pure JSON matching this schema:
{{
  "industry_standard": "Brief description of the industry standard",
  "is_conflict": boolean,
  "conflict_reason": "If is_conflict is true, explain why the codebase deviates. Otherwise null."
}}
"""
        messages = [
            Message(role=Role.SYSTEM, content="You output pure JSON matching the requested schema without markdown blocks."),
            Message(role=Role.USER, content=prompt),
        ]

        # In a real app we might use response_schema if supported, but here we enforce standard JSON.
        config = GenerationConfig(model="gemini-2.5-flash", temperature=0.1)

        try:
            response = await self.llm.generate(messages, config)
            # Clean up markdown if the LLM leaked some
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            comparison = StandardComparison.model_validate_json(text)

            if comparison.is_conflict and comparison.conflict_reason:
                result.conflicts.append(comparison.conflict_reason)

        except ValidationError as e:
            logger.debug("Failed to parse LLM response for %s: %s", result.category, e)
        except Exception as e:
            logger.debug("LLM generated error for %s: %s", result.category, e)
