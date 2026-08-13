# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python CodeStructure parser for extracting exact code symbol skeletons."""

from __future__ import annotations

import logging
import typing

import tree_sitter_python
from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
from specweaver.workspace.ast.parsers.tiers import ClassBasedParser

logger = logging.getLogger(__name__)


class PythonCodeStructure(ClassBasedParser):
    """Python tree-sitter structural parser."""

    grammar = staticmethod(tree_sitter_python.language)

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (function_definition
          body: (block) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return """
        (import_statement) @imp
        (import_from_statement) @imp
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (function_definition name: (identifier) @name)
        (class_definition name: (identifier) @name)
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (comment) @comment
        """

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
            and sym_name.split(".")[-1].startswith("_")
            and not sym_name.split(".")[-1].startswith("__")
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
            if parent.type == "class_definition":
                for child in parent.children:
                    if child.type == "identifier":
                        return typing.cast("bytes", child.text).decode("utf-8")
            parent = parent.parent
        return None

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope, target_name = self._split_scope(symbol_name)

        for name_node in self._named_nodes(tree, target_name):
            if self._get_symbol_scope(name_node) != target_scope:
                continue
            parent = name_node.parent
            if not (parent and parent.type in ("function_definition", "class_definition")):
                continue
            # A decorated definition owns the decorators, so the extracted span must start there.
            if parent.parent and parent.parent.type == "decorated_definition":
                return parent.parent
            return parent
        return None

    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    node = child
                    break
        for child in node.children:
            if child.type == "block":
                return child
        return None

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        indented_code = self._auto_indent(new_code, margin + 4).encode("utf-8")
        start_byte = typing.cast("int", target_block.start_byte)
        end_byte = typing.cast("int", target_block.end_byte)
        return code_bytes[:start_byte] + indented_code + code_bytes[end_byte:]

    def _process_import_node(self, node: typing.Any, imports: set[str]) -> None:
        """Record the module an import statement names.

        `import a.b` and `import a.b as c` both contribute `a.b`; `from a.b import x` contributes
        `a.b` only — the FIRST dotted_name, since the imported names are dotted_names too.
        """
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "dotted_name":
                    imports.add(self._extract_marker_text(child))
                elif child.type == "aliased_import":
                    for aliased in self._children_of_type(child, "dotted_name"):
                        imports.add(self._extract_marker_text(aliased))
                        break
        elif node.type == "import_from_statement":
            for child in self._children_of_type(node, "dotted_name"):
                imports.add(self._extract_marker_text(child))
                break

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        query = Query(self.language, self.SCM_IMPORT_QUERY)
        cursor = QueryCursor(query)
        matches = cursor.matches(tree.root_node)

        imports: set[str] = set()
        for _, match_dict in matches:
            if "imp" in match_dict:
                for node in match_dict["imp"]:
                    self._process_import_node(node, imports)
        return sorted(list(imports))

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

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.pyc", "*.pyo", "*.pyd"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["__pycache__/", ".pytest_cache/", ".tox/", ".venv/"]
