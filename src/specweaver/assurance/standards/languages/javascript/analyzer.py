# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Javascript-specific standards analyzer using tree-sitter.

Extracts coding conventions from Javascript source files in a single pass.
"""

from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

import tree_sitter
import tree_sitter_javascript

from specweaver.assurance.standards.analyzer import CategoryResult
from specweaver.assurance.standards.languages.python.analyzer import (
    _classify_name,  # We can reuse the Python naming classifier for basic cases
)
from specweaver.assurance.standards.tree_sitter_base import TreeSitterAnalyzer

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


def walk_tree(tree: tree_sitter.Tree) -> list[tree_sitter.Node]:
    """Generator that yields all nodes in a tree-sitter tree (DFS)."""
    cursor = tree.walk()
    reached_root = False
    nodes: list[tree_sitter.Node] = []

    while not reached_root:
        if cursor.node is not None:
            nodes.append(cursor.node)
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue

        retracing = True
        while retracing:
            if not cursor.goto_parent():
                retracing = False
                reached_root = True
            elif cursor.goto_next_sibling():
                retracing = False

    return nodes


def walk_node(node: tree_sitter.Node) -> list[tree_sitter.Node]:
    """Walk all descendants of a Node (DFS), not requiring a Tree root."""
    results: list[tree_sitter.Node] = []
    stack = [node]
    while stack:
        current = stack.pop()
        results.append(current)
        stack.extend(reversed(current.children))
    return results


class JSStandardsAnalyzer(TreeSitterAnalyzer):
    """Extract coding standards from Javascript source files via tree-sitter."""

    def language_name(self) -> str:
        return "javascript"

    def file_extensions(self) -> set[str]:
        return {".js", ".jsx", ".cjs", ".mjs"}

    def supported_categories(self) -> list[str]:
        return [
            "naming",
            "error_handling",
            "jsdoc",
            "test_patterns",
            "import_patterns",
            "async_patterns",
        ]

    def get_language(self) -> tree_sitter.Language:
        return tree_sitter.Language(tree_sitter_javascript.language())

    def get_extractors(self) -> list[Callable[..., CategoryResult]]:
        return [
            self._extract_naming,
            self._extract_error_handling,
            self._extract_jsdoc,
            self._extract_test_patterns,
            self._extract_import_patterns,
            self._extract_async_patterns,
        ]

    def _compute_confidence(self, counter: Counter[str]) -> float:
        """Compute confidence as the fraction of the dominant pattern."""
        if not counter:
            return 0.0
        total = sum(counter.values())
        if total == 0:
            return 0.0
        dominant_count = counter.most_common(1)[0][1]
        return dominant_count / total

    # ------------------------------------------------------------------
    # Extractors
    # ------------------------------------------------------------------

    def _extract_naming(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        func_styles: Counter[str] = Counter()
        class_styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            nodes = walk_tree(tree)
            for node in nodes:
                result = self._classify_naming_node(node)
                if result:
                    target, style = result
                    if target == "func":
                        func_styles[style] += round(w)
                    else:
                        class_styles[style] += round(w)
                    sample_size += 1

        dominant: dict[str, str] = {}
        if func_styles:
            dominant["function_style"] = func_styles.most_common(1)[0][0]
        if class_styles:
            dominant["class_style"] = class_styles.most_common(1)[0][0]

        return CategoryResult(
            category="naming",
            dominant=dominant,
            confidence=self._compute_confidence(func_styles) if func_styles else 0.0,
            sample_size=sample_size,
        )

    @staticmethod
    def _classify_naming_node(node: tree_sitter.Node) -> tuple[str, str] | None:
        """Classify a node for naming convention. Returns (target, style) or None."""
        if node.type == "function_declaration":
            name_node = node.child_by_field_name("name")
            if name_node and name_node.text:
                return ("func", _classify_name(name_node.text.decode("utf-8")))
        elif node.type == "variable_declarator":
            name_node = node.child_by_field_name("name")
            value_node = node.child_by_field_name("value")
            if (
                name_node
                and name_node.text
                and value_node
                and value_node.type in ("arrow_function", "function", "function_expression")
            ):
                return ("func", _classify_name(name_node.text.decode("utf-8")))
        elif node.type == "class_declaration":
            name_node = node.child_by_field_name("name")
            if name_node and name_node.text:
                return ("class", _classify_name(name_node.text.decode("utf-8")))
        return None

    def _extract_error_handling(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            nodes = walk_tree(tree)
            for node in nodes:
                if node.type == "catch_clause":
                    is_specific = self._is_specific_catch(node)
                    styles["specific" if is_specific else "bare"] += round(w)
                    sample_size += 1

        dominant: dict[str, str] = {}
        if styles:
            dominant["exception_style"] = styles.most_common(1)[0][0]

        return CategoryResult(
            category="error_handling",
            dominant=dominant,
            confidence=self._compute_confidence(styles) if styles else 0.0,
            sample_size=sample_size,
        )

    @staticmethod
    def _is_specific_catch(node: tree_sitter.Node) -> bool:
        """Check if a catch clause uses specific error type handling."""
        body = node.child_by_field_name("body")
        if not body:
            return False
        for bnode in walk_node(body):
            if bnode.type == "instanceof_expression":
                return True
            if bnode.type == "member_expression":
                prop = bnode.child_by_field_name("property")
                if prop and prop.text and prop.text.decode("utf-8") == "name":
                    return True
        return False

    def _extract_jsdoc(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        total_funcs = 0
        documented = 0

        for _path, _w, tree in parsed_files:
            nodes = walk_tree(tree)
            for node in nodes:
                if node.type in ("function_declaration", "arrow_function", "method_definition"):
                    total_funcs += 1
                    # In tree-sitter, comments preceding a node are typically previous siblings
                    prev = node.prev_sibling
                    if prev and prev.type == "comment" and prev.text is not None:
                        text = prev.text.decode("utf-8")
                        if text.startswith("/**"):
                            documented += 1

        dominant: dict[str, str] = {}
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
            category="jsdoc",
            dominant=dominant,
            confidence=documented / total_funcs if total_funcs > 0 else 0.0,
            sample_size=total_funcs,
        )

    def _extract_import_patterns(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            nodes = walk_tree(tree)
            for node in nodes:
                if node.type == "import_statement":
                    styles["es6"] += round(w)
                    sample_size += 1
                elif node.type == "call_expression":
                    func = node.child_by_field_name("function")
                    if (
                        func
                        and func.type == "identifier"
                        and func.text
                        and func.text.decode("utf-8") == "require"
                    ):
                        styles["commonjs"] += round(w)
                        sample_size += 1

        dominant: dict[str, str] = {}
        if styles:
            dominant["style"] = styles.most_common(1)[0][0]

        return CategoryResult(
            category="import_patterns",
            dominant=dominant,
            confidence=self._compute_confidence(styles) if styles else 0.0,
            sample_size=sample_size,
        )

    def _extract_async_patterns(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        styles: Counter[str] = Counter()
        sample_size = 0

        for _path, w, tree in parsed_files:
            nodes = walk_tree(tree)
            for node in nodes:
                pattern = self._classify_async_node(node)
                if pattern:
                    styles[pattern] += round(w)
                    sample_size += 1

        dominant: dict[str, str] = {}
        if styles:
            dominant["style"] = styles.most_common(1)[0][0]

        return CategoryResult(
            category="async_patterns",
            dominant=dominant,
            confidence=self._compute_confidence(styles) if styles else 0.0,
            sample_size=sample_size,
        )

    @staticmethod
    def _classify_async_node(node: tree_sitter.Node) -> str | None:
        """Classify a node as an async pattern. Returns pattern name or None."""
        if node.type == "await_expression":
            return "async/await"
        if node.type in ("function_declaration", "arrow_function"):
            for child in node.children:
                if child.type == "async":
                    return "async/await"
        elif node.type == "call_expression":
            func = node.child_by_field_name("function")
            if func and func.type == "member_expression":
                prop = func.child_by_field_name("property")
                if prop and prop.text and prop.text.decode("utf-8") in ("then", "catch", "finally"):
                    return "promises"
        return None

    def _extract_test_patterns(
        self, parsed_files: list[tuple[Path, float, tree_sitter.Tree]]
    ) -> CategoryResult:
        frameworks: Counter[str] = Counter()
        sample_size = 0

        for path, w, tree in parsed_files:
            if not path.name.endswith(".test.js") and not path.name.endswith(".spec.js"):
                continue

            nodes = walk_tree(tree)
            for node in nodes:
                if node.type == "call_expression":
                    func = node.child_by_field_name("function")
                    if func and func.type == "identifier" and func.text:
                        name = func.text.decode("utf-8")
                        if name in ("describe", "it", "xdescribe", "xit"):
                            frameworks["jest/mocha"] += round(w)
                            sample_size += 1

        dominant: dict[str, str] = {}
        if frameworks:
            dominant["framework"] = frameworks.most_common(1)[0][0]

        return CategoryResult(
            category="test_patterns",
            dominant=dominant,
            confidence=self._compute_confidence(frameworks) if frameworks else 0.0,
            sample_size=sample_size,
        )
