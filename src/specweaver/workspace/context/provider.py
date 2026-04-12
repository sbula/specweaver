# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Context provider — abstract interface for spec drafting context sources.

Context providers supply information to the drafter from various sources.
MVP: HITL (interactive user input). Future: file_search, RAG, web_search.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class ContextProvider(ABC):
    """Abstract interface for context providers.

    Provides answers to questions during spec drafting.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name (e.g., 'hitl', 'file_search', 'rag')."""
        ...

    @abstractmethod
    async def ask(self, question: str, *, section: str = "") -> str:
        """Ask a question and return the answer.

        Args:
            question: The question to ask.
            section: Which spec section the question relates to.

        Returns:
            Answer string. Empty string means "skip this question."
        """
        ...
