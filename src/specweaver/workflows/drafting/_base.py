# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The drafting loop both drafters run, and the four things a drafter changes about it.

`TECH-037`. `Drafter` and `FeatureDrafter` had **byte-identical** `__init__` (17 lines) and
`_generate_section` (35 lines), and a `draft` that differed in exactly four places: which sections
to walk, which Jinja template to render, what to call the output file, and the wording of the
instruction handed to the LLM. All four are data.

So a third drafter is four class attributes, not a third copy of ninety lines.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, TypedDict

from specweaver.infrastructure.llm.models import GenerationConfig, Message, ProjectMetadata, Role

if TYPE_CHECKING:
    from pathlib import Path

    from jinja2 import Template

    from specweaver.assurance.graph.topology import TopologyContext
    from specweaver.infrastructure.llm.adapters.base import LLMAdapter
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder
    from specweaver.workspace.context.provider import ContextProvider

logger = logging.getLogger(__name__)


class SectionDef(TypedDict, total=False):
    """A single spec section definition."""

    name: str
    heading: str
    question: str
    prompt: str
    inject_topology: bool


class BaseDrafter:
    """Interactive spec drafting: ask, generate, assemble, write.

    Subclasses supply only the four class attributes below. The loop itself — including the
    skipped-section placeholder and the per-section topology decision — is shared.
    """

    #: The sections to walk, in order. Empty on the base on purpose: a subclass that forgets its
    #: own data must draft nothing rather than silently inherit another drafter's.
    SECTIONS: ClassVar[list[SectionDef]] = []

    #: Jinja template for the assembled file.
    TEMPLATE: ClassVar[Template]

    #: Appended to the name to form the output filename. Load-bearing rather than cosmetic:
    #: `feature_name_from_spec` strips `_feature_spec` to recover a feature name, and
    #: `DraftSpecHandler`'s exists-skip keys on the component form.
    FILENAME_SUFFIX: ClassVar[str] = "_spec.md"

    #: `str.format` template for the per-section LLM instruction, taking `name`, `section_name`
    #: and `section_prompt`. The feature drafter adds a clause forbidding file paths.
    SECTION_INSTRUCTION: ClassVar[str] = ""

    def __init__(
        self,
        base_prompt: PromptBuilder,
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
        self._base_prompt = base_prompt

    async def draft(
        self,
        name: str,
        output_dir: Path,
        *,
        topology_contexts: list[TopologyContext] | None = None,
        project_metadata: ProjectMetadata | None = None,
    ) -> Path:
        """Draft a spec interactively, one section at a time.

        Args:
            name: The subject's name (e.g. "greet_service", "sell_shares").
            output_dir: Directory to write the spec file to.
            topology_contexts: Optional topology context from the project graph.
            project_metadata: Optional project metadata for the prompt.

        Returns:
            Path to the generated spec file.
        """
        logger.debug(
            "%s.draft: starting for name=%s, output=%s", type(self).__name__, name, output_dir
        )

        sections: list[dict[str, str]] = []
        for section_def in self.SECTIONS:
            content = await self._section_content(
                section_def,
                name,
                topology_contexts=topology_contexts,
                project_metadata=project_metadata,
            )
            sections.append({"heading": section_def["heading"], "content": content})

        spec_content = self.TEMPLATE.render(
            name=name.replace("_", " ").title(),
            date=datetime.now(tz=UTC).strftime("%Y-%m-%d"),
            sections=sections,
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        spec_path = output_dir / f"{name}{self.FILENAME_SUFFIX}"
        spec_path.write_text(spec_content, encoding="utf-8")
        return spec_path

    async def _section_content(
        self,
        section_def: SectionDef,
        name: str,
        *,
        topology_contexts: list[TopologyContext] | None,
        project_metadata: ProjectMetadata | None,
    ) -> str:
        """One section's body: what the user said, turned into prose by the LLM.

        A skipped section becomes a TODO placeholder rather than an empty heading, so the spec
        still validates as structurally complete and the gap is visible to the author.
        """
        user_input = await self._context.ask(section_def["question"], section=section_def["name"])
        if not user_input:
            return f"*TODO: Fill in {section_def['name']} section.*"

        return await self._generate_section(
            name=name,
            section_name=section_def["name"],
            section_prompt=section_def["prompt"],
            user_input=user_input,
            # Only the sections that ask for it pay the topology token cost.
            topology_contexts=topology_contexts if section_def.get("inject_topology") else None,
            project_metadata=project_metadata,
        )

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
        builder = self._base_prompt.clone()
        builder.add_instructions(
            self.SECTION_INSTRUCTION.format(
                name=name,
                section_name=section_name,
                section_prompt=section_prompt,
            )
        )

        if project_metadata:
            builder.add_project_metadata(project_metadata)

        builder.add_context(user_input, "user_context")

        if topology_contexts:
            builder.add_topology(topology_contexts)

        messages = [Message(role=Role.USER, content=builder.build())]
        response = await self._llm.generate(messages, self._config)
        return str(response.text).strip()
