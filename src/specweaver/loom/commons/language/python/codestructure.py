# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Python CodeStructure parser for extracting exact code symbol skeletons."""

from __future__ import annotations

import logging
import typing

import tree_sitter_python
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.loom.commons.language.interfaces import CodeStructureError, CodeStructureInterface

logger = logging.getLogger(__name__)

SCM_SKELETON_QUERY = """
(function_definition
  body: (block) @block)
"""

SCM_SYMBOL_QUERY = """
(function_definition name: (identifier) @name)
(class_definition name: (identifier) @name)
"""


class PythonCodeStructure(CodeStructureInterface):
    """Python tree-sitter structural parser."""

    def __init__(self) -> None:
        self.language = Language(tree_sitter_python.language())
        self.parser = Parser(self.language)

    def extract_skeleton(self, code: str) -> str:
        if not code.strip():
            return code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        query = Query(self.language, SCM_SKELETON_QUERY)
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)

        nodes_to_blank: list[tuple[int, int]] = []

        if "block" in captures:
            for node in captures["block"]:
                start_cut = node.start_byte + 1
                end_cut = node.end_byte - 1

                if node.children:
                    first_child = node.children[0]
                    if first_child.type == "expression_statement" and first_child.children and first_child.children[0].type == "string":
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

        query = Query(self.language, SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                    if node_name_str == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type in ("function_definition", "class_definition"):
                            if parent.parent and parent.parent.type == "decorated_definition":
                                return typing.cast("bytes", parent.parent.text).decode("utf-8")
                            return typing.cast("bytes", parent.text).decode("utf-8")

        raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")

    def extract_symbol_body(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot extract '{symbol_name}' from empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        query = Query(self.language, SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                    if node_name_str == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type in ("function_definition", "class_definition"):
                            for child in parent.children:
                                if child.type == "block":
                                    return typing.cast("bytes", child.text).decode("utf-8")
                            return ""

        raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")

    def list_symbols(self, code: str, visibility: list[str] | None = None) -> list[str]:
        if not code.strip():
            return []

        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        symbols = []
        for _match_id, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    sym_name = typing.cast("bytes", name_node.text).decode("utf-8")

                    if visibility and "public" in visibility and sym_name.startswith("_") and not sym_name.startswith("__"):
                        continue

                    symbols.append(sym_name)

        # distinct
        seen = set()

        unique_symbols = []
        for x in symbols:
            if x not in seen:
                seen.add(x)
                unique_symbols.append(x)
        return unique_symbols

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
                    padded.append(line) # preserve empty lines
                else:
                    padded.append((" " * margin) + line)
        return "\n".join(padded)

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        query = Query(self.language, SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                    if node_name_str == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type in ("function_definition", "class_definition"):
                            if parent.parent and parent.parent.type == "decorated_definition":
                                return parent.parent
                            return parent
        return None

    def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace '{symbol_name}' in empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)

        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        margin = typing.cast(int, node.start_point[1])
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")

        start_byte = typing.cast(int, node.start_byte)
        end_byte = typing.cast(int, node.end_byte)
        mutated = code_bytes[:start_byte] + indented_code + code_bytes[end_byte:]
        return mutated.decode("utf-8")

    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace body of '{symbol_name}' in empty code.")

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        # We need to find the block explicitly
        query = Query(self.language, SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        target_block = None
        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    if typing.cast("bytes", name_node.text).decode("utf-8") == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type in ("function_definition", "class_definition"):
                            for child in parent.children:
                                if child.type == "block":
                                    target_block = child
                                    break

        if not target_block:
            raise CodeStructureError(f"Body block for symbol '{symbol_name}' not found.")

        margin = target_block.start_point[1]
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")

        start_byte = target_block.start_byte
        end_byte = target_block.end_byte
        mutated = code_bytes[:start_byte] + indented_code + code_bytes[end_byte:]
        return mutated.decode("utf-8")

    def delete_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            return code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)

        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        start_byte = typing.cast(int, node.start_byte)
        end_byte = typing.cast(int, node.end_byte)
        mutated = code_bytes[:start_byte] + code_bytes[end_byte:]
        return mutated.decode("utf-8")

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        code_bytes = code.encode("utf-8")

        if not target_parent:
            # Append to EOF
            indented_code = self._auto_indent(new_code, 0).encode("utf-8")
            if not code.endswith("\n"):
                return (code_bytes + b"\n\n" + indented_code).decode("utf-8")
            return (code_bytes + b"\n" + indented_code).decode("utf-8")

        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, target_parent)

        if not node:
            raise CodeStructureError(f"Parent symbol '{target_parent}' not found.")

        # Target parent should be a class. Inject right before its end_byte.
        # But we need to indent inside it. Python body block standard indent is parent margin + 4.
        start_byte = typing.cast(int, node.start_byte)
        end_byte = typing.cast(int, node.end_byte)
        margin = typing.cast(int, node.start_point[1])
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")
        
        mutated = code_bytes[:end_byte] + b"\n" + (b" " * (margin + 4)) + indented_code + b"\n" + code_bytes[end_byte:]
        return mutated.decode("utf-8")
