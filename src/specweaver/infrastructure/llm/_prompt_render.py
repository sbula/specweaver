# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prompt rendering — XML-tagged output from content blocks."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.escaping import apply_escaping, escape_xml_attribute

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
        escaped_path = escape_xml_attribute(f.label)
        escaped_lang = escape_xml_attribute(f.language)
        attrs = f'path="{escaped_path}" language="{escaped_lang}"'
        if f.role:
            escaped_role = escape_xml_attribute(f.role)
            attrs += f' role="{escaped_role}"'
        escaped_text = apply_escaping(f.text, f.escaping)
        file_parts.append(
            f"<file {attrs}>\n{escaped_text}\n</file>",
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
    escaped_parts = [apply_escaping(b.text, b.escaping) for b in items]
    text = "\n\n".join(escaped_parts)
    return f"<{tag}>\n{text}\n</{tag}>"


def _render_mentioned(blocks: list[_ContentBlock]) -> str | None:
    """Render auto-detected mentioned files into XML."""
    mentioned = [b for b in blocks if b.kind == "mentioned"]
    if not mentioned:
        return None
    mention_parts: list[str] = []
    for m in mentioned:
        escaped_path = escape_xml_attribute(m.label)
        escaped_lang = escape_xml_attribute(m.language)
        attrs = f'path="{escaped_path}" language="{escaped_lang}"'
        if m.role:
            escaped_role = escape_xml_attribute(m.role)
            attrs += f' role="{escaped_role}"'
        escaped_text = apply_escaping(m.text, m.escaping)
        mention_parts.append(
            f"<file {attrs}>\n{escaped_text}\n</file>",
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
        escaped_text = apply_escaping(topo.text, topo.escaping)
        parts.append(
            f"<topology>\n{escaped_text}\n</topology>",
        )
    return "\n\n".join(parts)


def _render_contexts(blocks: list[_ContentBlock]) -> str | None:
    """Render context blocks into XML."""
    contexts = [b for b in blocks if b.kind == "context"]
    if not contexts:
        return None
    parts: list[str] = []
    for ctx in contexts:
        escaped_label = escape_xml_attribute(ctx.label)
        escaped_text = apply_escaping(ctx.text, ctx.escaping)
        parts.append(
            f'<context label="{escaped_label}">\n{escaped_text}\n</context>',
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
