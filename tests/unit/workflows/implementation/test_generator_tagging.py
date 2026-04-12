# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for artifact tagging injection in the implementation generator."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from specweaver.workflows.implementation.generator import Generator

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_generator_injects_uuid_to_prompt(tmp_path: Path) -> None:
    """generate_code translates artifact_uuid to a prompt instruction."""
    llm = AsyncMock()
    llm.generate.return_value.text = "```python\nx = 1\n```"
    llm.provider_name = "mock"
    llm.model = "mock-model"

    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Spec")
    output_path = tmp_path / "out.py"

    generator = Generator(llm=llm)

    await generator.generate_code(
        spec_path=spec_path,
        output_path=output_path,
        artifact_uuid="12345678-1234-1234-1234-123456789abc",
    )

    # Check the messages sent to the LLM
    call_args = llm.generate.call_args
    assert call_args is not None
    messages = call_args[0][0]

    # PromptBuilder adds priority=0 tagging instructions
    user_prompt = messages[1].content
    assert "12345678-1234-1234-1234-123456789abc" in user_prompt
    assert "sw-artifact:" in user_prompt


@pytest.mark.asyncio
async def test_generator_tests_injects_uuid_to_prompt(tmp_path: Path) -> None:
    """generate_tests translates artifact_uuid to a prompt instruction."""
    llm = AsyncMock()
    llm.generate.return_value.text = "```python\ndef test_x(): pass\n```"
    llm.provider_name = "mock"
    llm.model = "mock-model"

    spec_path = tmp_path / "spec.md"
    spec_path.write_text("# Spec")
    output_path = tmp_path / "test_out.py"

    generator = Generator(llm=llm)

    await generator.generate_tests(
        spec_path=spec_path,
        output_path=output_path,
        artifact_uuid="87654321-4321-4321-4321-cba987654321",
    )

    # Check the messages sent to the LLM
    call_args = llm.generate.call_args
    assert call_args is not None
    messages = call_args[0][0]

    user_prompt = messages[1].content
    assert "87654321-4321-4321-4321-cba987654321" in user_prompt
    assert "sw-artifact:" in user_prompt
