# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for PromptBuilder integration with the pluggable context protocol."""

import pytest

from specweaver.infrastructure.llm.models import TokenBudget
from specweaver.infrastructure.llm.prompt.interfaces import PromptContentSource
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder


class DummyAdapter:
    """A dummy class implementing PromptContentSource protocol."""

    def __init__(self, label: str, content: str):
        self.label = label
        self.content = content

    def get_prompt_label(self) -> str:
        return self.label

    def get_prompt_content(self, char_limit: int | None = None) -> str:
        text = self.content
        if char_limit is not None:
            text = text[:char_limit] + "\n[truncated]"
        # Wrap it directly in custom tags to simulate pre-escaped formatting
        return f'<custom_tag name="{self.label}">{text}</custom_tag>'


def test_conformance_check() -> None:
    """Ensure DummyAdapter conforms to PromptContentSource protocol."""
    assert issubclass(DummyAdapter, PromptContentSource)


def test_add_context_adapter_happy_path() -> None:
    """add_context accepts an adapter, gets its content and label, and renders it."""
    adapter = DummyAdapter("my-adapter", "adapter content data")
    builder = PromptBuilder()
    builder.add_context(adapter)
    result = builder.build()

    # The adapter returns its own custom tags, which should be rendered raw (no double wrapping)
    assert '<custom_tag name="my-adapter">adapter content data</custom_tag>' in result
    assert "<context" not in result  # Rendered directly, not wrapped inside <context> tags


def test_add_context_type_error() -> None:
    """add_context raises TypeError if the object does not conform to the protocol."""
    builder = PromptBuilder()
    with pytest.raises(TypeError, match="must conform to PromptContentSource"):
        # An arbitrary class with no get_prompt_content/label methods
        class InvalidSource:
            pass

        builder.add_context(InvalidSource())  # type: ignore


def test_chaining_legacy_and_pluggable_contexts() -> None:
    """PromptBuilder supports chaining legacy contexts and pluggable adapters."""
    adapter = DummyAdapter("plug-adapter", "plugged in")
    builder = (
        PromptBuilder()
        .add_instructions("Run instructions")
        .add_context("legacy string context", "legacy-label")
        .add_context(adapter)
    )
    result = builder.build()

    assert "<instructions>\nRun instructions\n</instructions>" in result
    assert '<context label="legacy-label">' in result
    assert "legacy string context" in result
    assert '<custom_tag name="plug-adapter">plugged in</custom_tag>' in result


def test_truncation_invokes_adapter_safe_truncation() -> None:
    """Safe truncation boundary: TokenBudget truncation calls get_prompt_content(char_limit)."""
    # Create an adapter with a very long string
    long_content = "A" * 1000
    adapter = DummyAdapter("trunc-adapter", long_content)

    # Use a tight token budget (e.g. 40 tokens)
    budget = TokenBudget(limit=40)
    builder = PromptBuilder(budget=budget)
    builder.add_instructions("Run")
    builder.add_context(adapter, priority=3)

    result = builder.build()

    # Since the budget was tight, it truncated.
    # The adapter's get_prompt_content(char_limit) returns:
    # "<custom_tag name="trunc-adapter">{truncated_content}\n[truncated]</custom_tag>"
    assert "[truncated]" in result
    assert '<custom_tag name="trunc-adapter">' in result
    assert "</custom_tag>" in result
