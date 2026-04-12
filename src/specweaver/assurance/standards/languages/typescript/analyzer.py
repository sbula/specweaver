# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Typescript-specific standards analyzer using tree-sitter.

Inherits heavily from JSStandardsAnalyzer since the AST structure is very
similar, but adds TS-specific node extractors (e.g., interface vs type).
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

import tree_sitter
import tree_sitter_typescript

from specweaver.assurance.standards.analyzer import CategoryResult
from specweaver.assurance.standards.languages.javascript.analyzer import JSStandardsAnalyzer, walk_tree

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


class TSStandardsAnalyzer(JSStandardsAnalyzer):
    """Extract coding standards from Typescript source files via tree-sitter."""

    def language_name(self) -> str:
        return "typescript"

    def file_extensions(self) -> set[str]:
        return {".ts", ".tsx", ".cts", ".mts"}

    def supported_categories(self) -> list[str]:
        return [
            "naming",
            "error_handling",
            "tsdoc",
            "test_patterns",
            "import_patterns",
            "async_patterns",
            "typescript_types",
        ]

    def get_language(self) -> tree_sitter.Language:
        # We use the TSX grammar because it safely parses standard TS as well
        # as TSX components, covering both extensions effectively.
        return tree_sitter.Language(tree_sitter_typescript.language_tsx())

    def get_extractors(self) -> list[Callable[..., CategoryResult]]:
        return [
            self._extract_naming,
            self._extract_error_handling,
            self._extract_tsdoc,
            self._extract_test_patterns,
            self._extract_import_patterns,
            self._extract_async_patterns,
            self._extract_typescript_types,
        ]

    def _extract_tsdoc(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        """Reuse JS docstring extraction, but output as tsdoc category."""
        res = self._extract_jsdoc(parsed_files)
        # We copy all the calculated fields directly into a new CategoryResult
        return CategoryResult(
            category="tsdoc",
            dominant=res.dominant,
            confidence=res.confidence,
            sample_size=res.sample_size,
        )

    def _extract_typescript_types(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        """Determine whether interfaces or type aliases are dominantly used."""
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            nodes = walk_tree(tree)
            for node in nodes:
                if node.type == "interface_declaration":
                    styles["interface"] += round(w)
                    sample_size += 1
                elif node.type == "type_alias_declaration":
                    styles["type_alias"] += round(w)
                    sample_size += 1

        dominant: dict[str, str] = {}
        if styles:
            dominant["declaration"] = styles.most_common(1)[0][0]

        return CategoryResult(
            category="typescript_types",
            dominant=dominant,
            confidence=self._compute_confidence(styles) if styles else 0.0,
            sample_size=sample_size,
        )
