# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Reviewer standards kwarg integration.

Verifies that passing standards= to review_spec and review_code
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
        return_value=MagicMock(text="VERDICT: ACCEPTED\nLooks good."),
    )
    return llm


class TestReviewerStandardsInjection:
    """Verify standards kwarg flows through to PromptBuilder."""

    @pytest.mark.asyncio()
    async def test_review_spec_with_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """review_spec with standards= injects into PromptBuilder."""
        from specweaver.workflows.review.reviewer import Reviewer

        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        reviewer = Reviewer(llm=mock_llm)
        await reviewer.review_spec(
            spec,
            standards="Use snake_case for functions",
        )

        # The LLM should have been called with a prompt containing standards
        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content  # The user message is the prompt
        assert "<standards>" in prompt
        assert "snake_case" in prompt

    @pytest.mark.asyncio()
    async def test_review_spec_without_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """review_spec without standards= has no <standards> block."""
        from specweaver.workflows.review.reviewer import Reviewer

        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        reviewer = Reviewer(llm=mock_llm)
        await reviewer.review_spec(spec)

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<standards>" not in prompt

    @pytest.mark.asyncio()
    async def test_review_code_with_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """review_code with standards= injects into PromptBuilder."""
        from specweaver.workflows.review.reviewer import Reviewer

        code = tmp_path / "code.py"
        code.write_text("def hello(): pass\n", encoding="utf-8")
        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        reviewer = Reviewer(llm=mock_llm)
        await reviewer.review_code(
            code,
            spec,
            standards="All functions must have docstrings",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<standards>" in prompt
        assert "docstrings" in prompt

    @pytest.mark.asyncio()
    async def test_review_code_without_standards(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """review_code without standards= has no <standards> block."""
        from specweaver.workflows.review.reviewer import Reviewer

        code = tmp_path / "code.py"
        code.write_text("def hello(): pass\n", encoding="utf-8")
        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        reviewer = Reviewer(llm=mock_llm)
        await reviewer.review_code(code, spec)

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
        from specweaver.workflows.review.reviewer import Reviewer

        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        reviewer = Reviewer(llm=mock_llm)
        await reviewer.review_spec(
            spec,
            constitution="Be strict about naming",
            standards="Use snake_case",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        assert "<constitution>" in prompt
        assert "<standards>" in prompt
        assert "snake_case" in prompt
        # Constitution must come before standards
        assert prompt.index("<constitution>") < prompt.index("<standards>")

    @pytest.mark.asyncio()
    async def test_standards_rendered_in_correct_position(
        self,
        tmp_path: Path,
        mock_llm,
    ) -> None:
        """Standards block appears between constitution and file contents."""
        from specweaver.workflows.review.reviewer import Reviewer

        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\n", encoding="utf-8")

        reviewer = Reviewer(llm=mock_llm)
        await reviewer.review_spec(
            spec,
            constitution="Const text",
            standards="Standards text",
        )

        call_args = mock_llm.generate.call_args
        messages = call_args[0][0]
        prompt = messages[-1].content
        const_pos = prompt.index("<constitution>")
        stds_pos = prompt.index("<standards>")
        file_pos = prompt.index("<file_contents>")
        assert const_pos < stds_pos < file_pos
