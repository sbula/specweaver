# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pure-logic protocols for language analyzers.

These protocols establish architectural boundaries, ensuring that context and discovery
layers can interoperate with structural code parsers (like Tree-Sitter) without
acquiring any C-bindings or I/O side-effects.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from pathlib import Path


class LanguageAnalyzer(Protocol):
    """Protocol for extracting structural context from source code natively."""

    def detect(self, directory: Path) -> bool:
        """Return True if this directory contains files of this language."""
        ...

    def extract_purpose(self, directory: Path) -> str | None:
        """Extract a one-sentence purpose from module-level docstrings."""
        ...

    def extract_imports(self, directory: Path) -> list[str]:
        """Extract all imported module names (top-level, deduplicated)."""
        ...

    def extract_public_symbols(self, directory: Path) -> list[str]:
        """Extract public symbol names (classes, functions, constants)."""
        ...

    def infer_archetype(self, directory: Path) -> str:
        """Heuristically infer the archetype from code patterns."""
        ...

    def get_binary_ignore_patterns(self) -> list[str]:
        """Get polyglot binary suppression patterns (e.g., *.pyc)."""
        ...

    def get_default_directory_ignores(self) -> list[str]:
        """Get polyglot directory suppression patterns (e.g., target/, node_modules/)."""
        ...

    def get_test_file_pattern(self) -> str:
        """Get the language-specific glob pattern for test files (e.g. test_*.py)."""
        ...

    def extract_test_mapped_requirements(self, directory: Path) -> set[str]:
        """Extract all traceability requirements dynamically mapped to test files within this directory."""
        ...


class AnalyzerFactoryProtocol(Protocol):
    """Protocol for resolving LanguageAnalyzer instances physically isolated from pure logic."""

    def for_directory(self, directory: Path) -> LanguageAnalyzer | None:
        """Return the first analyzer that detects its language in the directory."""
        ...

    def get_all_analyzers(self) -> list[LanguageAnalyzer]:
        """Return all globally registered language analyzers."""
        ...
