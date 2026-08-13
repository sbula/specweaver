# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Spec drafter — interactive co-authoring with LLM + context providers.

Drives the 5-section component spec template through:
1. Context providers (HITL questions for each section)
2. LLM suggestions (proposes content based on user input)
3. Human approval (accept, modify, or reject)

Output: a complete _spec.md file in the target project's specs/ directory.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from jinja2 import Template

from specweaver.workflows.drafting._base import BaseDrafter, SectionDef

logger = logging.getLogger(__name__)


# The 5 sections of a component spec and their guiding questions
SPEC_SECTIONS: list[SectionDef] = [
    {
        "name": "Purpose",
        "heading": "## 1. Purpose",
        "question": (
            "What does this component do? Describe its single responsibility in one sentence."
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
            "What are the inputs, outputs, and data types? Include code examples if possible."
        ),
        "prompt": (
            "Based on the user's answer, write a Contract "
            "section with data models, interface definitions, "
            "and at least one concrete input -> output example "
            "in a Python code block."
        ),
        "inject_topology": True,
    },
    {
        "name": "Protocol",
        "heading": "## 3. Protocol",
        "question": ("What are the step-by-step rules for how this component processes its input?"),
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
            "What is NOT this component's responsibility? What concerns belong to other components?"
        ),
        "prompt": (
            "Based on the user's answer, write a Boundaries "
            "section as a table (Concern | Owned By) listing "
            "what is explicitly out of scope for this component."
        ),
        "inject_topology": True,
    },
]

# Instruction template for per-section LLM calls
_SECTION_INSTRUCTION_TEMPLATE = (
    "You are a technical specification writer. You are helping draft a "
    'component spec for "{name}".\n\n'
    "Section: {section_name}\n"
    "{section_prompt}\n\n"
    "Write ONLY the content for this section. Do not include the heading.\n"
    "Use markdown formatting. Be concrete and specific, not vague."
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


class Drafter(BaseDrafter):
    """Interactive spec drafter using LLM + context providers."""

    SECTIONS: ClassVar[list[SectionDef]] = SPEC_SECTIONS
    TEMPLATE: ClassVar[Template] = _SPEC_FILE_TEMPLATE
    FILENAME_SUFFIX: ClassVar[str] = "_spec.md"
    SECTION_INSTRUCTION: ClassVar[str] = _SECTION_INSTRUCTION_TEMPLATE
