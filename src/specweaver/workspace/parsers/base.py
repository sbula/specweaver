# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Abstract base class for Tree-sitter CodeStructure parsers."""

from __future__ import annotations

import logging
import typing
from abc import ABC, abstractmethod

from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.parsers.interfaces import (
    CodeStructureError,
    CodeStructureInterface,
)

logger = logging.getLogger(__name__)


class BaseTreeSitterParser(CodeStructureInterface, ABC):
    """Base class centralizing Tree-sitter AST mutation and extraction."""

    @property
    @abstractmethod
    def language(self) -> Language:
        """The Tree-sitter Language binding."""

    @property
    @abstractmethod
    def parser(self) -> Parser:
        """The initialized Tree-sitter Parser."""

    @property
    @abstractmethod
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        """Tree-sitter query for skeletons."""

    @property
    @abstractmethod
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        """Tree-sitter query for extracting symbols."""

    @property
    @abstractmethod
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        """Tree-sitter query for extracting comments/trace tags."""

    @abstractmethod
    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        """Hook to filter symbols by visibility/decorators."""

    @abstractmethod
    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        """Finds the bounding node for a given symbol name."""

    @abstractmethod
    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        """Finds the inner block/body node of a given symbol node."""

    @abstractmethod
    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        """Hook to format a full symbol replacement."""

    @abstractmethod
    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        """Hook to format injecting new code into an existing block body."""

    def _extract_marker_text(self, node: typing.Any) -> str:
        return typing.cast("bytes", node.text).decode("utf-8").strip()

    def _auto_indent(self, new_code: str, margin: int) -> str:
        if not new_code:
            return new_code
        lines = new_code.split("\n")
        padded = []
        for i, line in enumerate(lines):
            if i == 0:
                padded.append(line)
            else:
                if line.strip() == "":
                    padded.append(line)
                else:
                    padded.append((" " * margin) + line)
        return "\n".join(padded)

    def extract_skeleton(self, code: str) -> str:
        if not code.strip():
            return code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        query = Query(self.language, self.SCM_SKELETON_QUERY)
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)

        nodes_to_blank: list[tuple[int, int]] = []

        if "block" in captures:
            for node in captures["block"]:
                start_cut = node.start_byte + 1
                end_cut = node.end_byte - 1

                if node.children:
                    first_child = node.children[0]
                    if (
                        first_child.type == "expression_statement"
                        and first_child.children
                        and first_child.children[0].type == "string"
                    ):
                        start_cut = first_child.end_byte

                if start_cut < end_cut:
                    nodes_to_blank.append((start_cut, end_cut))

        nodes_to_blank.sort(key=lambda x: x[0], reverse=True)

        skeleton = code_bytes
        for start_byte, end_byte in nodes_to_blank:
            skeleton = skeleton[:start_byte] + b" ... " + skeleton[end_byte:]

        return skeleton.decode("utf-8")

    def extract_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot extract '{symbol_name}' from empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")
        return typing.cast("bytes", node.text).decode("utf-8")

    def extract_symbol_body(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot extract body of '{symbol_name}' from empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")

        target_block = self._find_target_block(node)
        if not target_block:
            raise CodeStructureError(f"Body block for symbol '{symbol_name}' not found.")
        return typing.cast("bytes", target_block.text).decode("utf-8")

    def list_symbols(
        self, code: str, visibility: list[str] | None = None, decorator_filter: str | None = None
    ) -> list[str]:
        if not code.strip():
            return []

        framework_markers = {}
        if decorator_filter:
            framework_markers = self.extract_framework_markers(code)

        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        symbols = []
        for _match_id, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    sym_name = typing.cast("bytes", name_node.text).decode("utf-8")
                    if self._is_symbol_valid(
                        sym_name, name_node, visibility, decorator_filter, framework_markers
                    ):
                        symbols.append(sym_name)

        seen = set()
        unique_symbols = []
        for x in symbols:
            if x not in seen:
                seen.add(x)
                unique_symbols.append(x)
        return unique_symbols

    def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace '{symbol_name}' in empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)

        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        mutated = self._format_replacement(code_bytes, node, new_code)
        return mutated.decode("utf-8")

    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace body of '{symbol_name}' in empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        target_block = self._find_target_block(node)
        if not target_block:
            raise CodeStructureError(f"Body block for symbol '{symbol_name}' not found.")

        margin = typing.cast("int", node.start_point[1])
        mutated = self._format_body_injection(code_bytes, target_block, new_code, margin)
        return mutated.decode("utf-8")

    def delete_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            return code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)

        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        mutated = code_bytes[:start_byte] + code_bytes[end_byte:]
        return mutated.decode("utf-8")

    def extract_traceability_tags(self, code: str) -> set[str]:
        if not code.strip():
            return set()
        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, self.SCM_COMMENT_QUERY)
        cursor = QueryCursor(query)
        tags: set[str] = set()

        import re

        trace_pattern = re.compile(r"@trace\(([^)]+)\)")

        for _, match_dict in cursor.matches(tree.root_node):
            if "comment" in match_dict:
                for comment_node in match_dict["comment"]:
                    text = typing.cast("bytes", comment_node.text).decode("utf-8")
                    match = trace_pattern.search(text)
                    if match:
                        content = match.group(1)
                        for part in content.split(","):
                            tags.add(part.strip())
        return tags
