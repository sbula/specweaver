# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_java
from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
from specweaver.workspace.ast.parsers.tiers import ClassBasedParser

logger = logging.getLogger(__name__)


class JavaCodeStructure(ClassBasedParser):
    grammar = staticmethod(tree_sitter_java.language)

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (method_declaration body: (block) @block)
        (constructor_declaration body: (constructor_body) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return """
        (import_declaration) @imp
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (method_declaration name: (identifier) @name)
        (class_declaration name: (identifier) @name)
        (interface_declaration name: (identifier) @name)
        (enum_declaration name: (identifier) @name)
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (line_comment) @comment
        (block_comment) @comment
        """

    def _is_symbol_hidden(self, parent: typing.Any) -> bool:
        """Java is package-private by default, so anything without `public` is hidden."""
        if parent and parent.type in (
            "class_declaration",
            "method_declaration",
            "interface_declaration",
            "enum_declaration",
        ):
            for child in parent.children:
                if child.type == "modifiers" and child.text and b"public" in child.text:
                    return False
        return True

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        if not name_node.parent:
            return None
        parent = name_node.parent.parent
        while parent:
            if parent.type in ("class_declaration", "interface_declaration", "enum_declaration"):
                for child in parent.children:
                    if child.type == "identifier":
                        return typing.cast("bytes", child.text).decode("utf-8")
            parent = parent.parent
        return None

    #: Declaration nodes a Java identifier may belong to.
    _DECLARATION_TYPES = (
        "method_declaration",
        "class_declaration",
        "interface_declaration",
        "enum_declaration",
    )

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope, target_name = self._split_scope(symbol_name)

        for name_node in self._named_nodes(tree, target_name):
            if self._get_symbol_scope(name_node) != target_scope:
                continue
            parent = name_node.parent
            if parent and parent.type in self._DECLARATION_TYPES:
                return parent
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        for child in node.children:
            if child.type in ("block", "class_body", "interface_body", "enum_body"):
                return child
        return None

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, self.SCM_IMPORT_QUERY)
        # Everything in the statement except its syntax IS the imported name.
        return sorted(
            {
                self._extract_marker_text(child)
                for _, match_dict in QueryCursor(query).matches(tree.root_node)
                for node in match_dict.get("imp", [])
                for child in node.children
                if child.type not in ("import", "static", ";")
            }
        )

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        bases = []
        for child in target_node.children:
            if child.type == "superclass":
                if len(child.children) >= 2:
                    bases.append(self._extract_marker_text(child.children[1]))
            elif child.type == "super_interfaces" and len(child.children) >= 2:
                type_list_node = child.children[1]
                for t in type_list_node.children:
                    if t.type != ",":
                        bases.append(self._extract_marker_text(t))
        return bases

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        """Annotation names on a declaration, `@` stripped, first occurrence order preserved."""
        modifiers = next(self._children_of_type(target_node, "modifiers"), None)
        if modifiers is None:
            return []

        decorators: list[str] = []
        for mod in self._children_of_type(modifiers, "marker_annotation", "annotation"):
            name = self._extract_marker_text(mod).removeprefix("@")
            if name not in decorators:
                decorators.append(name)
        return decorators

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        if not code.strip():
            return {}
        tree = self.parser.parse(code.encode("utf-8"))
        query_str = "(class_declaration name: (identifier) @name) @cls\n(method_declaration name: (identifier) @name) @fn"
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

        target_block = None
        for child in node.children:
            if child.type in ("class_body", "interface_body", "enum_body", "block"):
                target_block = child
                break

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
        return ["*.class", "*.jar", "*.ear", "*.war"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["target/", "build/"]
