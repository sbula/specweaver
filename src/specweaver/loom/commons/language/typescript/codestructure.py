# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_typescript
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.loom.commons.language.interfaces import CodeStructureError, CodeStructureInterface

logger = logging.getLogger(__name__)

SCM_SKELETON_QUERY = """
(function_declaration body: (statement_block) @block)
(method_definition body: (statement_block) @block)
(arrow_function body: (statement_block) @block)
"""

SCM_SYMBOL_QUERY = """
(function_declaration name: (identifier) @name)
(method_definition name: (property_identifier) @name)
(class_declaration name: (type_identifier) @name)
(variable_declarator name: (identifier) @name value: (arrow_function))
"""


class TypeScriptCodeStructure(CodeStructureInterface):
    def __init__(self) -> None:
        self.language = Language(tree_sitter_typescript.language_typescript())
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

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                    if node_name_str == symbol_name:
                        parent = name_node.parent
                        if parent and parent.type in ("function_declaration", "method_definition", "class_declaration", "variable_declarator"):
                            wrapper = parent
                            if wrapper.type == "variable_declarator" and wrapper.parent and wrapper.parent.type == "lexical_declaration":
                                wrapper = wrapper.parent
                            if wrapper.parent and wrapper.parent.type == "export_statement":
                                wrapper = wrapper.parent
                            return typing.cast("bytes", wrapper.text).decode("utf-8")

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
        while parent:
            if parent.type == "export_statement":
                return True
            parent = parent.parent
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
                        if parent and parent.type in ("function_declaration", "method_definition", "class_declaration", "variable_declarator"):
                            wrapper = parent
                            if wrapper.type == "variable_declarator" and wrapper.parent and wrapper.parent.type == "lexical_declaration":
                                wrapper = wrapper.parent
                            if wrapper.parent and wrapper.parent.type == "export_statement":
                                wrapper = wrapper.parent
                            return wrapper
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

    def _search_declarator(self, child: typing.Any) -> typing.Any | None:
        for sub2 in child.children:
            if sub2.type == "arrow_function":
                for sub3 in sub2.children:
                    if sub3.type == "statement_block":
                        return sub3
        return None

    def _extract_arrow_block(self, child: typing.Any) -> typing.Any | None:
        if child.type == "variable_declarator":
            res = self._search_declarator(child)
            if res:
                return res
        elif child.type == "arrow_function":
            for sub3 in child.children:
                if sub3.type == "statement_block":
                    return sub3
        # recursive search for nested variable bounds
        for sub in child.children:
            res = self._extract_arrow_block(sub)
            if res:
                return res
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        for child in node.children:
            if child.type == "statement_block" or child.type == "class_body":
                return child
            elif child.type == "lexical_declaration" or child.type == "variable_declarator":
                res = self._extract_arrow_block(child)
                if res:
                    return res
        return None

    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace '{symbol_name}' in empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        target_block = self._find_target_block(node)

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
