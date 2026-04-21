# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Reviewer environment_context pipeline integrations."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.workflows.review.reviewer import Reviewer

if TYPE_CHECKING:
    from pathlib import Path


class TestReviewerEnvironment:
    """Test that environment_context is successfully forwarded into the prompt builder."""

    @pytest.mark.asyncio
    async def test_environment_context_spec_review(self, tmp_path: Path) -> None:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="review content"))
        reviewer = Reviewer(llm=mock_llm)

        spec = tmp_path / "spec.md"
        spec.write_text("Spec info")

        await reviewer.review_spec(
            spec_path=spec,
            environment_context="mcp://database:\n  |\n    Users Schema: id, name",
        )

        args, _kwargs = mock_llm.generate.call_args
        prompt_built = args[0][1].content

        assert "Users Schema: id, name" in prompt_built

    @pytest.mark.asyncio
    async def test_environment_context_code_review(self, tmp_path: Path) -> None:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="review content"))
        reviewer = Reviewer(llm=mock_llm)

        spec = tmp_path / "spec.md"
        spec.write_text("Spec info")
        code = tmp_path / "code.py"
        code.write_text("def x(): pass")

        await reviewer.review_code(
            spec_path=spec,
            code_path=code,
            environment_context="mcp://testing:\n  |\n    pytest-helpers-mocked",
        )

        args, _kwargs = mock_llm.generate.call_args
        prompt_built = args[0][1].content

        assert "pytest-helpers-mocked" in prompt_built
