from __future__ import annotations

import pytest

from specweaver.infrastructure.llm._prompt_profiles import PromptSlot
from specweaver.infrastructure.llm._prompt_render import (
    _render_contexts,
    _render_tagged_blocks,
    _render_topology,
    render_blocks,
)
from specweaver.infrastructure.llm.prompt_builder import _ContentBlock


def _block(
    kind: str,
    text: str,
    label: str = "",
    priority: int = 3,
    tokens: int | None = None,
    truncated: bool = False,
) -> _ContentBlock:
    return _ContentBlock(
        kind=kind,
        label=label,
        text=text,
        priority=priority,
        tokens=tokens or 10,
        truncated=truncated,
    )


def test_render_blocks_with_order_respects_sequence() -> None:
    # R1: Profile order controls rendering sequence
    blocks = [
        _block("instructions", "Inst text"),
        _block("constitution", "Const text"),
    ]
    output = render_blocks(blocks, order=(PromptSlot.CONSTITUTION, PromptSlot.INSTRUCTIONS))
    assert "<constitution>" in output
    assert "<instructions>" in output
    assert output.find("<constitution>") < output.find("<instructions>")


def test_render_blocks_without_order_uses_legacy() -> None:
    # R2: No order -> current hardcoded sequence
    blocks = [
        _block("instructions", "Inst text"),
        _block("constitution", "Const text"),
    ]
    output = render_blocks(blocks)
    assert "<instructions>" in output
    assert "<constitution>" in output
    assert output.find("<instructions>") < output.find("<constitution>")


def test_render_blocks_skips_empty_slots() -> None:
    # R3: Slots in order with no matching blocks -> no empty tags
    blocks = [
        _block("instructions", "Inst text"),
    ]
    output = render_blocks(blocks, order=(PromptSlot.INSTRUCTIONS, PromptSlot.TOPOLOGY))
    assert "<instructions>" in output
    assert "<topology>" not in output


def test_render_topology_extracted_helper() -> None:
    # R4: _render_topology() produces same output as inline code - per-block pattern preserved
    blocks = [
        _block("topology", "Topo 1"),
        _block("topology", "Topo 2", truncated=True),
    ]
    output = _render_topology(blocks)
    assert output is not None
    assert "<topology>\nTopo 1\n</topology>" in output
    assert "<topology>\nTopo 2\n[truncated]\n</topology>" in output


def test_render_contexts_extracted_helper() -> None:
    # R5: _render_contexts() produces same output
    blocks = [
        _block("context", "Ctx 1", label="l1"),
        _block("context", "Ctx 2", label="l2", truncated=True),
    ]
    output = _render_contexts(blocks)
    assert output is not None
    assert '<context label="l1">\nCtx 1\n</context>' in output
    assert '<context label="l2">\nCtx 2\n[truncated]\n</context>' in output


def test_render_blocks_reminder_via_tagged_blocks() -> None:
    # R6: REMINDER routed through _render_tagged_blocks
    blocks = [
        _block("reminder", "Rem 1"),
        _block("reminder", "Rem 2", truncated=True),
    ]
    output = render_blocks(blocks, order=(PromptSlot.REMINDER,))
    assert "<reminder>\nRem 1\n\nRem 2\n[truncated]\n</reminder>" in output


def test_render_blocks_agent_memory_uses_tagged_renderer() -> None:
    # R7: Block with kind="agent_memory" renders as <agent_memory> not <context label="...">
    blocks = [
        _block("agent_memory", "Mem content"),
    ]
    output = render_blocks(blocks, order=(PromptSlot.AGENT_MEMORY,))
    assert "<agent_memory>\nMem content\n</agent_memory>" in output
    assert '<context label="agent_memory">' not in output
