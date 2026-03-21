# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests for specweaver.context.hitl_provider — interactive HITL context."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from specweaver.context.hitl_provider import HITLProvider
from specweaver.context.provider import ContextProvider


class TestHITLProviderInit:
    """Construction and basic properties."""

    def test_name_is_hitl(self) -> None:
        provider = HITLProvider()
        assert provider.name == "hitl"

    def test_default_console(self) -> None:
        provider = HITLProvider()
        assert isinstance(provider._console, Console)

    def test_custom_console(self) -> None:
        console = Console()
        provider = HITLProvider(console=console)
        assert provider._console is console

    def test_is_context_provider(self) -> None:
        assert issubclass(HITLProvider, ContextProvider)


class TestHITLProviderAsk:
    """Interactive prompting behaviour."""

    @pytest.mark.asyncio
    async def test_ask_returns_user_input(self) -> None:
        provider = HITLProvider()
        with patch("specweaver.context.hitl_provider.Prompt.ask", return_value="my answer"):
            result = await provider.ask("What is X?")
        assert result == "my answer"

    @pytest.mark.asyncio
    async def test_ask_strips_whitespace(self) -> None:
        provider = HITLProvider()
        with patch("specweaver.context.hitl_provider.Prompt.ask", return_value="  padded  "):
            result = await provider.ask("Q?")
        assert result == "padded"

    @pytest.mark.asyncio
    async def test_ask_empty_returns_empty(self) -> None:
        provider = HITLProvider()
        with patch("specweaver.context.hitl_provider.Prompt.ask", return_value=""):
            result = await provider.ask("Q?")
        assert result == ""

    @pytest.mark.asyncio
    async def test_ask_with_section_prints_context(self) -> None:
        console = MagicMock(spec=Console)
        provider = HITLProvider(console=console)
        with patch("specweaver.context.hitl_provider.Prompt.ask", return_value="ok"):
            await provider.ask("Q?", section="Purpose")
        # Should have printed section context
        calls = [str(c) for c in console.print.call_args_list]
        assert any("Purpose" in c for c in calls)

    @pytest.mark.asyncio
    async def test_ask_without_section_no_section_line(self) -> None:
        console = MagicMock(spec=Console)
        provider = HITLProvider(console=console)
        with patch("specweaver.context.hitl_provider.Prompt.ask", return_value="ok"):
            await provider.ask("Q?")
        # Only the question should be printed, not a section context
        assert console.print.call_count == 1
