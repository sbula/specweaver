# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Abstract base for language-specific standards analyzers.

Provides the ``StandardsAnalyzer`` ABC and data models (``CategoryResult``,
``ScopeReport``) used across all language implementations.

Each concrete analyzer (Python, JS/TS, Kotlin, etc.) registers its own
categories via ``supported_categories()`` and implements ``extract()``
for each.

Usage::

    from specweaver.standards.analyzer import (
        CategoryResult,
        ScopeReport,
        StandardsAnalyzer,
    )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path


@dataclass
class CategoryResult:
    """Result of extracting one category from source files.

    Attributes:
        category: Category name (e.g., "naming", "docstrings").
        dominant: Dominant pattern findings (e.g., {"style": "snake_case"}).
        confidence: Recency-weighted confidence score (0.0-1.0).
        sample_size: Number of samples analyzed.
        alternatives: Minority patterns with locations.
        conflicts: Human-readable conflict notes.
    """

    category: str
    dominant: Mapping[str, object]
    confidence: float
    sample_size: int
    language: str | None = None
    alternatives: Mapping[str, object] = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class ScopeReport:
    """Standards report for one scope x language combination.

    Attributes:
        scope: Directory scope name (e.g., "user-service" or ".").
        language: Programming language (e.g., "python", "typescript").
        categories: List of per-category extraction results.
    """

    scope: str
    language: str
    categories: list[CategoryResult] = field(default_factory=list)


class StandardsAnalyzer(ABC):
    """Abstract base for extracting coding standards from source files.

    Each concrete implementation handles one programming language.
    Categories are dynamic — each language defines its own set via
    ``supported_categories()``.
    """

    @abstractmethod
    def language_name(self) -> str:
        """Return the language this analyzer handles (e.g., 'python')."""
        ...

    @abstractmethod
    def file_extensions(self) -> set[str]:
        """Return file extensions this analyzer handles (e.g., {'.py'})."""
        ...

    @abstractmethod
    def supported_categories(self) -> list[str]:
        """Return language-specific category names.

        Examples: ``['naming', 'docstrings', 'type_hints']`` for Python,
        ``['naming', 'jsdoc', 'typescript_types']`` for JS/TS.
        """
        ...

    @abstractmethod
    def extract_all(
        self,
        files: list[Path],
        half_life_days: float,
    ) -> list[CategoryResult]:
        """Extract all supported categories from the given files in a single pass.

        Args:
            files: Source files to analyze.
            half_life_days: Decay half-life for recency weighting.

        Returns:
            List of CategoryResult containing findings for all supported categories.
        """
        ...
