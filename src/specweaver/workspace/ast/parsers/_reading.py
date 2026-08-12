# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading structure out of a parsed file.

`TECH-035`. `BaseTreeSitterParser` was one class doing four jobs, at `LCOM4=8` — the most
incohesive class in the repo after `TECH-034` deliberately concentrated the parsers' shared
mechanics into it.

Reading and editing turned out to share **nothing**: measured, they have zero cross-references and
each depends only on the per-language contract the base declares. That is what made splitting them
a move rather than a rewrite.

A mixin rather than a collaborator, so no parser's public API changes — every one of them still
answers `extract_symbol` and the rest exactly as before.
"""

from __future__ import annotations

import logging
import typing

from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

logger = logging.getLogger(__name__)


class SymbolReadingMixin:
    """Extracting skeletons, symbols, bodies, listings and traceability tags."""

    # What this mixin needs from the parser it is mixed into. Declared for the type checker only:
    # it states the dependency instead of leaving `self.parser` to resolve by luck, and does not
    # touch the runtime MRO. `BaseTreeSitterParser` supplies all of it.
    if typing.TYPE_CHECKING:

        @property
        def language(self) -> typing.Any: ...
        @property
        def parser(self) -> typing.Any: ...
        @property
        def SCM_SKELETON_QUERY(self) -> str: ...
        @property
        def SCM_SYMBOL_QUERY(self) -> str: ...
        @property
        def SCM_COMMENT_QUERY(self) -> str: ...

        def _is_symbol_valid(
            self,
            sym_name: str,
            name_node: typing.Any | None,
            visibility: list[str] | None,
            decorator_filter: str | None,
            framework_markers: dict[str, typing.Any],
        ) -> bool: ...
        def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None: ...
        def _find_target_block(self, node: typing.Any) -> typing.Any | None: ...
        def _get_symbol_scope(self, name_node: typing.Any) -> str | None: ...
        def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]: ...

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
                    scope = self._get_symbol_scope(name_node)
                    full_name = f"{scope}.{sym_name}" if scope else sym_name
                    if self._is_symbol_valid(
                        full_name, name_node, visibility, decorator_filter, framework_markers
                    ):
                        symbols.append(full_name)

        seen = set()
        unique_symbols = []
        for x in symbols:
            if x not in seen:
                seen.add(x)
                unique_symbols.append(x)
        return unique_symbols

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
