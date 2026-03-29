# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Prompt rendering — XML-tagged output from content blocks."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.llm.prompt_builder import _ContentBlock


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


def render_blocks(blocks: list[_ContentBlock]) -> str:
    """Render blocks into XML-tagged prompt text."""
    parts: list[str] = []

    # Render standard top-level tagged blocks in exact order
    ordered_tags = [
        "instructions",
        "project_metadata",
        "constitution",
        "standards",
        "plan",
    ]
    for tag in ordered_tags:
        rendered = _render_tagged_blocks(blocks, tag, tag)
        if rendered:
            parts.append(rendered)

    # Topology (before files — gives structural context)
    topology = [b for b in blocks if b.kind == "topology"]
    for topo in topology:
        marker = "\n[truncated]" if topo.truncated else ""
        parts.append(
            f"<topology>\n{topo.text}{marker}\n</topology>",
        )

    # Files (delegated to render_files)
    file_xml = render_files(blocks)
    if file_xml:
        parts.append(file_xml)

    # Mentioned files (auto-detected from prior LLM responses)
    mentioned_xml = _render_mentioned(blocks)
    if mentioned_xml:
        parts.append(mentioned_xml)

    # Context blocks
    contexts = [b for b in blocks if b.kind == "context"]
    for ctx in contexts:
        marker = "\n[truncated]" if ctx.truncated else ""
        parts.append(
            f'<context label="{ctx.label}">\n{ctx.text}{marker}\n</context>',
        )

    # Reminders at the very end
    reminders = [b for b in blocks if b.kind == "reminder"]
    if reminders:
        reminder_text = "\n\n".join(b.text for b in reminders)
        parts.append(f"<reminder>\n{reminder_text}\n</reminder>")

    return "\n\n".join(parts)
