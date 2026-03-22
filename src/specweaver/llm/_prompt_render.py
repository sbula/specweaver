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


def render_blocks(blocks: list[_ContentBlock]) -> str:
    """Render blocks into XML-tagged prompt text."""
    parts: list[str] = []

    # Instructions first
    instructions = [b for b in blocks if b.kind == "instructions"]
    if instructions:
        instr_text = "\n\n".join(b.text for b in instructions)
        parts.append(f"<instructions>\n{instr_text}\n</instructions>")

    # Constitution (after instructions, before topology)
    constitutions = [b for b in blocks if b.kind == "constitution"]
    if constitutions:
        text = "\n\n".join(b.text for b in constitutions)
        parts.append(f"<constitution>\n{text}\n</constitution>")

    # Standards (after constitution, before topology)
    standards = [b for b in blocks if b.kind == "standards"]
    if standards:
        text = "\n\n".join(b.text for b in standards)
        marker = "\n[truncated]" if any(b.truncated for b in standards) else ""
        parts.append(f"<standards>\n{text}{marker}\n</standards>")

    # Plan (after standards, before topology)
    plans = [b for b in blocks if b.kind == "plan"]
    if plans:
        text = "\n\n".join(b.text for b in plans)
        marker = "\n[truncated]" if any(b.truncated for b in plans) else ""
        parts.append(f"<plan>\n{text}{marker}\n</plan>")

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
