# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_kotlin
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.parsers.interfaces import (
    CodeStructureError,
    CodeStructureInterface,
)

logger = logging.getLogger(__name__)

SCM_SKELETON_QUERY = """
(function_declaration (function_body (block) @block))
(anonymous_initializer (block) @block)
"""

SCM_IMPORT_QUERY = """
(import_header) @imp
"""

SCM_SYMBOL_QUERY = """
(function_declaration (identifier) @name)
(class_declaration (identifier) @name)
(object_declaration (identifier) @name)
"""


SCM_COMMENT_QUERY = """
(line_comment) @comment
(block_comment) @comment
"""


class KotlinCodeStructure(CodeStructureInterface):
    def __init__(self) -> None:
        self.language = Language(tree_sitter_kotlin.language())
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
                            "class_declaration",
                            "object_declaration",
                        ):
                            return typing.cast("bytes", parent.text).decode("utf-8")

        raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")

    def extract_traceability_tags(self, code: str) -> set[str]:
        if not code.strip():
            return set()
        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, SCM_COMMENT_QUERY)
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

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        query = Query(self.language, SCM_IMPORT_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        imports = set()
        for _, match_dict in matches:
            if "imp" in match_dict:
                for node in match_dict["imp"]:
                    import_text = typing.cast("bytes", node.text).decode("utf-8").strip()
                    if import_text.startswith("import "):
                        import_text = import_text[7:].strip()
                    if " as " in import_text:
                        import_text = import_text.split(" as ")[0].strip()
                    imports.add(import_text)

        return sorted(list(imports))

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

    def _is_symbol_private(self, parent: typing.Any) -> bool:
        if parent:
            for child in parent.children:
                if child.type == "modifiers":
                    mod_text = child.text
                    if mod_text and (
                        b"private" in mod_text
                        or b"protected" in mod_text
                        or b"internal" in mod_text
                    ):
                        return True
        return False

    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        if visibility and "public" in visibility and self._is_symbol_private(name_node.parent):
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
                            "class_declaration",
                            "object_declaration",
                        ):
                            return parent
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

        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")

        mutated = code_bytes[: node.start_byte] + indented_code + code_bytes[node.end_byte :]
        return mutated.decode("utf-8")

    def replace_symbol_body(self, code: str, symbol_name: str, new_code: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot replace '{symbol_name}' in empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found.")

        # Kotlin bodies can be (function_body (block)) or (class_body)
        target_block = None
        for child in node.children:
            if child.type == "function_body":
                for sub in child.children:
                    if sub.type == "block":
                        target_block = sub
                        break
            elif child.type == "class_body":
                target_block = child

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
            if child.type == "delegation_specifiers":
                for specifier in child.children:
                    if specifier.type == "delegation_specifier":
                        for c in specifier.children:
                            if c.type == "user_type":
                                bases.append(self._extract_marker_text(c))
                            elif c.type == "constructor_invocation":
                                for cc in c.children:
                                    if cc.type == "user_type":
                                        bases.append(self._extract_marker_text(cc))
        return bases

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        decorators = []
        for child in target_node.children:
            if child.type == "modifiers":
                for mod in child.children:
                    if mod.type == "annotation":
                        dec_text = self._extract_marker_text(mod)
                        if dec_text.startswith("@"):
                            dec_text = dec_text[1:]
                        if dec_text not in decorators:
                            decorators.append(dec_text)
        return decorators

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        if not code.strip():
            return {}

        tree = self.parser.parse(code.encode("utf-8"))
        query_str = "(class_declaration name: (identifier) @name) @cls\n(function_declaration name: (identifier) @name) @fn\n(object_declaration name: (identifier) @name) @cls"
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

        target_block = None
        for child in node.children:
            if child.type == "function_body":
                for sub in child.children:
                    if sub.type == "block":
                        target_block = sub
                        break
            elif child.type == "class_body":
                target_block = child

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

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.class", "*.jar"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["target/", "build/", ".gradle/"]
