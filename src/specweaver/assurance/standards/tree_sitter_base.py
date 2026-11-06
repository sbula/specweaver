# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Base class for the style analyzers powered by tree-sitter, and the helpers they share.

Provides common infrastructure for loading grammars and executing
single-pass AST extraction across multiple files.
"""

from __future__ import annotations

import logging
import re
import time
from abc import abstractmethod
from typing import TYPE_CHECKING

from specweaver.assurance.standards.analyzer import CategoryResult, StandardsAnalyzer
from specweaver.assurance.standards.recency import recency_weight

if TYPE_CHECKING:
    from collections import Counter
    from collections.abc import Callable
    from pathlib import Path

    import tree_sitter

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface

logger = logging.getLogger(__name__)


def classify_name(name: str) -> str:
    """Classify an identifier's casing style."""
    if name.startswith("__") and name.endswith("__"):
        return "dunder"
    if re.match(r"^[A-Z][a-zA-Z0-9]*$", name):
        return "PascalCase"
    if re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", name):
        return "snake_case"
    if re.match(r"^[a-z][a-zA-Z0-9]*$", name):
        return "camelCase"
    if re.match(r"^[A-Z][A-Z0-9]*(_[A-Z0-9]+)*$", name):
        return "UPPER_SNAKE"
    return "other"


def compute_confidence(counter: Counter[str]) -> float:
    """Compute confidence as the fraction of the dominant pattern."""
    total = sum(counter.values())
    if total == 0:
        return 0.0
    return counter.most_common(1)[0][1] / total


def vote_result(category: str, sample_size: int, **votes: Counter[str]) -> CategoryResult:
    """A category's result from its vote counts: each non-empty count names its winner; the
    confidence is the first count's dominant share."""
    return CategoryResult(
        category=category,
        dominant={key: counts.most_common(1)[0][0] for key, counts in votes.items() if counts},
        confidence=compute_confidence(next(iter(votes.values()))),
        sample_size=sample_size,
    )


def file_weight(path: Path, half_life_days: float) -> float:
    """Calculate the recency weight of a file."""
    try:
        mtime = path.stat().st_mtime
    except OSError as exc:
        logger.debug("Failed to stat %s: %s", path, exc)
        mtime = time.time()
    return recency_weight(mtime, half_life_days=half_life_days)


class TreeSitterStyleAnalyzer(StandardsAnalyzer):
    """Base class for style analyzers using tree-sitter."""

    @abstractmethod
    def get_code_structure(self) -> CodeStructureInterface:
        """Return the core parser structure to use for extraction.

        Example:
            return TypeScriptCodeStructure()
        """
        ...

    @abstractmethod
    def get_extractors(self) -> list[Callable[..., CategoryResult]]:
        """Return a list of extraction methods to run during the single pass.

        Each extractor should accept:
            parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
        and return a ``CategoryResult``.
        """
        ...

    def extract_all(
        self,
        files: list[Path],
        half_life_days: float,
    ) -> list[CategoryResult]:
        """Extract all supported categories from the given files in a single pass."""
        parser = self.get_code_structure().parser

        parsed_files: list[tuple[Path, float, tree_sitter.Tree]] = []
        for path in files:
            try:
                source = path.read_bytes()
                tree = parser.parse(source)
                w = file_weight(path, half_life_days)
                parsed_files.append((path, w, tree))
            except Exception as e:
                logger.debug("Skipping %s: %s", path, e)

        results = []
        for extractor in self.get_extractors():
            try:
                results.append(extractor(parsed_files))
            except Exception as e:
                logger.warning("Failed to extract with %s: %s", extractor.__name__, e)

        return results
