# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prompt rendering — XML-tagged output from content blocks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Callable

    from specweaver.infrastructure.llm._prompt_profiles import PromptSlot
    from specweaver.infrastructure.llm.prompt_builder import _ContentBlock


def render_files(blocks: list[_ContentBlock]) -> str | None:
    """Render ``<file_contents>`` XML from file blocks."""
    files = [b for b in blocks if b.kind == "file"]
    if not files:
        return None
    file_parts: list[str] = []
    for f in files:
        attrs = f'path="{f.label}" language="{f.language}"'
        if f.role:
            attrs += f' role="{f.role}"'
        marker = "\n[truncated]" if f.truncated else ""
        file_parts.append(
            f"<file {attrs}>\n{f.text}{marker}\n</file>",
        )
    inner = "\n".join(file_parts)
    return f"<file_contents>\n{inner}\n</file_contents>"


def _render_tagged_blocks(
    blocks: list[_ContentBlock],
    kind: str,
    tag: str,
) -> str | None:
    """Render blocks of a given kind into a single XML-tagged section."""
    items = [b for b in blocks if b.kind == kind]
    if not items:
        return None
    text = "\n\n".join(b.text for b in items)
    marker = "\n[truncated]" if any(b.truncated for b in items) else ""
    return f"<{tag}>\n{text}{marker}\n</{tag}>"


def _render_mentioned(blocks: list[_ContentBlock]) -> str | None:
    """Render auto-detected mentioned files into XML."""
    mentioned = [b for b in blocks if b.kind == "mentioned"]
    if not mentioned:
        return None
    mention_parts: list[str] = []
    for m in mentioned:
        attrs = f'path="{m.label}" language="{m.language}"'
        if m.role:
            attrs += f' role="{m.role}"'
        marker = "\n[truncated]" if m.truncated else ""
        mention_parts.append(
            f"<file {attrs}>\n{m.text}{marker}\n</file>",
        )
    inner = "\n".join(mention_parts)
    return f"<mentioned_files>\n{inner}\n</mentioned_files>"


def _render_topology(blocks: list[_ContentBlock]) -> str | None:
    """Render topology blocks into XML."""
    topology = [b for b in blocks if b.kind == "topology"]
    if not topology:
        return None
    parts: list[str] = []
    for topo in topology:
        marker = "\n[truncated]" if topo.truncated else ""
        parts.append(
            f"<topology>\n{topo.text}{marker}\n</topology>",
        )
    return "\n\n".join(parts)


def _render_contexts(blocks: list[_ContentBlock]) -> str | None:
    """Render context blocks into XML."""
    contexts = [b for b in blocks if b.kind == "context"]
    if not contexts:
        return None
    parts: list[str] = []
    for ctx in contexts:
        marker = "\n[truncated]" if ctx.truncated else ""
        parts.append(
            f'<context label="{ctx.label}">\n{ctx.text}{marker}\n</context>',
        )
    return "\n\n".join(parts)


_SLOT_RENDERERS: dict[str, Callable[[list[_ContentBlock]], str | None]] = {
    "topology": _render_topology,
    "file": render_files,
    "mentioned": _render_mentioned,
    "context": _render_contexts,
}


def render_blocks(
    blocks: list[_ContentBlock],
    order: tuple[PromptSlot, ...] | None = None,
) -> str:
    """Render blocks into XML-tagged prompt text."""
    logger.debug("Rendering %d prompt blocks", len(blocks))
    parts: list[str] = []

    if order is None:
        ordered_tags = [
            "instructions",
            "dictator-overrides",
            "project_metadata",
            "constitution",
            "standards",
            "plan",
            "topology",
            "file",
            "mentioned",
            "context",
            "reminder",
            "agent_memory",
        ]
        for tag in ordered_tags:
            if tag in _SLOT_RENDERERS:
                rendered = _SLOT_RENDERERS[tag](blocks)
            else:
                rendered = _render_tagged_blocks(blocks, tag, tag)
            if rendered:
                parts.append(rendered)
    else:
        for slot in order:
            if slot.value in _SLOT_RENDERERS:
                rendered = _SLOT_RENDERERS[slot.value](blocks)
            else:
                rendered = _render_tagged_blocks(blocks, slot.value, slot.value)
            if rendered:
                parts.append(rendered)

    return "\n\n".join(parts)
