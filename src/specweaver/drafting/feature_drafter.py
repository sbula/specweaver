# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""FeatureDrafter — interactive co-authoring for Feature Specs.

Drives the 5-section feature spec template (Intent, Blast Radius,
Change Map, Integration Seams, Sequence) through context providers
+ LLM suggestions + human approval.

Output: a *_feature_spec.md file in the target directory.
"""

from __future__ import annotations

import logging
from datetime import UTC
from typing import TYPE_CHECKING, TypedDict

from jinja2 import Template

from specweaver.llm.models import GenerationConfig, Message, ProjectMetadata, Role

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.context.provider import ContextProvider
    from specweaver.graph.topology import TopologyContext
    from specweaver.llm.adapters.base import LLMAdapter

logger = logging.getLogger(__name__)


class FeatureSectionDef(TypedDict, total=False):
    """A single feature spec section definition."""

    name: str
    heading: str
    question: str
    prompt: str
    inject_topology: bool


# The 5 sections of a Feature Spec and their guiding questions
FEATURE_SECTIONS: list[FeatureSectionDef] = [
    {
        "name": "Intent",
        "heading": "## Intent",
        "question": (
            "What is the business goal of this feature? "
            "Describe in one or two sentences what value it delivers."
        ),
        "prompt": (
            "Based on the user's answer, write a clear, focused "
            "Intent section for a Feature Spec. The intent must "
            "describe the business value in 1-2 sentences. "
            "Avoid implementation details."
        ),
    },
    {
        "name": "Blast Radius",
        "heading": "## Blast Radius",
        "question": (
            "Which services, modules, or subsystems are affected "
            "by this feature? List all areas of impact."
        ),
        "prompt": (
            "Based on the user's answer, write a Blast Radius "
            "section listing all affected services/modules as a "
            "bullet list. For each, briefly note the nature of "
            "the impact (new, modified, or removed behavior)."
        ),
        "inject_topology": True,
    },
    {
        "name": "Change Map",
        "heading": "## Change Map",
        "question": (
            "For each affected area, what specific changes are "
            "needed? Describe whether each is a new interface, "
            "schema change, behavior change, or config change."
        ),
        "prompt": (
            "Based on the user's answer, write a Change Map "
            "section as a table with columns: Component | "
            "Change Nature | Description. Use concrete terms."
        ),
        "inject_topology": True,
    },
    {
        "name": "Integration Seams",
        "heading": "## Integration Seams",
        "question": (
            "How do the affected components communicate? "
            "What contracts, events, or APIs connect them?"
        ),
        "prompt": (
            "Based on the user's answer, write an Integration "
            "Seams section listing each connection between "
            "components as: Between | Contract | Format "
            "(shared type, event, API call, etc.)."
        ),
        "inject_topology": True,
    },
    {
        "name": "Sequence",
        "heading": "## Sequence",
        "question": (
            "In what order should the changes be implemented? "
            "Which must be built first due to dependencies?"
        ),
        "prompt": (
            "Based on the user's answer, write a Sequence "
            "section as a numbered build order. Each step should "
            "name the component and briefly note why it must come "
            "at this position (e.g., 'dependency of step 3')."
        ),
    },
]

# Instruction template for per-section LLM calls
_SECTION_INSTRUCTION_TEMPLATE = (
    "You are a technical specification writer. You are helping draft a "
    'Feature Spec for "{name}".\n\n'
    "Section: {section_name}\n"
    "{section_prompt}\n\n"
    "Write ONLY the content for this section. Do not include the heading.\n"
    "Use markdown formatting. Be concrete and specific, not vague.\n"
    "Do NOT reference file paths, class names, or import paths — "
    "use service/module names only."
)

# Template for the final spec file
_FEATURE_SPEC_TEMPLATE = Template("""\
# {{ name }} — Feature Spec

> **Status**: DRAFT
> **Date**: {{ date }}
> **Layer**: Feature (L1)

---

{% for section in sections %}
{{ section.heading }}

{{ section.content }}

---

{% endfor %}
## Done Definition

- [ ] Intent describes a single business outcome
- [ ] Blast Radius lists all affected services/modules
- [ ] Change Map has at least one entry per Blast Radius item
- [ ] Integration Seams defines contracts for cross-module communication
- [ ] Sequence is ordered by dependency
- [ ] `sw check --level=feature` passes
""")


class FeatureDrafter:
    """Interactive Feature Spec drafter using LLM + context providers."""

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
            temperature=0.7,
            max_output_tokens=4096,
        )

    async def draft(
        self,
        name: str,
        output_dir: Path,
        *,
        topology_contexts: list[TopologyContext] | None = None,
        project_metadata: ProjectMetadata | None = None,
    ) -> Path:
        """Draft a Feature Spec interactively.

        Args:
            name: Feature name (e.g., "sell_shares").
            output_dir: Directory to write the spec file to.
            topology_contexts: Optional topology context from the project graph.

        Returns:
            Path to the generated spec file.
        """
        from datetime import datetime

        sections: list[dict[str, str]] = []
        logger.debug("FeatureDrafter.draft: starting for name=%s, output=%s", name, output_dir)

        for section_def in FEATURE_SECTIONS:
            # Ask the user for context
            user_input = await self._context.ask(
                section_def["question"],
                section=section_def["name"],
            )

            if not user_input:
                # User skipped — use a placeholder
                content = f"*TODO: Fill in {section_def['name']} section.*"
            else:
                # Decide whether to inject topology for this section
                section_topology = topology_contexts if section_def.get("inject_topology") else None
                # Generate content with LLM
                content = await self._generate_section(
                    name=name,
                    section_name=section_def["name"],
                    section_prompt=section_def["prompt"],
                    user_input=user_input,
                    topology_contexts=section_topology,
                    project_metadata=project_metadata,
                )

            sections.append(
                {
                    "heading": section_def["heading"],
                    "content": content,
                }
            )

        # Render the full spec
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        spec_content = _FEATURE_SPEC_TEMPLATE.render(
            name=name.replace("_", " ").title(),
            date=date_str,
            sections=sections,
        )

        # Write to file
        output_dir.mkdir(parents=True, exist_ok=True)
        spec_path = output_dir / f"{name}_feature_spec.md"
        spec_path.write_text(spec_content, encoding="utf-8")

        return spec_path

    async def _generate_section(
        self,
        name: str,
        section_name: str,
        section_prompt: str,
        user_input: str,
        *,
        topology_contexts: list[TopologyContext] | None = None,
        project_metadata: ProjectMetadata | None = None,
    ) -> str:
        """Generate content for a single spec section using the LLM."""
        from specweaver.llm.prompt_builder import PromptBuilder

        instructions = _SECTION_INSTRUCTION_TEMPLATE.format(
            name=name,
            section_name=section_name,
            section_prompt=section_prompt,
        )

        builder = (
            PromptBuilder()
            .add_instructions(instructions)
            .add_project_metadata(project_metadata)
            .add_context(user_input, "user_context")
        )
        if topology_contexts:
            builder.add_topology(topology_contexts)
        prompt = builder.build()

        messages = [
            Message(role=Role.USER, content=prompt),
        ]

        response = await self._llm.generate(messages, self._config)
        return response.text.strip()
