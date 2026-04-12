# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Generator plan kwarg integration.

Verifies that passing plan= to generate_code and generate_tests
actually results in the plan being injected into the prompt
via PromptBuilder.add_plan().
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


class TestGeneratorPlanInjection:
    """Verify plan kwarg flows through to PromptBuilder."""

    @pytest.mark.asyncio()
    async def test_generate_code_with_plan(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_code with plan= injects <plan> block into prompt."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(
            spec,
            output,
            plan="## Tasks\n1. Create module\n2. Add tests",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<plan>" in prompt
        assert "Create module" in prompt

    @pytest.mark.asyncio()
    async def test_generate_tests_with_plan(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_tests with plan= injects <plan> block into prompt."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "test_out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_tests(
            spec,
            output,
            plan="## File Layout\n- src/auth.py: Auth handler",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<plan>" in prompt
        assert "Auth handler" in prompt

    @pytest.mark.asyncio()
    async def test_generate_code_without_plan(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """generate_code without plan= has no <plan> block."""
        from specweaver.workflows.implementation.generator import Generator

        spec = tmp_path / "spec.md"
        spec.write_text("# Spec\n", encoding="utf-8")
        output = tmp_path / "out.py"

        gen = Generator(llm=mock_llm)
        await gen.generate_code(spec, output)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<plan>" not in prompt
