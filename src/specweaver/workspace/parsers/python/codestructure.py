# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python CodeStructure parser for extracting exact code symbol skeletons."""

from __future__ import annotations

import logging
import typing

import tree_sitter_python
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.parsers.interfaces import (
    CodeStructureError,
    CodeStructureInterface,
)

logger = logging.getLogger(__name__)

SCM_SKELETON_QUERY = """
(function_definition
  body: (block) @block)
"""

SCM_IMPORT_QUERY = """
(import_statement) @imp
(import_from_statement) @imp
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

    def _process_import_node(self, node: typing.Any, imports: set[str]) -> None:
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.add(self._extract_marker_text(child))
                elif child.type == "aliased_import":
                    for grandchild in child.children:
                        if grandchild.type == "dotted_name":
                            imports.add(self._extract_marker_text(grandchild))
                            break
        elif node.type == "import_from_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.add(self._extract_marker_text(child))
                    break

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        query = Query(self.language, SCM_IMPORT_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        imports: set[str] = set()
        for _, match_dict in matches:
            if "imp" in match_dict:
                for node in match_dict["imp"]:
                    self._process_import_node(node, imports)
        return sorted(list(imports))

    def _is_symbol_valid(
        self,
        sym_name: str,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        if (
            visibility
            and "public" in visibility
            and sym_name.startswith("_")
            and not sym_name.startswith("__")
        ):
            return False

        if decorator_filter:
            decs = framework_markers.get(sym_name, {}).get("decorators", [])
            if not any(decorator_filter in d for d in decs):
                return False

        return True

    def list_symbols(
        self, code: str, visibility: list[str] | None = None, decorator_filter: str | None = None
    ) -> list[str]:
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
                    if self._is_symbol_valid(sym_name, visibility, decorator_filter, framework_markers):
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
                    padded.append(line)  # preserve empty lines
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

        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")

        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
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

        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        mutated = code_bytes[:start_byte] + code_bytes[end_byte:]
        return mutated.decode("utf-8")

    def _extract_marker_text(self, node: typing.Any) -> str:
        return typing.cast("bytes", node.text).decode("utf-8").strip()

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        bases = []
        for child in target_node.children:
            if child.type == "argument_list":
                for arg_child in child.children:
                    if arg_child.type in ("identifier", "attribute"):
                        bases.append(self._extract_marker_text(arg_child))
        return bases

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        decorators = []
        parent = target_node.parent
        if parent and parent.type == "decorated_definition":
            for child in parent.children:
                if child.type == "decorator":
                    dec_text = self._extract_marker_text(child)
                    if dec_text.startswith("@"):
                        dec_text = dec_text[1:]
                    if dec_text not in decorators:
                        decorators.append(dec_text)
        return decorators

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        if not code.strip():
            return {}
        tree = self.parser.parse(code.encode("utf-8"))
        query_str = "(class_definition name: (identifier) @name) @cls\n(function_definition name: (identifier) @name) @fn"
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
        end_byte = typing.cast("int", node.end_byte)
        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")

        mutated = (
            code_bytes[:end_byte]
            + b"\n"
            + (b" " * (margin + 4))
            + indented_code
            + b"\n"
            + code_bytes[end_byte:]
        )
        return mutated.decode("utf-8")
