# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for FeatureDrafter — 5-section feature spec template."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from specweaver.drafting.feature_drafter import (
    _FEATURE_SPEC_TEMPLATE,
    FEATURE_SECTIONS,
    FeatureDrafter,
)

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Section definitions
# ---------------------------------------------------------------------------


class TestFeatureSections:
    """Feature Spec has exactly 5 sections with the correct names."""

    def test_five_sections(self) -> None:
        assert len(FEATURE_SECTIONS) == 5

    def test_section_names(self) -> None:
        names = [s["name"] for s in FEATURE_SECTIONS]
        assert names == [
            "Intent",
            "Blast Radius",
            "Change Map",
            "Integration Seams",
            "Sequence",
        ]

    def test_each_section_has_required_keys(self) -> None:
        required = {"name", "heading", "question", "prompt"}
        for section in FEATURE_SECTIONS:
            assert required <= set(section.keys()), f"Missing keys in {section['name']}"


# ---------------------------------------------------------------------------
# Template rendering
# ---------------------------------------------------------------------------


class TestFeatureSpecTemplate:
    """_FEATURE_SPEC_TEMPLATE renders a complete Feature Spec."""

    def test_template_renders_name(self) -> None:
        result = _FEATURE_SPEC_TEMPLATE.render(
            name="Sell My Shares",
            date="2026-03-18",
            sections=[
                {"heading": "## Intent", "content": "Test intent."},
            ],
        )
        assert "Sell My Shares" in result

    def test_template_includes_feature_layer(self) -> None:
        result = _FEATURE_SPEC_TEMPLATE.render(
            name="Test",
            date="2026-03-18",
            sections=[],
        )
        assert "Feature" in result

    def test_template_includes_done_definition(self) -> None:
        result = _FEATURE_SPEC_TEMPLATE.render(
            name="Test",
            date="2026-03-18",
            sections=[],
        )
        assert "Done Definition" in result

    def test_template_includes_feature_check(self) -> None:
        result = _FEATURE_SPEC_TEMPLATE.render(
            name="Test",
            date="2026-03-18",
            sections=[],
        )
        assert "--level=feature" in result


# ---------------------------------------------------------------------------
# FeatureDrafter — integration with mock LLM
# ---------------------------------------------------------------------------


class TestFeatureDrafter:
    """FeatureDrafter co-authors a Feature Spec using LLM + context."""

    @pytest.fixture()
    def mock_llm(self) -> AsyncMock:
        llm = AsyncMock()
        response = AsyncMock()
        response.text = "Generated section content."
        llm.generate = AsyncMock(return_value=response)
        return llm

    @pytest.fixture()
    def mock_context(self) -> AsyncMock:
        context = AsyncMock()
        context.ask = AsyncMock(return_value="User provided answer.")
        return context

    @pytest.mark.asyncio()
    async def test_draft_creates_file(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        drafter = FeatureDrafter(llm=mock_llm, context_provider=mock_context)
        result = await drafter.draft("sell_shares", tmp_path)
        assert result.exists()
        assert result.name == "sell_shares_feature_spec.md"

    @pytest.mark.asyncio()
    async def test_draft_calls_llm_per_section(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        drafter = FeatureDrafter(llm=mock_llm, context_provider=mock_context)
        await drafter.draft("sell_shares", tmp_path)
        assert mock_llm.generate.call_count == 5

    @pytest.mark.asyncio()
    async def test_draft_asks_user_per_section(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        drafter = FeatureDrafter(llm=mock_llm, context_provider=mock_context)
        await drafter.draft("sell_shares", tmp_path)
        assert mock_context.ask.call_count == 5

    @pytest.mark.asyncio()
    async def test_draft_content_includes_all_headings(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        drafter = FeatureDrafter(llm=mock_llm, context_provider=mock_context)
        path = await drafter.draft("sell_shares", tmp_path)
        content = path.read_text(encoding="utf-8")
        for section in FEATURE_SECTIONS:
            assert section["heading"] in content

    @pytest.mark.asyncio()
    async def test_skipped_section_gets_placeholder(
        self, mock_llm: AsyncMock, tmp_path: Path
    ) -> None:
        context = AsyncMock()
        # First question answered, rest skipped
        context.ask = AsyncMock(side_effect=["answer", "", "", "", ""])
        drafter = FeatureDrafter(llm=mock_llm, context_provider=context)
        path = await drafter.draft("test_feature", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "TODO" in content
        # Only 1 LLM call (for the answered section)
        assert mock_llm.generate.call_count == 1

    @pytest.mark.asyncio()
    async def test_draft_output_dir_created(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        output = tmp_path / "nested" / "dir"
        drafter = FeatureDrafter(llm=mock_llm, context_provider=mock_context)
        path = await drafter.draft("test", output)
        assert output.exists()
        assert path.parent == output


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestFeatureDrafterEdgeCases:
    """Edge cases for FeatureDrafter."""

    @pytest.fixture()
    def mock_llm(self) -> AsyncMock:
        llm = AsyncMock()
        response = AsyncMock()
        response.text = "Generated."
        llm.generate = AsyncMock(return_value=response)
        return llm

    @pytest.fixture()
    def mock_context(self) -> AsyncMock:
        context = AsyncMock()
        context.ask = AsyncMock(return_value="User answer.")
        return context

    @pytest.mark.asyncio()
    async def test_llm_exception_propagates(self, mock_context: AsyncMock, tmp_path: Path) -> None:
        """If LLM raises mid-draft, exception propagates (no partial file)."""
        llm = AsyncMock()
        llm.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        drafter = FeatureDrafter(llm=llm, context_provider=mock_context)
        with pytest.raises(RuntimeError, match="LLM down"):
            await drafter.draft("crash_test", tmp_path)
        # No file should be written
        assert not (tmp_path / "crash_test_feature_spec.md").exists()

    @pytest.mark.asyncio()
    async def test_topology_only_injected_for_flagged_sections(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        """Topology is only injected for Blast Radius, Change Map, Integration Seams."""
        topology_flag_expected = {
            "Intent": False,
            "Blast Radius": True,
            "Change Map": True,
            "Integration Seams": True,
            "Sequence": False,
        }
        for section in FEATURE_SECTIONS:
            expected = topology_flag_expected[section["name"]]
            actual = bool(section.get("inject_topology"))
            assert actual == expected, (
                f"Section '{section['name']}' inject_topology={actual}, expected={expected}"
            )

    @pytest.mark.asyncio()
    async def test_overwrite_existing_file(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        """Drafting when file already exists silently overwrites."""
        drafter = FeatureDrafter(llm=mock_llm, context_provider=mock_context)
        # Create a file first
        existing = tmp_path / "sell_shares_feature_spec.md"
        existing.write_text("OLD CONTENT", encoding="utf-8")
        path = await drafter.draft("sell_shares", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "OLD CONTENT" not in content
        assert "Sell Shares" in content  # new content

    @pytest.mark.asyncio()
    async def test_name_with_underscores_titled(
        self, mock_llm: AsyncMock, mock_context: AsyncMock, tmp_path: Path
    ) -> None:
        """Feature name underscores are converted to title case in spec."""
        drafter = FeatureDrafter(llm=mock_llm, context_provider=mock_context)
        path = await drafter.draft("sell_my_shares", tmp_path)
        content = path.read_text(encoding="utf-8")
        assert "Sell My Shares" in content
