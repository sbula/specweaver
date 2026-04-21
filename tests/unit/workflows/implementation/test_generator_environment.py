# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Generator environment_context pipeline integrations."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from specweaver.workflows.implementation.generator import Generator


class TestGeneratorEnvironment:
    """Test that environment_context is successfully forwarded into the prompt builder."""

    @pytest.mark.asyncio
    async def test_environment_context_code(self, tmp_path: Path) -> None:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="generated code"))
        gen = Generator(llm=mock_llm)

        spec = tmp_path / "spec.md"
        spec.write_text("Spec info")
        out = tmp_path / "out.py"

        await gen.generate_code(
            spec_path=spec,
            output_path=out,
            environment_context="mcp://database:\n  |\n    Users Schema: id, name",
        )

        args, kwargs = mock_llm.generate.call_args
        prompt_built = args[0][1].content  # User Message Role is the second element

        # Verify the context builder appended the environment context mapped payload natively
        assert "Users Schema: id, name" in prompt_built

    @pytest.mark.asyncio
    async def test_environment_context_tests(self, tmp_path: Path) -> None:
        mock_llm = MagicMock()
        mock_llm.generate = AsyncMock(return_value=MagicMock(text="generated tests"))
        gen = Generator(llm=mock_llm)

        spec = tmp_path / "spec.md"
        spec.write_text("Spec info")
        out = tmp_path / "test_out.py"

        await gen.generate_tests(
            spec_path=spec,
            output_path=out,
            environment_context="mcp://testing:\n  |\n    pytest-helpers-mocked",
        )

        args, kwargs = mock_llm.generate.call_args
        prompt_built = args[0][1].content  # User message Role string

        assert "pytest-helpers-mocked" in prompt_built
