# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for Generator standards kwarg integration.

Verifies that passing standards= to generate_code and generate_tests
actually results in the standards being injected into the prompt
via PromptBuilder.add_standards().
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def mock_llm():
    """Create a mock LLM adapter."""
    llm = AsyncMock()
    llm.generate = AsyncMock(
        return_value=MagicMock(text="def hello():\n    pass\n"),
    )
    return llm


class TestGeneratorStandardsInjection:
    """Verify standards kwarg flows through to PromptBuilder."""

    @pytest.mark.asyncio()
    async def test_generate_code_with_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_code with standards= injects into PromptBuilder."""
        from specweaver.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(
            spec,
            output,
            standards="Use snake_case for functions",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<standards>" in prompt
        assert "snake_case" in prompt

    @pytest.mark.asyncio()
    async def test_generate_code_without_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_code without standards= has no <standards> block."""
        from specweaver.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(spec, output)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<standards>" not in prompt

    @pytest.mark.asyncio()
    async def test_generate_tests_with_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_tests with standards= injects into PromptBuilder."""
        from specweaver.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "test_out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_tests(
            spec,
            output,
            standards="All functions must have docstrings",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<standards>" in prompt
        assert "docstrings" in prompt

    @pytest.mark.asyncio()
    async def test_generate_tests_without_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_tests without standards= has no <standards> block."""
        from specweaver.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "test_out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_tests(spec, output)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<standards>" not in prompt

    @pytest.mark.asyncio()
    async def test_standards_and_constitution_both_injected(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """Both constitution and standards can be injected together."""
        from specweaver.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(
            spec,
            output,
            constitution="Be strict",
            standards="Use snake_case",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<constitution>" in prompt
        assert "<standards>" in prompt
        # Constitution before standards in render order
        assert prompt.index("<constitution>") < prompt.index("<standards>")

    @pytest.mark.asyncio()
    async def test_output_file_still_written(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """Standards injection doesn't break file writing."""
        from specweaver.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        result = await gen.generate_code(
            spec,
            output,
            standards="Use type hints",
        )

        assert result == output
        assert output.exists()
        assert output.read_text(encoding="utf-8").strip() != ""
