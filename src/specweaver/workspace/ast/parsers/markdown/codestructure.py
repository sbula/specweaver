# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Markdown CodeStructure parser for extracting semantic structures like Headers."""

from __future__ import annotations

import logging
import typing

import tree_sitter_markdown
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.ast.parsers.base import BaseTreeSitterParser
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

logger = logging.getLogger(__name__)


class MarkdownCodeStructure(BaseTreeSitterParser):
    """Markdown tree-sitter structural parser."""

    def __init__(self) -> None:
        self._language = Language(tree_sitter_markdown.language())
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
        (paragraph) @block
        (list) @block
        (fenced_code_block) @block
        (indented_code_block) @block
        (block_quote) @block
        (html_block) @block
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return ""

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return "(section (atx_heading heading_content: (inline) @name)) @block"

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return "(html_block) @comment"

    def supported_intents(self) -> list[str]:
        return [
            "skeleton",
            "symbol",
            "symbol_body",
            "list",
            "replace",
            "replace_body",
            "add",
            "delete",
            "traceability",
            "imports",
        ]

    def supported_parameters(self) -> list[str]:
        return []

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        return {}

    def extract_imports(self, code: str) -> list[str]:
        return []

    def get_binary_ignore_patterns(self) -> list[str]:
        return []

    def get_default_directory_ignores(self) -> list[str]:
        return []

    def extract_traceability_tags(self, code: str) -> set[str]:
        return set()

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        if not code.strip():
            return new_code
        if target_parent:
            raise CodeStructureError("Markdown does not support injecting into target_parent.")

        prefix = code
        if not prefix.endswith("\n\n"):
            if prefix.endswith("\n"):
                prefix += "\n"
            else:
                prefix += "\n\n"

        return prefix + new_code

    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        return True

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        if not name_node.parent:
            return None
        section_node = name_node.parent.parent
        if not section_node or section_node.type != "section":
            return None
        scopes: list[str] = []
        parent_section = section_node.parent
        while parent_section and parent_section.type == "section":
            for child in parent_section.children:
                if child.type == "atx_heading":
                    for gc in child.children:
                        if gc.type == "inline":
                            scopes.insert(0, typing.cast("bytes", gc.text).decode("utf-8").strip())
            parent_section = parent_section.parent

        if scopes:
            return ".".join(scopes)
        return None

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope = None
        target_name = symbol_name
        if "." in symbol_name:
            target_scope, target_name = symbol_name.rsplit(".", 1)

        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)
        for _match_id, match_dict in matches:
            if "name" in match_dict and "block" in match_dict:
                for name_node, block_node in zip(
                    match_dict["name"], match_dict["block"], strict=False
                ):
                    if typing.cast("bytes", name_node.text).decode("utf-8").strip() == target_name:
                        scope = self._get_symbol_scope(name_node)
                        if scope == target_scope:
                            return block_node
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        heading_node = None
        for child in node.children:
            if child.type == "atx_heading":
                heading_node = child
                break

        if not heading_node:
            return None

        start_byte = typing.cast("int", heading_node.end_byte)
        end_byte = typing.cast("int", node.end_byte)
        node_text = typing.cast("bytes", node.text)

        offset = start_byte - typing.cast("int", node.start_byte)
        text = node_text[offset:]

        class MarkdownBodyBlock:
            def __init__(self, s: int, e: int, t: bytes):
                self.start_byte = s
                self.end_byte = e
                self.text = t
                self.start_point = (0, 0)

        return MarkdownBodyBlock(start_byte, end_byte, text)

    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)

        prefix = code_bytes[:start_byte]
        suffix = code_bytes[end_byte:]

        return prefix + new_code.encode("utf-8") + suffix

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        start_byte = typing.cast("int", target_block.start_byte)
        end_byte = typing.cast("int", target_block.end_byte)

        prefix = code_bytes[:start_byte]
        suffix = code_bytes[end_byte:]

        if not prefix.endswith(b"\n"):
            new_code = "\n" + new_code

        return prefix + new_code.encode("utf-8") + suffix
