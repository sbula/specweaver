# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Interfaces for AST-based code parsing and skeleton extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod


class CodeStructureError(Exception):
    """Raised when the CodeStructure parser encounters a fatal error or cannot resolve a symbol."""


class CodeStructureInterface(ABC):
    """Common abstraction for Polyglot AST extraction.

    This layer receives raw code strings from atoms and performs pure logic
    Tree-Sitter .scm queries to safely extract interface skeletons or symbol bodies.
    IO-bound operations are blocked from entering this component.
    """

    @abstractmethod
    def extract_skeleton(self, code: str) -> str:
        """Extract a simplified structural "skeleton" of the source code.

        The skeleton must contain ONLY:
        - Class definitions (with docstrings)
        - Method/Function signatures (with docstrings)
        - Imports

        All internal implementation bodies must be omitted.

        Args:
            code: The raw source code of the file.

        Returns:
            The raw string containing ONLY the file's interfaces.
        """

    @abstractmethod
    def extract_symbol(self, code: str, symbol_name: str) -> str:
        """Extract the exact full source code string of a specific symbol.

        Args:
            code: The raw source code of the file.
            symbol_name: The target node (e.g., 'MyClass' or 'my_function').

        Returns:
            The raw implementation string of the requested symbol.

        Raises:
            CodeStructureError: If the symbol cannot be found in the AST.
        """

    @abstractmethod
    def extract_symbol_body(self, code: str, symbol_name: str) -> str:
        """Extract the exact full source code string of a specific symbol's internal body block.

        This prevents mutation of the symbol's decorators or signature when performing rewrites.

        Args:
            code: The raw source code of the file.
            symbol_name: The target node (e.g., 'MyClass' or 'my_function').

        Returns:
            The raw execution logic inside the symbol bounds (e.g. `{...}` or `...`).

        Raises:
            CodeStructureError: If the symbol cannot be found in the AST.
        """

    @abstractmethod
    def list_symbols(self, code: str, visibility: list[str] | None = None) -> list[str]:
        """Dynamically map and list all targetable symbols within a file.

        Args:
            code: The raw source code of the file.
            visibility: Optional list to limit the payload to explicit access boundaries (e.g. ['public']).

        Returns:
            A flat array of all targetable symbols.
        """
