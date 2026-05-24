from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import pytest

from specweaver.infrastructure.llm._prompt_profiles import (
    _DEFAULT_PROFILE,
    PromptSlot,
    RenderProfile,
)
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from pathlib import Path

FULL = RenderProfile(
    name="full",
    active_slots=frozenset(PromptSlot),
    order=tuple(PromptSlot),
)

ARBITER = RenderProfile(
    name="arbiter",
    active_slots=frozenset([PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT]),
    order=(PromptSlot.INSTRUCTIONS, PromptSlot.CONTEXT),
)

MINIMAL = RenderProfile(
    name="minimal",
    active_slots=frozenset([PromptSlot.INSTRUCTIONS, PromptSlot.METADATA, PromptSlot.TOPOLOGY]),
    order=(PromptSlot.INSTRUCTIONS, PromptSlot.METADATA, PromptSlot.TOPOLOGY),
)


def test_builder_no_profile_uses_default() -> None:
    # B1
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        builder = PromptBuilder()
    assert builder._profile is _DEFAULT_PROFILE


def test_builder_no_profile_emits_deprecation_warning() -> None:
    # B2
    with pytest.warns(DeprecationWarning, match="PromptBuilder created without explicit profile"):
        PromptBuilder()


def test_builder_explicit_profile_no_warning() -> None:
    # B3
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        builder = PromptBuilder(profile=FULL)
    assert builder._profile is FULL


def test_inactive_slot_skips_add_instructions() -> None:
    # B4
    builder = PromptBuilder(profile=ARBITER)
    builder.add_constitution("Const text")
    assert not any(b.kind == "constitution" for b in builder._blocks)


def test_inactive_slot_skips_add_file_before_io(tmp_path: Path) -> None:
    # B5
    f = tmp_path / "x.py"
    builder = PromptBuilder(profile=ARBITER)
    # File does not exist; if it tries to read, it will raise FileNotFoundError
    builder.add_file(f)
    assert not any(b.kind == "file" for b in builder._blocks)


def test_inactive_slot_skips_add_mentioned_before_io(tmp_path: Path) -> None:
    # B6
    from specweaver.infrastructure.llm.mention_scanner.models import ResolvedMention

    f = tmp_path / "y.py"
    mention = ResolvedMention(original="y.py", resolved_path=f, kind="code")
    builder = PromptBuilder(profile=MINIMAL)
    builder.add_mentioned_files([mention])
    assert not any(b.kind == "mentioned" for b in builder._blocks)


def test_active_slot_allows_add() -> None:
    # B7
    builder = PromptBuilder(profile=FULL)
    builder.add_constitution("Const text")
    assert any(b.kind == "constitution" for b in builder._blocks)


def test_clone_preserves_profile() -> None:
    # B8
    builder = PromptBuilder(profile=ARBITER)
    cloned = builder.clone()
    assert cloned._profile is builder._profile


def test_add_context_with_slot_sets_kind() -> None:
    # B9
    builder = PromptBuilder(profile=FULL)
    builder.add_context("Mem", "agent_mem", slot=PromptSlot.AGENT_MEMORY)
    blocks = [b for b in builder._blocks if "Mem" in b.text]
    assert len(blocks) == 1
    assert blocks[0].kind == "agent_memory"


def test_add_context_default_slot_is_context() -> None:
    # B10
    builder = PromptBuilder(profile=FULL)
    builder.add_context("Ctx", "label")
    blocks = [b for b in builder._blocks if "Ctx" in b.text]
    assert len(blocks) == 1
    assert blocks[0].kind == "context"


def test_profile_controls_render_order() -> None:
    # B11
    builder = PromptBuilder(profile=ARBITER)
    builder.add_instructions("Inst text")
    builder.add_context("Ctx text", "label")
    output = builder.build()
    assert "<instructions>" in output
    assert '<context label="label">' in output
    assert output.find("<instructions>") < output.find("<context label=")


def test_full_profile_backward_compatible_output() -> None:
    # B12
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        legacy = PromptBuilder()
    full = PromptBuilder(profile=FULL)
    legacy.add_instructions("A").add_context("B", "C")
    full.add_instructions("A").add_context("B", "C")
    assert legacy.build() == full.build()


def test_is_slot_active_returns_correct() -> None:
    # B13
    builder = PromptBuilder(profile=ARBITER)
    assert builder._is_slot_active(PromptSlot.INSTRUCTIONS) is True
    assert builder._is_slot_active(PromptSlot.CONSTITUTION) is False
