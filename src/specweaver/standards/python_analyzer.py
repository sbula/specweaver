# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Python-specific standards analyzer using AST parsing.

Extracts coding conventions from Python source files in a single AST pass
per file, then aggregates results with recency weighting.

Categories: naming, error_handling, type_hints, docstrings,
            import_patterns, test_patterns.
"""

from __future__ import annotations

import ast
import logging
import re
import time
from collections import Counter
from typing import TYPE_CHECKING

from specweaver.standards.analyzer import CategoryResult, StandardsAnalyzer
from specweaver.standards.recency import recency_weight

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "naming",
    "error_handling",
    "type_hints",
    "docstrings",
    "import_patterns",
    "test_patterns",
]


def _classify_name(name: str) -> str:
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


class PythonStandardsAnalyzer(StandardsAnalyzer):
    """Extract coding standards from Python source files via ``ast``."""

    def language_name(self) -> str:
        return "python"

    def file_extensions(self) -> set[str]:
        return {".py"}

    def supported_categories(self) -> list[str]:
        return list(_CATEGORIES)

    def extract(
        self,
        category: str,
        files: list[Path],
        half_life_days: float,
    ) -> CategoryResult:
        if category not in _CATEGORIES:
            msg = f"Unsupported category: {category}"
            raise ValueError(msg)

        extractors = {
            "naming": self._extract_naming,
            "error_handling": self._extract_error_handling,
            "type_hints": self._extract_type_hints,
            "docstrings": self._extract_docstrings,
            "import_patterns": self._extract_imports,
            "test_patterns": self._extract_test_patterns,
        }
        return extractors[category](files, half_life_days)

    # ------------------------------------------------------------------
    # Category extractors
    # ------------------------------------------------------------------

    def _extract_naming(
        self, files: list[Path], half_life_days: float,
    ) -> CategoryResult:
        func_styles: Counter = Counter()
        class_styles: Counter = Counter()
        total_weight = 0.0
        sample_size = 0

        for path in files:
            tree = self._parse_file(path)
            if tree is None:
                continue
            w = self._file_weight(path, half_life_days)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    if not node.name.startswith("_"):
                        style = _classify_name(node.name)
                        func_styles[style] += w
                        sample_size += 1
                elif isinstance(node, ast.ClassDef):
                    style = _classify_name(node.name)
                    class_styles[style] += w
                    sample_size += 1

            total_weight += w

        dominant: dict = {}
        if func_styles:
            dominant["function_style"] = func_styles.most_common(1)[0][0]
        if class_styles:
            dominant["class_style"] = class_styles.most_common(1)[0][0]

        return CategoryResult(
            category="naming",
            dominant=dominant,
            confidence=self._compute_confidence(func_styles)
            if func_styles
            else 0.0,
            sample_size=sample_size,
        )

    def _extract_error_handling(
        self, files: list[Path], half_life_days: float,
    ) -> CategoryResult:
        styles: Counter = Counter()
        sample_size = 0

        for path in files:
            tree = self._parse_file(path)
            if tree is None:
                continue
            w = self._file_weight(path, half_life_days)

            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        styles["bare"] += w
                    else:
                        styles["specific"] += w
                    sample_size += 1

        dominant: dict = {}
        if styles:
            dominant["exception_style"] = styles.most_common(1)[0][0]

        return CategoryResult(
            category="error_handling",
            dominant=dominant,
            confidence=self._compute_confidence(styles) if styles else 0.0,
            sample_size=sample_size,
        )

    def _extract_type_hints(
        self, files: list[Path], half_life_days: float,
    ) -> CategoryResult:
        typed: Counter = Counter()
        sample_size = 0

        for path in files:
            tree = self._parse_file(path)
            if tree is None:
                continue
            w = self._file_weight(path, half_life_days)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    has_annotations = (
                        node.returns is not None
                        or any(a.annotation is not None for a in node.args.args)
                    )
                    typed["yes" if has_annotations else "no"] += w
                    sample_size += 1

        dominant: dict = {}
        if typed:
            dominant["usage"] = typed.most_common(1)[0][0]

        return CategoryResult(
            category="type_hints",
            dominant=dominant,
            confidence=self._compute_confidence(typed) if typed else 0.0,
            sample_size=sample_size,
        )

    def _extract_docstrings(
        self, files: list[Path], half_life_days: float,
    ) -> CategoryResult:
        total_funcs = 0
        documented = 0

        for path in files:
            tree = self._parse_file(path)
            if tree is None:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                    total_funcs += 1
                    if ast.get_docstring(node):
                        documented += 1

        dominant: dict = {}
        if total_funcs > 0:
            ratio = documented / total_funcs
            if ratio >= 0.9:
                dominant["coverage"] = "full"
            elif ratio >= 0.5:
                dominant["coverage"] = "high"
            elif ratio >= 0.2:
                dominant["coverage"] = "low"
            else:
                dominant["coverage"] = "none"

        return CategoryResult(
            category="docstrings",
            dominant=dominant,
            confidence=documented / total_funcs if total_funcs > 0 else 0.0,
            sample_size=total_funcs,
        )

    def _extract_imports(
        self, files: list[Path], half_life_days: float,
    ) -> CategoryResult:
        styles: Counter = Counter()
        sample_size = 0

        for path in files:
            tree = self._parse_file(path)
            if tree is None:
                continue
            w = self._file_weight(path, half_life_days)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    styles["absolute"] += w
                    sample_size += 1
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        styles["relative"] += w
                    else:
                        styles["absolute"] += w
                    sample_size += 1

        dominant: dict = {}
        if styles:
            dominant["style"] = styles.most_common(1)[0][0]

        return CategoryResult(
            category="import_patterns",
            dominant=dominant,
            confidence=self._compute_confidence(styles) if styles else 0.0,
            sample_size=sample_size,
        )

    def _extract_test_patterns(
        self, files: list[Path], half_life_days: float,
    ) -> CategoryResult:
        frameworks: Counter = Counter()
        sample_size = 0

        for path in files:
            if not path.name.startswith("test_") and not path.name.endswith(
                "_test.py",
            ):
                continue

            tree = self._parse_file(path)
            if tree is None:
                continue

            framework = self._detect_test_framework(tree)
            if framework:
                frameworks[framework] += self._file_weight(path, half_life_days)
                sample_size += 1

        dominant: dict = {}
        if frameworks:
            dominant["framework"] = frameworks.most_common(1)[0][0]

        return CategoryResult(
            category="test_patterns",
            dominant=dominant,
            confidence=self._compute_confidence(frameworks)
            if frameworks
            else 0.0,
            sample_size=sample_size,
        )

    @staticmethod
    def _detect_test_framework(tree: ast.Module) -> str | None:
        """Detect whether a parsed AST uses pytest or unittest."""
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "pytest":
                        return "pytest"
                    if alias.name == "unittest":
                        return "unittest"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("pytest"):
                    return "pytest"
                if node.module and node.module.startswith("unittest"):
                    return "unittest"
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

    @staticmethod
    def _file_weight(path: Path, half_life_days: float) -> float:
        """Get recency weight for a file."""
        try:
            mtime = path.stat().st_mtime
        except OSError:
            mtime = time.time()
        return recency_weight(mtime, half_life_days=half_life_days)

    @staticmethod
    def _compute_confidence(counter: Counter) -> float:
        """Compute confidence as the fraction of the dominant pattern."""
        if not counter:
            return 0.0
        total = sum(counter.values())
        if total == 0:
            return 0.0
        dominant_count = counter.most_common(1)[0][1]
        return dominant_count / total
