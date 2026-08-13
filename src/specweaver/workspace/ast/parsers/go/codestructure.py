# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Go CodeStructure parser for extracting exact code symbol skeletons."""

from __future__ import annotations

import logging
import typing

import tree_sitter_go
from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers.tiers import FunctionBasedParser

logger = logging.getLogger(__name__)


class GoCodeStructure(FunctionBasedParser):
    """Go tree-sitter structural parser."""

    grammar = staticmethod(tree_sitter_go.language)

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration body: (block) @block)
        (method_declaration body: (block) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return """
        (import_declaration) @imp
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration name: (identifier) @name)
        (method_declaration name: (field_identifier) @name)
        (type_declaration (type_spec name: (type_identifier) @name))
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (comment) @comment
        """

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        """The receiver type of a Go method, which is the scope its name lives in.

        `func (s *Server) Handle()` scopes `Handle` to `Server` — the pointer star is dropped so
        value and pointer receivers name the same scope.
        """
        parent = name_node.parent
        if not (parent and parent.type == "method_declaration"):
            return None

        for params in self._children_of_type(parent, "parameter_list"):
            for param in self._children_of_type(params, "parameter_declaration"):
                for type_node in self._children_of_type(param, "type_identifier", "pointer_type"):
                    return self._text_of(type_node).replace("*", "")
        return None

    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        if decorator_filter:
            return False  # Go does not have decorators

        if visibility and "public" in visibility:
            # In Go, public symbols start with an uppercase letter
            short_name = sym_name.split(".")[-1]
            if short_name and not short_name[0].isupper():
                return False

        return True

    def _resolve_symbol_parent(self, name_node: typing.Any) -> typing.Any | None:
        parent = name_node.parent
        if parent and parent.type in ("function_declaration", "method_declaration"):
            return parent
        if parent and parent.type == "type_spec":
            type_decl = parent.parent
            if type_decl:
                for child in type_decl.children:
                    if child.type == "(":
                        return parent  # it is grouped, return type_spec
            return type_decl  # not grouped, return type_declaration wrapper
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
            if "name" not in match_dict:
                continue
            for name_node in match_dict["name"]:
                node_name_str = typing.cast("bytes", name_node.text).decode("utf-8")
                if (
                    node_name_str == target_name
                    and self._get_symbol_scope(name_node) == target_scope
                ):
                    resolved = self._resolve_symbol_parent(name_node)
                    if resolved:
                        return resolved
        return None

    def _find_type_body(self, node: typing.Any) -> typing.Any | None:
        for child in node.children:
            if child.type in ("struct_type", "interface_type"):
                return child
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        """The body a symbol's edits apply to: a type's field list, else the function block."""
        specs = (
            [node] if node.type == "type_spec" else list(self._children_of_type(node, "type_spec"))
        )
        if node.type in ("type_declaration", "type_spec"):
            for spec in specs:
                body = self._find_type_body(spec)
                if body:
                    return body

        return next(self._children_of_type(node, "block"), None)

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        start_byte = typing.cast("int", target_block.start_byte) + 1
        end_byte = typing.cast("int", target_block.end_byte) - 1

        if target_block.type in ("struct_type", "interface_type"):
            for child in target_block.children:
                if child.type == "{":
                    start_byte = typing.cast("int", child.end_byte)
                elif child.type == "}":
                    end_byte = typing.cast("int", child.start_byte)

        indented_code = self._auto_indent(new_code, margin + 4)
        if not indented_code.startswith("\n"):
            indented_code = "\n" + indented_code
        if not indented_code.endswith("\n"):
            indented_code += "\n" + (" " * margin)

        return code_bytes[:start_byte] + indented_code.encode("utf-8") + code_bytes[end_byte:]

    def _process_import_node(self, imp_node: typing.Any, imports: set[str]) -> None:
        """Record every quoted import path, whether grouped in a block or written singly."""
        specs: list[typing.Any] = list(self._children_of_type(imp_node, "import_spec"))
        for spec_list in self._children_of_type(imp_node, "import_spec_list"):
            specs.extend(self._children_of_type(spec_list, "import_spec"))

        for spec in specs:
            for path_node in self._children_of_type(spec, "interpreted_string_literal"):
                imports.add(self._text_of(path_node).strip('"'))

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, self.SCM_IMPORT_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        imports: set[str] = set()
        for _, match_dict in matches:
            if "imp" in match_dict:
                for imp_node in match_dict["imp"]:
                    self._process_import_node(imp_node, imports)
        return sorted(list(imports))

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        # Go lacks decorators/annotations, return empty structures
        return {}

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
        return ["visibility"]

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        code_bytes = code.encode("utf-8")
        indented_code = self._auto_indent(new_code, 0).encode("utf-8")

        # In Go, methods are defined at the top level, not nested in structs.
        # So target_parent doesn't structurally nest the new code like Python classes do.
        # It's essentially just an append. We will always append at the bottom.
        if not code.endswith("\n"):
            return (code_bytes + b"\n\n" + indented_code).decode("utf-8")
        return (code_bytes + b"\n" + indented_code).decode("utf-8")

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.a", "*.o", "*.so", "*.exe", "*.dll"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["vendor/", "bin/", "pkg/"]
