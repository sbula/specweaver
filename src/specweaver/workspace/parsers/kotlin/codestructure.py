# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_kotlin
from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.parsers.base import BaseTreeSitterParser
from specweaver.workspace.parsers.interfaces import CodeStructureError

logger = logging.getLogger(__name__)


class KotlinCodeStructure(BaseTreeSitterParser):
    def __init__(self) -> None:
        self._language = Language(tree_sitter_kotlin.language())
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
        (function_declaration (function_body (block) @block))
        (anonymous_initializer (block) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return """
        (import_header) @imp
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration (identifier) @name)
        (class_declaration (identifier) @name)
        (object_declaration (identifier) @name)
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (line_comment) @comment
        (block_comment) @comment
        """

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
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        if (
            visibility
            and "public" in visibility
            and name_node
            and self._is_symbol_private(name_node.parent)
        ):
            return False

        if decorator_filter:
            decs = framework_markers.get(sym_name, {}).get("decorators", [])
            if not any(decorator_filter in d for d in decs):
                return False

        return True

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        if not name_node.parent:
            return None
        parent = name_node.parent.parent
        while parent:
            if parent.type in ("class_declaration", "object_declaration"):
                for child in parent.children:
                    if child.type == "identifier":
                        return typing.cast("bytes", child.text).decode("utf-8")
            parent = parent.parent
        return None

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope = None
        target_name = symbol_name
        if "." in symbol_name:
            target_scope, target_name = symbol_name.split(".", 1)

        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        for _, match_dict in matches:
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                    if node_name_str == target_name:
                        scope = self._get_symbol_scope(name_node)
                        if scope == target_scope:
                            parent = name_node.parent
                            if parent and parent.type in (
                                "function_declaration",
                                "class_declaration",
                                "object_declaration",
                            ):
                                return parent
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        for child in node.children:
            if child.type == "function_body":
                for sub in child.children:
                    if sub.type == "block":
                        return sub
            elif child.type == "class_body":
                return child
        return None

    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        margin = typing.cast("int", node.start_point[1])
        indented_code = self._auto_indent(new_code, margin).encode("utf-8")
        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        return code_bytes[:start_byte] + indented_code + code_bytes[end_byte:]

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")
        insert_start = target_block.start_byte + 1
        insert_end = target_block.end_byte - 1
        return (
            code_bytes[:insert_start]
            + b"\n"
            + (b" " * (margin + 4))
            + indented_code
            + b"\n"
            + (b" " * margin)
            + code_bytes[insert_end:]
        )

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        query = Query(self.language, self.SCM_IMPORT_QUERY)
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
            name_node = match_dict["name"][0]
            symbol = self._extract_marker_text(name_node)
            scope = self._get_symbol_scope(name_node)
            full_name = f"{scope}.{symbol}" if scope else symbol

            is_class = "cls" in match_dict
            target = match_dict["cls"][0] if is_class else match_dict["fn"][0]

            if full_name not in markers:
                markers[full_name] = {"decorators": self._extract_decorators(target)}
                if is_class:
                    markers[full_name]["extends"] = self._extract_bases(target)
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

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.class", "*.jar"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["target/", "build/", ".gradle/"]
