# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Spec drafter — interactive co-authoring with LLM + context providers.

Drives the 5-section component spec template through:
1. Context providers (HITL questions for each section)
2. LLM suggestions (proposes content based on user input)
3. Human approval (accept, modify, or reject)

Output: a complete _spec.md file in the target project's specs/ directory.
"""

from __future__ import annotations

from datetime import UTC
from typing import TYPE_CHECKING

from jinja2 import Template

from specweaver.llm.models import GenerationConfig, Message, Role

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.context.provider import ContextProvider
    from specweaver.llm.adapter import LLMAdapter

# The 5 sections of a component spec and their guiding questions
SPEC_SECTIONS: list[dict[str, str]] = [
    {
        "name": "Purpose",
        "heading": "## 1. Purpose",
        "question": (
            "What does this component do? Describe its "
            "single responsibility in one sentence."
        ),
        "prompt": (
            "Based on the user's answer, write a clear, "
            "focused one-paragraph Purpose section for a "
            "component spec. The purpose must describe "
            "ONE thing the component does."
        ),
    },
    {
        "name": "Contract",
        "heading": "## 2. Contract",
        "question": (
            "What are the inputs, outputs, and data types? "
            "Include code examples if possible."
        ),
        "prompt": (
            "Based on the user's answer, write a Contract "
            "section with data models, interface definitions, "
            "and at least one concrete input -> output example "
            "in a Python code block."
        ),
    },
    {
        "name": "Protocol",
        "heading": "## 3. Protocol",
        "question": (
            "What are the step-by-step rules for how this "
            "component processes its input?"
        ),
        "prompt": (
            "Based on the user's answer, write a Protocol "
            "section as a numbered list of processing steps. "
            "Each step should be concrete and actionable."
        ),
    },
    {
        "name": "Policy",
        "heading": "## 4. Policy",
        "question": (
            "What happens when things go wrong? What are "
            "the error cases, limits, and configurable "
            "parameters?"
        ),
        "prompt": (
            "Based on the user's answer, write a Policy "
            "section with an Error Handling table "
            "(Error Condition | Behavior) and a Limits "
            "table (Parameter | Default | Range)."
        ),
    },
    {
        "name": "Boundaries",
        "heading": "## 5. Boundaries",
        "question": (
            "What is NOT this component's responsibility? "
            "What concerns belong to other components?"
        ),
        "prompt": (
            "Based on the user's answer, write a Boundaries "
            "section as a table (Concern | Owned By) listing "
            "what is explicitly out of scope for this component."
        ),
    },
]

# Instruction template for per-section LLM calls
_SECTION_INSTRUCTION_TEMPLATE = (
    'You are a technical specification writer. You are helping draft a '
    'component spec for "{name}".\n\n'
    'Section: {section_name}\n'
    '{section_prompt}\n\n'
    'Write ONLY the content for this section. Do not include the heading.\n'
    'Use markdown formatting. Be concrete and specific, not vague.'
)

# Template for the final spec file
_SPEC_FILE_TEMPLATE = Template("""\
# {{ name }} — Component Spec

> **Status**: DRAFT
> **Date**: {{ date }}
> **Layer**: Component (L2)

---

{% for section in sections %}
{{ section.heading }}

{{ section.content }}

---

{% endfor %}
## Done Definition

- [ ] All public methods have unit tests
- [ ] Examples from Contract pass as test cases
- [ ] Error cases from Policy have test coverage
- [ ] Coverage >= 70%
- [ ] `sw check --level=component` passes
""")


class Drafter:
    """Interactive spec drafter using LLM + context providers."""

    def __init__(
        self,
        llm: LLMAdapter,
        context_provider: ContextProvider,
        config: GenerationConfig | None = None,
    ) -> None:
        self._llm = llm
        self._context = context_provider
        self._config = config or GenerationConfig(model="gemini-2.5-flash")

    async def draft(self, name: str, output_dir: Path) -> Path:
        """Draft a component spec interactively.

        Args:
            name: Component name (e.g., "greet_service").
            output_dir: Directory to write the spec file to (typically specs/).

        Returns:
            Path to the generated spec file.
        """
        from datetime import datetime

        sections: list[dict[str, str]] = []

        for section_def in SPEC_SECTIONS:
            # Ask the user for context
            user_input = await self._context.ask(
                section_def["question"],
                section=section_def["name"],
            )

            if not user_input:
                # User skipped — use a placeholder
                content = f"*TODO: Fill in {section_def['name']} section.*"
            else:
                # Generate content with LLM
                content = await self._generate_section(
                    name=name,
                    section_name=section_def["name"],
                    section_prompt=section_def["prompt"],
                    user_input=user_input,
                )

            sections.append(
                {
                    "heading": section_def["heading"],
                    "content": content,
                }
            )

        # Render the full spec
        date_str = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        spec_content = _SPEC_FILE_TEMPLATE.render(
            name=name.replace("_", " ").title(),
            date=date_str,
            sections=sections,
        )

        # Write to file
        output_dir.mkdir(parents=True, exist_ok=True)
        spec_path = output_dir / f"{name}_spec.md"
        spec_path.write_text(spec_content, encoding="utf-8")

        return spec_path

    async def _generate_section(
        self,
        name: str,
        section_name: str,
        section_prompt: str,
        user_input: str,
    ) -> str:
        """Generate content for a single spec section using the LLM."""
        from specweaver.llm.prompt_builder import PromptBuilder

        instructions = _SECTION_INSTRUCTION_TEMPLATE.format(
            name=name,
            section_name=section_name,
            section_prompt=section_prompt,
        )

        prompt = (
            PromptBuilder()
            .add_instructions(instructions)
            .add_context(user_input, "user_context")
            .build()
        )

        messages = [
            Message(role=Role.USER, content=prompt),
        ]

        response = await self._llm.generate(messages, self._config)
        return response.text.strip()
