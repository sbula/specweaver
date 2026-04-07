# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_rust
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.loom.commons.language.interfaces import CodeStructureError, CodeStructureInterface

logger = logging.getLogger(__name__)

SCM_SKELETON_QUERY = """
(function_item body: (block) @block)
"""

SCM_SYMBOL_QUERY = """
(struct_item name: (type_identifier) @name)
(impl_item type: (type_identifier) @name)
(impl_item type: (generic_type (type_identifier) @name))
(function_item name: (identifier) @name)
"""


class RustCodeStructure(CodeStructureInterface):
    def __init__(self) -> None:
        self.language = Language(tree_sitter_rust.language())
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

        collected_blocks: list[str] = []

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                    if node_name_str == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type == "generic_type":
                            parent = parent.parent
                        if parent and parent.type in ("function_item", "struct_item", "impl_item"):
                            collected_blocks.append(typing.cast("bytes", parent.text).decode("utf-8"))

        if collected_blocks:
            return "\n\n".join(collected_blocks)

        raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")

    def extract_symbol_body(self, code: str, symbol_name: str) -> str:
        symbol_code = self.extract_symbol(code, symbol_name)
        tree = self.parser.parse(symbol_code.encode("utf-8"))
        query = Query(self.language, SCM_SKELETON_QUERY)
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)

        if captures.get("block"):
            # Pick the largest block if there are multiple (to avoid nested class bodies parsing issue)
            # Actually, the first capture is usually the outermost block.
            return typing.cast("bytes", captures["block"][0].text).decode("utf-8")
        return ""


    def _is_symbol_public(self, parent: typing.Any) -> bool:
        if parent:
            for child in parent.children:
                if child.type == "visibility_modifier":
                    return True
        return False

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
                    if visibility and "public" in visibility and not self._is_symbol_public(name_node.parent):
                        continue
                    symbols.append(sym_name)

        seen = set()
        unique_symbols = []
        for x in symbols:
            if x not in seen:
                seen.add(x)
                unique_symbols.append(x)
        return unique_symbols

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
                        if parent and parent.type == "generic_type":
                            parent = parent.parent
                        if parent and parent.type in ("function_item", "struct_item", "impl_item"):
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
        mutated = code_bytes[:node.start_byte] + new_code.encode("utf-8") + code_bytes[node.end_byte:]
        return mutated.decode("utf-8")

    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace '{symbol_name}' in empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        target_block = None
        for child in node.children:
            if child.type == "block" or child.type == "declaration_list":
                target_block = child
                break

        if not target_block:
            raise CodeStructureError(f"Body block for symbol '{symbol_name}' not found.")
        mutated = code_bytes[:target_block.start_byte] + new_code.encode("utf-8") + code_bytes[target_block.end_byte:]
        return mutated.decode("utf-8")

    def delete_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            return code
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")
        mutated = code_bytes[:node.start_byte] + code_bytes[node.end_byte:]
        return mutated.decode("utf-8")

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        code_bytes = code.encode("utf-8")
        if not target_parent:
            if not code.endswith("\n"):
                return (code_bytes + b"\n\n" + new_code.encode("utf-8")).decode("utf-8")
            return (code_bytes + b"\n" + new_code.encode("utf-8")).decode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, target_parent)
        if not node:
            raise CodeStructureError(f"Parent symbol '{target_parent}' not found.")

        mutated = code_bytes[:node.end_byte] + b"\n" + new_code.encode("utf-8") + b"\n" + code_bytes[node.end_byte:]
        return mutated.decode("utf-8")
