# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""HITL context provider — interactive user input during spec drafting.

Uses Rich prompts to ask the user questions and collect answers.
"""

from __future__ import annotations

import logging

from rich.console import Console
from rich.prompt import Prompt

from specweaver.workspace.context.provider import ContextProvider

logger = logging.getLogger(__name__)


class HITLProvider(ContextProvider):
    """Interactive HITL (Human-in-the-Loop) context provider.

    Prompts the user via the terminal for answers during spec drafting.
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()

    @property
    def name(self) -> str:
        return "hitl"

    async def ask(self, question: str, *, section: str = "") -> str:
        """Prompt the user for an answer via Rich.

        Args:
            question: The question to display.
            section: Which spec section this relates to (shown as context).

        Returns:
            User's answer. Empty string if they press Enter without typing.
        """
        if section:
            self._console.print(f"\n[dim]Section: {section}[/dim]")
        self._console.print(f"[bold cyan]?[/bold cyan] {question}")
        answer = Prompt.ask("[dim](press Enter to skip)[/dim]", default="", console=self._console)
        logger.debug("HITL response received, length=%d chars", len(answer.strip()))
        return answer.strip()
