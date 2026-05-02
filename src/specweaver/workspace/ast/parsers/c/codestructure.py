# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tree-sitter CodeStructureInterface implementation for C."""

import typing

import tree_sitter_c
from tree_sitter import Language, Parser, Query

from specweaver.workspace.ast.parsers.base import BaseTreeSitterParser


class CCodeStructure(BaseTreeSitterParser):
    """AST parser for C source files."""

    def __init__(self) -> None:
        self._language = Language(tree_sitter_c.language())
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
        (function_definition body: (compound_statement) @block)
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (function_definition
          declarator: (function_declarator
            declarator: (identifier) @name)) @block

        (struct_specifier
          name: (type_identifier) @name) @block

        (enum_specifier
          name: (type_identifier) @name) @block

        (union_specifier
          name: (type_identifier) @name) @block
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (comment) @comment
        """

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

    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        # C does not support decorator filters in this MVP.
        if decorator_filter is not None:
            from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

            raise CodeStructureError("Decorator filtering is not supported in C parsers")
        # C does not have class visibility (public/private).
        return visibility is None

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        return None

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope = None
        target_name = symbol_name
        if "." in symbol_name:
            target_scope, target_name = symbol_name.split(".", 1)

        from tree_sitter import Query, QueryCursor

        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        cursor = QueryCursor(query)
        for _, match_dict in cursor.matches(tree.root_node):
            if "name" in match_dict:
                for name_node in match_dict["name"]:
                    if typing.cast("bytes", name_node.text).decode("utf-8") == target_name:
                        scope = self._get_symbol_scope(name_node)
                        if scope == target_scope:
                            return match_dict.get("block", [None])[0]
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        if node.type == "function_definition":
            return node.child_by_field_name("body")
        if node.type in ("struct_specifier", "union_specifier"):
            return node.child_by_field_name("body")
        if node.type == "enum_specifier":
            return node.child_by_field_name("body")
        return node

    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        start_byte = typing.cast("int", node.start_byte)
        end_byte = typing.cast("int", node.end_byte)
        new_code_bytes = new_code.encode("utf-8")
        return code_bytes[:start_byte] + new_code_bytes + code_bytes[end_byte:]

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        if target_block.type == "compound_statement":
            # Find the `{` and `}`
            start_byte = typing.cast("int", target_block.start_byte) + 1
            end_byte = typing.cast("int", target_block.end_byte) - 1
        elif target_block.type in ("field_declaration_list", "enumerator_list"):
            start_byte = typing.cast("int", target_block.start_byte) + 1
            end_byte = typing.cast("int", target_block.end_byte) - 1
        else:
            start_byte = typing.cast("int", target_block.start_byte)
            end_byte = typing.cast("int", target_block.end_byte)

        indented_code = self._auto_indent(new_code, margin + 4)
        if not indented_code.startswith("\n"):
            indented_code = "\n" + indented_code
        if not indented_code.endswith("\n"):
            indented_code += "\n" + (" " * margin)

        return code_bytes[:start_byte] + indented_code.encode("utf-8") + code_bytes[end_byte:]

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        return {}

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []
        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, "(preproc_include) @inc")
        from tree_sitter import QueryCursor

        cursor = QueryCursor(query)
        imports = []
        for _, match_dict in cursor.matches(tree.root_node):
            if "inc" in match_dict:
                for node in match_dict["inc"]:
                    imports.append(typing.cast("bytes", node.text).decode("utf-8").strip())

        seen = set()
        dedup = []
        for inc in imports:
            if inc not in seen:
                seen.add(inc)
                dedup.append(inc)
        return dedup

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.o", "*.so", "*.a", "*.dll", "*.exe", "*.obj", "*.dylib"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["build/", "out/", "bin/", "obj/", "cmake-build-*/"]

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        if not target_parent:
            return code + "\n\n" + new_code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        parent_node = self._find_symbol_node(tree, target_parent)
        if not parent_node:
            from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

            raise CodeStructureError(f"Target parent '{target_parent}' not found.")

        target_block = self._find_target_block(parent_node)
        if not target_block:
            from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

            raise CodeStructureError(f"Body block for symbol '{target_parent}' not found.")

        end_byte = typing.cast("int", target_block.end_byte) - 1
        margin = typing.cast("int", parent_node.start_point[1])
        indented_code = self._auto_indent(new_code, margin + 4)

        return (
            code_bytes[:end_byte]
            + b"\n"
            + indented_code.encode("utf-8")
            + b"\n"
            + code_bytes[end_byte:]
        ).decode("utf-8")
