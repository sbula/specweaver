# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Markdown CodeStructure parser for extracting semantic structures like Headers."""

import tree_sitter_markdown
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.commons import json
from specweaver.workspace.parsers.interfaces import (
    CodeStructureError,
    CodeStructureInterface,
)

SCM_SKELETON_QUERY = """
(atx_heading (atx_h1_marker) heading_content: (_) @h1)
(atx_heading (atx_h2_marker) heading_content: (_) @h2)
(atx_heading (atx_h3_marker) heading_content: (_) @h3)
"""


class MarkdownCodeStructure(CodeStructureInterface):
    """Markdown tree-sitter structural parser."""

    def __init__(self) -> None:
        self.language = Language(tree_sitter_markdown.language())
        self.parser = Parser(self.language)

    def extract_skeleton(self, code: str) -> str:
        if not code.strip():
            return "{}"

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        query = Query(self.language, SCM_SKELETON_QUERY)
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)

        skeleton: dict[str, list[str]] = {"h1": [], "h2": [], "h3": []}

        for node_type in ["h1", "h2", "h3"]:
            if node_type in captures:
                for node in captures[node_type]:
                    header_text = node.text.decode("utf-8").strip() if node.text else ""
                    skeleton[node_type].append(header_text)

        return json.dumps(skeleton)

    def extract_symbol(self, code: str, symbol_name: str) -> str:
        raise CodeStructureError("Markdown extraction logic for symbols is not yet implemented.")

    def extract_symbol_body(self, code: str, symbol_name: str) -> str:
        raise CodeStructureError("Markdown extraction logic for symbols is not yet implemented.")

    def list_symbols(
        self, code: str, visibility: list[str] | None = None, decorator_filter: str | None = None
    ) -> list[str]:
        return []

    def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:
        raise CodeStructureError("Markdown mutators not implemented.")

    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        raise CodeStructureError("Markdown mutators not implemented.")

    def delete_symbol(self, code: str, symbol_name: str) -> str:
        raise CodeStructureError("Markdown mutators not implemented.")

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        raise CodeStructureError("Markdown mutators not implemented.")

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        return {}

    def extract_imports(self, code: str) -> list[str]:
        return []

    def get_binary_ignore_patterns(self) -> list[str]:
        return []

    def get_default_directory_ignores(self) -> list[str]:
        return []
