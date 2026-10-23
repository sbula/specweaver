# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Context Assembler — fetches background dependency contexts and condenses them lazily.

This utility runs transparently within `flow` handlers to bypass text reading
of massive background files, explicitly routing `CodeStructureAtom.run(intent="skeletonize")`
over the files to ensure token limits remain fully stable during large system integrations.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from specweaver.sandbox.code_structure.core.atom import CodeStructureAtom

if TYPE_CHECKING:
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


def evaluate_and_fetch_skeleton_context(
    context: RunContext,
    target_files: list[str] | list[Path],
) -> dict[str, str]:
    """Extract AST Skeletons for a list of background contextual files.

    Used by downstream Generation/Review PromptBuilders to inject pre-condensed boundaries
    without triggering fallback C-bindings from inside the adapter.

    Args:
        context: The active RunContext providing the parser registry and project configuration.
        target_files: List of file paths (absolute or relative to the project) to skeletonize.

    Returns:
        Dictionary mapping absolute file path strings to their condensed string payloads.
    """
    skeleton_files: dict[str, str] = {}
    if not target_files:
        return skeleton_files

    from specweaver.core.config.archetype_resolver import ArchetypeResolver

    # Each file is skeletonized under its own nearest `context.yaml`'s archetype; one atom per
    # archetype, with the run's parser mappings.
    resolver = ArchetypeResolver(context.project_path)
    atoms: dict[str, CodeStructureAtom] = {}

    def atom_for(path: Path) -> CodeStructureAtom:
        archetype = resolver.resolve(path) or "generic"
        if archetype not in atoms:
            atoms[archetype] = CodeStructureAtom(
                cwd=context.project_path,
                active_archetype=archetype,
                parsers=context.analysis.parsers,
            )
        return atoms[archetype]

    logger.debug(
        "ContextAssembler: Resolving %d background files for skeletonization...",
        len(target_files),
    )

    for file_path in target_files:
        path_str = str(file_path)
        try:
            absolute = Path(file_path)
            if not absolute.is_absolute():
                absolute = context.project_path / absolute
            res = atom_for(absolute).run({"intent": "skeletonize", "path": path_str})
            # `CodeStructureAtom._handle_structure` exports the payload under "structure"; this
            # read "skeleton", the condition never holds and the assembler returns {} for every
            # caller, so generation and review prompts carry no skeleton context. A containment
            # mutant survives that, because the result is discarded before containment can matter.
            if res.status.value == "SUCCESS" and res.exports and "structure" in res.exports:
                skeleton_files[path_str] = res.exports["structure"]
            else:
                logger.debug(
                    "ContextAssembler: Could not skeletonize %s, skipping... reason: %s",
                    path_str,
                    res.message,
                )
        except Exception as exc:
            logger.warning(
                "ContextAssembler: Exception extracting skeleton for %s — %s", path_str, exc
            )

    return skeleton_files
