# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""FeatureDrafter — interactive co-authoring for Feature Specs.

Drives the 5-section feature spec template (Intent, Blast Radius,
Change Map, Integration Seams, Sequence) through context providers
+ LLM suggestions + human approval.

Output: a *_feature_spec.md file in the target directory.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from jinja2 import Template

from specweaver.workflows.drafting._base import BaseDrafter, SectionDef

logger = logging.getLogger(__name__)


#: The feature sections have the same shape as any other; kept as a name so existing
#: imports of `FeatureSectionDef` keep resolving (`TECH-037`).
FeatureSectionDef = SectionDef


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
    {
        "name": "Risk Assessment (DAL)",
        "heading": "## Risk Assessment (DAL)",
        "question": (
            "What is the severity of failure for this feature? "
            "Please assess data sensitivity and operational criticality."
        ),
        "prompt": (
            "Based on the user's answer, write a Risk Assessment section for a "
            "Feature Spec. Propose a DAL using strict DO-178C logic: DAL_A "
            "(Catastrophic), DAL_B (Hazardous), DAL_C (Major), DAL_D (Minor), "
            "DAL_E (No Safety Effect). Ground your output securely in these categorizations."
        ),
        "inject_topology": True,
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
- [ ] Risk Assessment explicitly declares a DAL level
- [ ] `sw check --level=feature` passes
""")


class FeatureDrafter(BaseDrafter):
    """Interactive Feature Spec drafter using LLM + context providers."""

    SECTIONS: ClassVar[list[SectionDef]] = FEATURE_SECTIONS
    TEMPLATE: ClassVar[Template] = _FEATURE_SPEC_TEMPLATE
    FILENAME_SUFFIX: ClassVar[str] = "_feature_spec.md"
    SECTION_INSTRUCTION: ClassVar[str] = _SECTION_INSTRUCTION_TEMPLATE
