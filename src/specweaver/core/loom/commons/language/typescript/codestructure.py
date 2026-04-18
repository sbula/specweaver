# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_typescript
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.core.loom.commons.language.interfaces import (
    CodeStructureError,
    CodeStructureInterface,
)

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
                        if parent and parent.type in (
                            "function_declaration",
                            "method_definition",
                            "class_declaration",
                            "variable_declarator",
                        ):
                            wrapper = parent
                            if (
                                wrapper.type == "variable_declarator"
                                and wrapper.parent
                                and wrapper.parent.type == "lexical_declaration"
                            ):
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

    def list_symbols(self, code: str, visibility: list[str] | None = None, decorator_filter: str | None = None) -> list[str]:
        if not code.strip():
            return []

        framework_markers = {}
        if decorator_filter:
            framework_markers = self.extract_framework_markers(code)

        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        symbols = []
        for _match_id, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    sym_name = typing.cast("bytes", name_node.text).decode("utf-8")

                    if (
                        visibility
                        and "public" in visibility
                        and not self._is_symbol_public(name_node.parent)
                    ):
                        continue

                    if decorator_filter:
                        decs = framework_markers.get(sym_name, {}).get("decorators", [])
                        if not any(decorator_filter in d for d in decs):
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
                        if parent and parent.type in (
                            "function_declaration",
                            "method_definition",
                            "class_declaration",
                            "variable_declarator",
                        ):
                            wrapper = parent
                            if (
                                wrapper.type == "variable_declarator"
                                and wrapper.parent
                                and wrapper.parent.type == "lexical_declaration"
                            ):
                                wrapper = wrapper.parent
                            if wrapper.parent and wrapper.parent.type == "export_statement":
                                wrapper = wrapper.parent
                            return wrapper
        return None

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

    def replace_symbol(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace '{symbol_name}' in empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")
        mutated = (
            code_bytes[: node.start_byte] + new_code.encode("utf-8") + code_bytes[node.end_byte :]
        )
        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")
        mutated = code_bytes[: node.start_byte] + indented_code + code_bytes[node.end_byte :]
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
        if node.type == "export_statement":
            for child in node.children:
                res = self._find_target_block(child)
                if res:
                    return res
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

        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")

        insert_start = target_block.start_byte + 1
        insert_end = target_block.end_byte - 1
        mutated = (
            code_bytes[:insert_start]
            + b"\n"
            + (b" " * (margin + 4))
            + indented_code
            + b"\n"
            + (b" " * margin)
            + code_bytes[insert_end:]
        )
        return mutated.decode("utf-8")

    def delete_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            return code
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")
        mutated = code_bytes[: node.start_byte] + code_bytes[node.end_byte :]
        return mutated.decode("utf-8")

    def _extract_marker_text(self, node: typing.Any) -> str:
        return typing.cast("bytes", node.text).decode("utf-8").strip()

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        bases = []
        for child in target_node.children:
            if child.type == "class_heritage":
                for clause in child.children:
                    if clause.type in ("extends_clause", "implements_clause"):
                        for t in clause.children:
                            if t.type in ("identifier", "type_identifier"):
                                bases.append(self._extract_marker_text(t))
                            elif t.type == "type_list":
                                for sub in t.children:
                                    if sub.type in ("identifier", "type_identifier"):
                                        bases.append(self._extract_marker_text(sub))
        return bases

    def _add_dec(self, child: typing.Any, decorators: list[str]) -> None:
        dec_text = self._extract_marker_text(child)
        if dec_text.startswith("@"):
            dec_text = dec_text[1:]
        if dec_text not in decorators:
            decorators.append(dec_text)

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        decorators: list[str] = []
        parent = target_node.parent
        if parent and parent.type == "export_statement":
            target_node = parent

        for child in target_node.children:
            if child.type == "decorator":
                self._add_dec(child, decorators)

        if target_node.type == "method_definition":
            prev = target_node.prev_named_sibling
            temp: list[typing.Any] = []
            while prev and prev.type == "decorator":
                temp.insert(0, prev)
                prev = prev.prev_named_sibling
            for dec_node in temp:
                self._add_dec(dec_node, decorators)

        return decorators

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        if not code.strip():
            return {}
        tree = self.parser.parse(code.encode("utf-8"))
        query_str = "(class_declaration name: (type_identifier) @name) @cls\n(method_definition name: (property_identifier) @name) @fn\n(function_declaration name: (identifier) @name) @fn"
        cursor = QueryCursor(Query(self.language, query_str))

        markers: dict[str, dict[str, list[str]]] = {}
        for _, match_dict in cursor.matches(tree.root_node):
            if "name" not in match_dict:
                continue
            symbol = self._extract_marker_text(match_dict["name"][0])
            is_class = "cls" in match_dict
            target = match_dict["cls"][0] if is_class else match_dict["fn"][0]

            if symbol not in markers:
                markers[symbol] = {"decorators": self._extract_decorators(target)}
                if is_class:
                    markers[symbol]["extends"] = self._extract_bases(target)
        return markers

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        code_bytes = code.encode("utf-8")
        if not target_parent:
            indented_code = self._auto_indent(new_code, 0).encode("utf-8")
            if not code.endswith("\n"):
                return (code_bytes + b"\n\n" + indented_code).decode("utf-8")
            return (code_bytes + b"\n" + indented_code).decode("utf-8")

        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, target_parent)
        if not node:
            raise CodeStructureError(f"Parent symbol '{target_parent}' not found.")

        target_block = self._find_target_block(node)

        if not target_block:
            raise CodeStructureError(f"Body block for parent symbol '{target_parent}' not found.")

        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")

        insert_point = target_block.end_byte - 1
        mutated = (
            code_bytes[:insert_point]
            + (b" " * (margin + 4))
            + indented_code
            + b"\n"
            + (b" " * margin)
            + code_bytes[insert_point:]
        )
        return mutated.decode("utf-8")
