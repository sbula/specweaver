# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Generator dictator overrides and validation findings injection.

Verifies that passing dictator_overrides= and validation_findings= to generate_code
and generate_tests actually results in them being injected into the prompt
via PromptBuilder.
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


class TestGeneratorOverridesInjection:
    """Verify hitl feedback kwargs flow through to PromptBuilder."""

    @pytest.mark.asyncio()
    async def test_generate_code_with_dictator_overrides(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_code with dictator_overrides= injects into PromptBuilder."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(
            spec,
            output,
            dictator_overrides=["Make the UI red"],
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<dictator-overrides>" in prompt
        assert "Make the UI red" in prompt

    @pytest.mark.asyncio()
    async def test_generate_code_with_validation_findings(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_code with validation_findings= outputs a Priority 2 <context> block."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(
            spec,
            output,
            validation_findings="[LINT01] Line too long.",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert '<context label="validation_errors">' in prompt
        assert "[LINT01] Line too long." in prompt

    @pytest.mark.asyncio()
    async def test_generate_tests_with_dictator_overrides(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_tests overrides are forwarded into the generated LLM prompt."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "test_out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_tests(
            spec,
            output,
            dictator_overrides=["Test negative balances too"],
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<dictator-overrides>" in prompt
        assert "Test negative balances too" in prompt

    @pytest.mark.asyncio()
    async def test_generate_tests_with_validation_findings(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_tests with findings maps findings to Priority 2 context."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "test_out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_tests(
            spec,
            output,
            validation_findings="[COV] Missing test case.",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert '<context label="validation_errors">' in prompt
        assert "[COV] Missing test case." in prompt
