# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for Drafter ProjectMetadata injection."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from specweaver.drafting.drafter import Drafter
from specweaver.llm.models import LLMResponse, ProjectMetadata, PromptSafeConfig


class TestDrafterProjectMetadata:
    """Drafter injects project_metadata into the PromptBuilder."""

    @pytest.mark.asyncio
    async def test_draft_injects_metadata(self) -> None:
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = LLMResponse(text="```markdown\n# Doc\n```", model="test")

        mock_context = AsyncMock()
        mock_context.ask.return_value = "yes"

        drafter = Drafter(llm=mock_llm, context_provider=mock_context)
        metadata = ProjectMetadata(
            project_name="draft_test",
            archetype="pure-logic",
            language_target="python",
            date_iso="now",
            safe_config=PromptSafeConfig(llm_provider="test", llm_model="test")
        )

        # We need to mock write_text so it doesn't actually write to disk!
        with patch.object(Path, "write_text"):
            await drafter.draft(
                name="test_component",
                output_dir=Path("fake_dir"),
                project_metadata=metadata
            )

        prompt = mock_llm.generate.call_args[0][0][0].content
        assert "<project_metadata>" in prompt
        assert '"project_name": "draft_test"' in prompt
