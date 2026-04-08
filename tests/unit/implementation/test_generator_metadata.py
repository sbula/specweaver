# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for Generator ProjectMetadata injection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.implementation.generator import Generator
from specweaver.llm.models import LLMResponse, ProjectMetadata, PromptSafeConfig


class TestGeneratorProjectMetadata:
    """Generator injects project_metadata into the PromptBuilder."""

    @pytest.mark.asyncio
    async def test_generate_code_injects_metadata(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(text="```python\n# code\n```", model="test")

        generator = Generator(llm=mock_llm)
        metadata = ProjectMetadata(
            project_name="gen_test",
            archetype="pure-logic",
            language_target="python",
            date_iso="now",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test"),
        )

        with patch("pathlib.Path.read_text", return_value="spec content"):
            await generator.generate_code(
                Path("dummy.md"), Path("out.py"), project_metadata=metadata
            )

        prompt = mock_llm.generate.call_args[0][0][1].content
        assert "<project_metadata>" in prompt
        assert '"project_name": "gen_test"' in prompt

    @pytest.mark.asyncio
    async def test_generate_tests_injects_metadata(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(text="```python\n# tests\n```", model="test")

        generator = Generator(llm=mock_llm)
        metadata = ProjectMetadata(
            project_name="test_gen",
            archetype="pure-logic",
            language_target="python",
            date_iso="now",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test"),
        )

        with patch("pathlib.Path.read_text", return_value="content"):
            await generator.generate_tests(
                Path("dummy.md"), Path("out.py"), project_metadata=metadata
            )

        prompt = mock_llm.generate.call_args[0][0][1].content
        assert "<project_metadata>" in prompt
        assert '"project_name": "test_gen"' in prompt
