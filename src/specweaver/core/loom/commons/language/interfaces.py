# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Interfaces for AST-based code parsing and skeleton extraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


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

    @abstractmethod
    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        """Extract framework-specific markers like annotations, decorators, and inheritance."""

    @abstractmethod
    def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:
        """Replace the entire symbol wrapper (decorators, signature, body)."""

    @abstractmethod
    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        """Replace only the inner execution block of a symbol."""

    @abstractmethod
    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        """Add a new symbol to the file or to a target parent symbol."""

    @abstractmethod
    def delete_symbol(self, code: str, symbol_name: str) -> str:
        """Remove a symbol completely from the file."""


# ---------------------------------------------------------------------------
# Scenario Pipeline Interfaces (Feature 3.28 SF-B2)
# ---------------------------------------------------------------------------


class ScenarioConverterInterface(ABC):
    """Language-specific converter from ``ScenarioSet`` to test file content.

    Mechanical (non-LLM). Produces language-native parametrized test files
    with ``# @trace(FR-X)`` tags for C09 compatibility.

    Each implementation fully owns the output path convention for its language.
    The handler calls ``output_path()`` and writes to the returned location —
    zero language awareness is required in the handler.
    """

    @abstractmethod
    def convert(self, scenario_set: object) -> str:
        """Convert a ``ScenarioSet`` to test file content.

        Args:
            scenario_set: The scenarios to convert.

        Returns:
            The complete test file content as a string.
        """

    @abstractmethod
    def output_path(self, stem: str, project_root: Path) -> Path:
        """Return the full absolute output path for the generated test file.

        Encodes the language's build-tool-enforced test convention:

        - **Python**: ``project_root/scenarios/generated/test_{stem}_scenarios.py``
        - **Java**: ``project_root/src/test/java/scenarios/generated/{Stem}ScenariosTest.java``
        - **Kotlin**: ``project_root/src/test/kotlin/scenarios/generated/{Stem}ScenariosTest.kt``
        - **TypeScript**: ``project_root/scenarios/generated/{stem}.scenarios.test.ts``
        - **Rust**: ``project_root/tests/{stem}_scenarios.rs``

        Args:
            stem: Component name  (e.g. ``'payment'``).
            project_root: Absolute path to the project root directory.

        Returns:
            Absolute ``Path`` to write the generated test file.
        """


class StackTraceFilterInterface(ABC):
    """Strips scenario test file frames from stack traces by language.

    Used by the Arbiter (SF-C) to produce coding agent feedback that contains
    zero scenario vocabulary — only the coding agent's own source frames.

    The scenario frame marker for each language is derived directly from the
    ``output_path()`` convention in ``ScenarioConverterInterface``:

    - **Python / TypeScript**: ``scenarios/generated/`` in the path string
    - **Java / Kotlin**: ``scenarios.generated.`` package prefix in JVM frame
    - **Rust**: ``_scenarios::`` module segment in frame symbol
    """

    @abstractmethod
    def filter(self, stack_trace: str) -> str:
        """Remove scenario file frames; preserve source code frames.

        Args:
            stack_trace: Raw stack trace text from a failing test.

        Returns:
            Filtered stack trace with all scenario frames removed.
        """

    @abstractmethod
    def is_scenario_frame(self, line: str) -> bool:
        """Return ``True`` if this line is from a scenario test file's frame."""
