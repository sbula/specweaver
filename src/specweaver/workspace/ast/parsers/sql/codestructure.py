# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SQL CodeStructure parser for extracting exact code symbol skeletons."""

from __future__ import annotations

import logging
import typing

import tree_sitter_sql
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.ast.parsers.base import BaseTreeSitterParser

logger = logging.getLogger(__name__)


class SqlCodeStructure(BaseTreeSitterParser):
    """SQL tree-sitter structural parser."""

    def __init__(self) -> None:
        self._language = Language(tree_sitter_sql.language())
        self._parser = Parser(self._language)

    @property
    def language(self) -> Language:
        return self._language

    @property
    def parser(self) -> Parser:
        return self._parser

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (create_table (column_definitions) @block)
        (create_view (create_query) @block)
        (create_function (function_body) @block)
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (create_table (object_reference (identifier) @name))
        (create_view (object_reference (identifier) @name))
        (create_function (object_reference (identifier) @name))
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        """

    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        return True

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    if typing.cast("bytes", name_node.text).decode("utf-8") == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type == "object_reference":
                            return parent.parent
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        return None

    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")
        return code_bytes[:start_byte] + indented_code + code_bytes[end_byte:]

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        return code_bytes

    def extract_imports(self, code: str) -> list[str]:
        return []

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        return {}

    def supported_intents(self) -> list[str]:
        return [
            "skeleton", "symbol", "symbol_body", "list", "replace",
            "replace_body", "add", "delete", "traceability"
        ]

    def supported_parameters(self) -> list[str]:
        return []

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.sqlite", "*.db", "*.mdf", "*.ldf"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["data/", "migrations/"]

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        code_bytes = code.encode("utf-8")
        indented_code = self._auto_indent(new_code, 0).encode("utf-8")
        if not code.endswith("\n"):
            return (code_bytes + b"\n\n" + indented_code).decode("utf-8")
        return (code_bytes + b"\n" + indented_code).decode("utf-8")
