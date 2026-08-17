# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Assembling the prompt every handler starts from.

`StepHandler` belongs in a `base`; sixty-seven lines of prompt assembly — instructions, project
metadata, rules, memory — do not.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.run_context import RunContext
    from specweaver.infrastructure.llm.prompt.profiles import RenderProfile
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


async def _build_base_prompt(
    context: RunContext,
    instructions: str,
    *,
    profile: RenderProfile | None = None,
    skeleton_files: dict[str, str] | None = None,
) -> PromptBuilder:
    """Build a PromptBuilder with base context (instructions, metadata, rules, memory).

    Args:
        context: The RunContext for this pipeline step.
        instructions: Module-specific instruction text.
        profile: The RenderProfile to use for rendering slots. Defaults to FULL.
        skeleton_files: Optional skeleton files for PromptBuilder constructor.

    Returns:
        A partially-built PromptBuilder ready for domain-specific additions.

    The memory hydration is fail-safe: any exception during hydration (db=None,
    DB failure, Pydantic error) is caught and logged at WARNING. The returned
    PromptBuilder simply lacks the agent_memory block.
    """
    from specweaver.core.flow.handlers._profiles import FULL
    from specweaver.infrastructure.llm._prompt_profiles import PromptSlot
    from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

    if profile is None:
        profile = FULL

    builder = PromptBuilder(profile=profile, skeleton_files=skeleton_files)
    builder.add_instructions(instructions)
    builder.add_project_metadata(context.project_metadata)

    if context.guidance.constitution:
        builder.add_constitution(context.guidance.constitution)
    if context.guidance.standards:
        builder.add_standards(context.guidance.standards)

    # Memory Hydration — fail-safe
    if (
        PromptSlot.AGENT_MEMORY in profile.active_slots
        and context.db is not None
        and context.project_path is not None
    ):
        try:
            from specweaver.workspace.memory.hydrator import MemoryHydrator

            async with context.db.async_session_scope() as session:
                hydrator = MemoryHydrator(session, context.project_path.name)
                result = await hydrator.hydrate()
                if result.task_count > 0:
                    block = result.format_prompt_block()
                    builder.add_context(
                        block, "agent_memory", priority=2, slot=PromptSlot.AGENT_MEMORY
                    )
                    logger.info(
                        "Hydration: %d tasks, %d tokens",
                        result.task_count,
                        result.token_estimate,
                    )
        except Exception:
            logger.warning(
                "Memory hydration failed — continuing without agent_memory",
                exc_info=True,
            )

    return builder
