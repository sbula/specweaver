# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests for TopologyContext's PromptContentSource protocol conformance."""

from specweaver.assurance.graph.topology import TopologyContext
from specweaver.infrastructure.llm.prompt.interfaces import PromptContentSource
from specweaver.infrastructure.llm.prompt_builder import PromptBuilder


def test_topology_context_conforms_to_protocol() -> None:
    """Ensure TopologyContext conforms structurally to PromptContentSource protocol."""
    assert issubclass(TopologyContext, PromptContentSource)


def test_topology_context_prompt_formatting() -> None:
    """TopologyContext get_prompt_content produces correct XML tags and label."""
    ctx = TopologyContext(
        name="my-module",
        purpose="Perform database updates",
        archetype="service",
        relationship="direct dependency",
        constraints=["reliable", "fast"],
    )

    assert ctx.get_prompt_label() == "my-module"

    content = ctx.get_prompt_content()
    assert "<topology>" in content
    assert "</topology>" in content
    assert (
        "  - my-module (direct dependency): Perform database updates [archetype=service, constraints=reliable, fast]"
        in content
    )


def test_topology_context_truncation() -> None:
    """TopologyContext respects char_limit parameter during formatting."""
    ctx = TopologyContext(
        name="my-module",
        purpose="Perform database updates",
        archetype="service",
        relationship="direct dependency",
    )

    # Use a small limit that forces truncation of the inner text
    content = ctx.get_prompt_content(char_limit=20)
    assert "<topology>" in content
    assert "</topology>" in content
    assert "[truncated]" in content
    # The actual inner text is truncated, but XML tags are closed properly
    assert content.endswith("\n</topology>")


def test_topology_context_prompt_builder_integration() -> None:
    """PromptBuilder accepts a TopologyContext and renders it raw without double wrapping."""
    ctx = TopologyContext(
        name="auth-service",
        purpose="User authentication and token verification",
        archetype="service",
        relationship="direct consumer",
        constraints=["secure"],
    )

    builder = PromptBuilder()
    builder.add_context(ctx)
    result = builder.build()

    # It should not double wrap inside <context> tags
    assert '<context label="auth-service">' not in result
    assert "<topology>" in result
    assert "auth-service" in result
    assert "User authentication" in result
