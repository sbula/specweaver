# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python-specific standards analyzer using AST parsing.

Extracts coding conventions from Python source files in a single AST pass
per file, then aggregates results with recency weighting.

Categories: naming, error_handling, type_hints, docstrings,
            import_patterns, test_patterns.
"""

from __future__ import annotations

import ast
import logging
from collections import Counter
from typing import TYPE_CHECKING

from specweaver.assurance.standards.analyzer import CategoryResult, StandardsAnalyzer
from specweaver.assurance.standards.tree_sitter_base import (
    classify_name,
    file_weight,
    vote_result,
)
from specweaver.commons.languages import LANGUAGE_SUFFIXES

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.assurance.standards._documentation import documentation_result

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "naming",
    "error_handling",
    "type_hints",
    "docstrings",
    "import_patterns",
    "test_patterns",
]


#: Test frameworks recognised from an import, longest-prefix irrelevant — both are top-level names.
_TEST_FRAMEWORKS = ("pytest", "unittest")


def _framework_of(node: ast.AST) -> str | None:
    """The test framework an import statement names, if it names one."""
    if isinstance(node, ast.Import):
        return next((a.name for a in node.names if a.name in _TEST_FRAMEWORKS), None)
    if isinstance(node, ast.ImportFrom) and node.module:
        return next((f for f in _TEST_FRAMEWORKS if node.module.startswith(f)), None)
    return None


class PythonStandardsAnalyzer(StandardsAnalyzer):
    """Extract coding standards from Python source files via ``ast``."""

    def language_name(self) -> str:
        return "python"

    def file_extensions(self) -> set[str]:
        return set(LANGUAGE_SUFFIXES["python"])

    def supported_categories(self) -> list[str]:
        return list(_CATEGORIES)

    def extract_all(
        self,
        files: list[Path],
        half_life_days: float,
    ) -> list[CategoryResult]:
        parsed_files: list[tuple[Path, float, ast.Module]] = []
        for path in files:
            tree = self._parse_file(path)
            if tree is None:
                continue
            w = file_weight(path, half_life_days)
            parsed_files.append((path, w, tree))

        extractors = [
            self._extract_naming,
            self._extract_error_handling,
            self._extract_type_hints,
            self._extract_docstrings,
            self._extract_imports,
            self._extract_test_patterns,
        ]

        results = []
        for ext in extractors:
            try:
                results.append(ext(parsed_files))
            except Exception as e:
                logger.warning("Failed to extract with %s: %s", ext.__name__, e)

        return results

    # ------------------------------------------------------------------
    # Category extractors
    # ------------------------------------------------------------------

    def _extract_naming(
        self,
        parsed_files: list[tuple[Path, float, ast.Module]],
    ) -> CategoryResult:
        func_styles: Counter[str] = Counter()
        class_styles: Counter[str] = Counter()
        total_weight = 0.0
        sample_size = 0

        for _path, w, tree in parsed_files:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    if not node.name.startswith("_"):
                        style = classify_name(node.name)
                        func_styles[style] += round(w)
                        sample_size += 1
                elif isinstance(node, ast.ClassDef):
                    style = classify_name(node.name)
                    class_styles[style] += round(w)
                    sample_size += 1

            total_weight += w

        return vote_result(
            "naming", sample_size, function_style=func_styles, class_style=class_styles
        )

    def _extract_error_handling(
        self,
        parsed_files: list[tuple[Path, float, ast.Module]],
    ) -> CategoryResult:
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        styles["bare"] += round(w)
                    else:
                        styles["specific"] += round(w)
                    sample_size += 1

        return vote_result("error_handling", sample_size, exception_style=styles)

    def _extract_type_hints(
        self,
        parsed_files: list[tuple[Path, float, ast.Module]],
    ) -> CategoryResult:
        typed: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    has_annotations = node.returns is not None or any(
                        a.annotation is not None for a in node.args.args
                    )
                    typed["yes" if has_annotations else "no"] += round(w)
                    sample_size += 1

        return vote_result("type_hints", sample_size, usage=typed)

    def _extract_docstrings(
        self,
        parsed_files: list[tuple[Path, float, ast.Module]],
    ) -> CategoryResult:
        functions = [
            node
            for _path, _w, tree in parsed_files
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        documented = sum(1 for node in functions if ast.get_docstring(node))
        return documentation_result("docstrings", documented, len(functions))

    def _extract_imports(
        self,
        parsed_files: list[tuple[Path, float, ast.Module]],
    ) -> CategoryResult:
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    styles["absolute"] += round(w)
                    sample_size += 1
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        styles["relative"] += round(w)
                    else:
                        styles["absolute"] += round(w)
                    sample_size += 1

        return vote_result("import_patterns", sample_size, style=styles)

    def _extract_test_patterns(
        self,
        parsed_files: list[tuple[Path, float, ast.Module]],
    ) -> CategoryResult:
        frameworks: Counter[str] = Counter()
        sample_size = 0

        for path, w, tree in parsed_files:
            if not path.name.startswith("test_") and not path.name.endswith("_test.py"):
                continue

            framework = self._detect_test_framework(tree)
            if framework:
                frameworks[framework] += round(w)
                sample_size += 1

        return vote_result("test_patterns", sample_size, framework=frameworks)

    @staticmethod
    def _detect_test_framework(tree: ast.Module) -> str | None:
        """Detect whether a parsed AST uses pytest or unittest."""
        for node in ast.walk(tree):
            framework = _framework_of(node)
            if framework:
                return framework
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_file(path: Path) -> ast.Module | None:
        """Parse a Python file, returning None on syntax errors."""
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            return ast.parse(source, filename=str(path))
        except SyntaxError:
            logger.debug("Skipping %s: syntax error", path)
            return None
