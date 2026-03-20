# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Abstract base for language-specific standards analyzers.

Provides the ``StandardsAnalyzer`` ABC and data models (``CategoryResult``,
``ScopeReport``) used across all language implementations.

Each concrete analyzer (Python, JS/TS, Kotlin, etc.) registers its own
categories via ``supported_categories()`` and implements ``extract()``
for each.

Usage::

    from specweaver.context.standards_analyzer import (
        CategoryResult,
        ScopeReport,
        StandardsAnalyzer,
    )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CategoryResult:
    """Result of extracting one category from source files.

    Attributes:
        category: Category name (e.g., "naming", "docstrings").
        dominant: Dominant pattern findings (e.g., {"style": "snake_case"}).
        confidence: Recency-weighted confidence score (0.0–1.0).
        sample_size: Number of samples analyzed.
        alternatives: Minority patterns with locations.
        conflicts: Human-readable conflict notes.
    """

    category: str
    dominant: dict
    confidence: float
    sample_size: int
    alternatives: dict = field(default_factory=dict)
    conflicts: list[str] = field(default_factory=list)


@dataclass
class ScopeReport:
    """Standards report for one scope × language combination.

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
    def extract(
        self,
        category: str,
        files: list[Path],
        half_life_days: float,
    ) -> CategoryResult:
        """Extract one category from the given files.

        Args:
            category: One of the values from ``supported_categories()``.
            files: Source files to analyze.
            half_life_days: Decay half-life for recency weighting.

        Returns:
            CategoryResult with dominant patterns and confidence.

        Raises:
            ValueError: If *category* is not in ``supported_categories()``.
        """
        ...
