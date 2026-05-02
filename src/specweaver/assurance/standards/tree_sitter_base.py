# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Base class for language analyzers powered by tree-sitter.

Provides common infrastructure for loading grammars and executing
single-pass AST extraction across multiple files.
"""

from __future__ import annotations

import logging
import time
from abc import abstractmethod
from typing import TYPE_CHECKING

from specweaver.assurance.standards.analyzer import CategoryResult, StandardsAnalyzer
from specweaver.assurance.standards.recency import recency_weight

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    import tree_sitter

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface

logger = logging.getLogger(__name__)


class TreeSitterAnalyzer(StandardsAnalyzer):
    """Base class for standards analyzers using tree-sitter."""

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
                w = self._file_weight(path, half_life_days)
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

    @staticmethod
    def _file_weight(path: Path, half_life_days: float) -> float:
        """Calculate the recency weight of a file."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = time.time()
        return recency_weight(mtime, half_life_days=half_life_days)
