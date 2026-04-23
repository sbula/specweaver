# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Context Assembler — fetches background dependency contexts and condenses them lazily.

This utility runs transparently within `flow` handlers to bypass text reading
of massive background files, explicitly routing `CodeStructureAtom.run(intent="skeletonize")`
over the files to ensure token limits remain fully stable during large system integrations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.core.loom.atoms.code_structure.atom import CodeStructureAtom

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.handlers.base import RunContext

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

    # Try to grab the resolved archetype from context if available, otherwise just use generic
    active_archetype = "generic"
    if getattr(context, "topology", None) and hasattr(context.topology, "archetype"):
        active_archetype = context.topology.archetype

    # Instantiate the CodeStructure atom statically with injected parser mappings
    # ensuring we adhere to the architectural dependency boundary.
    atom = CodeStructureAtom(
        cwd=context.project_path,
        active_archetype=active_archetype,
        parsers=context.parsers,
    )

    logger.debug(
        "ContextAssembler: Resolving %d background files for skeletonization...",
        len(target_files),
    )

    for file_path in target_files:
        path_str = str(file_path)
        try:
            res = atom.run({"intent": "skeletonize", "path": path_str})
            if res.status.value == "SUCCESS" and res.exports and "skeleton" in res.exports:
                skeleton_files[path_str] = res.exports["skeleton"]
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
