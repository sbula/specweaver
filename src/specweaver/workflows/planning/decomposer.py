# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""FeatureDecomposer — automated feature decomposition using LLM structural output.

This module is responsible for interpreting a Feature Spec and generating
a `DecompositionPlan` which outlines the necessary component-level changes,
integration seams, and build sequence.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.models import GenerationConfig, Message, ProjectMetadata, Role
from specweaver.workflows.planning.decomposition import DecompositionPlan

if TYPE_CHECKING:
    from specweaver.assurance.graph.topology import TopologyContext
    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.workspace.context.provider import ContextProvider

logger = logging.getLogger(__name__)

_DECOMPOSE_INSTRUCTION_TEMPLATE = """\
You are an expert system architect analyzing a new feature specification.
Your task is to decompose the provided Feature Spec into discrete component-level tasks.

You must reply with a valid JSON document matching the DecompositionPlan structure perfectly.
No markdown wrappers, no conversational text.

Analyze the intent, blast radius, and change map. For each affected component,
specify the change nature, dependencies, and propose a DO-178C DAL level (DAL_A to DAL_E).
Assess the coverage (fraction of blast radius items covered) and include it as `coverage_score` (0.0 to 1.0).

For EVERY component, you MUST strictly map it to the physical architecture using the provided TopologyContexts.
1. Populate `target_modules` with the exact namespace(s) from the TopologyContext list.
2. Populate `dependencies` logically (e.g. if Component B reads data written by Component A, B depends on A).

Feature Name: {feature_name}
Feature Spec Content:
{spec_content}
"""


class FeatureDecomposer:
    """Automated feature decomposer generating structured DecompositionPlans."""

    def __init__(
        self,
        llm: LLMAdapter,
        context_provider: ContextProvider,
        config: GenerationConfig | None = None,
    ) -> None:
        self._llm = llm
        self._context = context_provider
        self._config = config or GenerationConfig(
            model="gemini-3-flash-preview",
            temperature=0.2,  # Low temperature for structured output
            max_output_tokens=4096,
        )

    async def decompose(
        self,
        feature_name: str,
        spec_content: str,
        *,
        topology_contexts: list[TopologyContext] | None = None,
        project_metadata: ProjectMetadata | None = None,
    ) -> DecompositionPlan:
        """Decompose a feature spec into a structured plan.

        Args:
            feature_name: Name of the feature.
            spec_content: The full markdown content of the feature spec.
            topology_contexts: Optional graph contexts for blast radius alignment.
            project_metadata: Optional project metadata.

        Returns:
            The parsed DecompositionPlan.
        """
        from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

        instructions = _DECOMPOSE_INSTRUCTION_TEMPLATE.format(
            feature_name=feature_name,
            spec_content=spec_content,
        )

        builder = (
            PromptBuilder().add_instructions(instructions).add_project_metadata(project_metadata)
        )

        if topology_contexts:
            builder.add_topology(topology_contexts)

        prompt = builder.build()

        messages = [
            Message(role=Role.USER, content=prompt),
        ]

        # Force structured JSON output config
        cfg = self._config.model_copy()

        try:
            logger.debug(
                "FeatureDecomposer.decompose: executing LLM generation for %s", feature_name
            )
            response = await self._llm.generate(messages, cfg)
        except Exception as e:
            logger.critical(
                "Generator failed: Provider error for '%s'. Details: %s", feature_name, str(e)
            )
            raise

        raw_text = response.text.strip()

        # Clean up markdown code blocks if the LLM hallucinated them despite prompt
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        raw_text = raw_text.strip()

        # Parse JSON and validate against model
        try:
            return DecompositionPlan.model_validate_json(raw_text)
        except Exception as e:
            logger.error(
                "LLM failed to output valid schema. Parse error: %s. Raw payload size: %s",
                str(e),
                len(raw_text),
            )
            raise ValueError(
                f"LLM failed to provide a structurally valid DecompositionPlan: {e}"
            ) from e
