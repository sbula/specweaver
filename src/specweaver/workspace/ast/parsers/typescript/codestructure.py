# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_typescript
from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
from specweaver.workspace.ast.parsers.tiers import ClassBasedParser

logger = logging.getLogger(__name__)


class TypeScriptCodeStructure(ClassBasedParser):
    grammar = staticmethod(tree_sitter_typescript.language_typescript)

    TYPE_DECLARATION_NODES: typing.ClassVar[tuple[str, ...]] = ("class_declaration",)

    def _supertypes_of(self, node: typing.Any) -> dict[str, list[str]]:
        """TypeScript wraps both clauses in `class_heritage`, and keeps them distinct inside it."""
        heritage = next((c for c in node.children if c.type == "class_heritage"), None)
        clauses = {c.type: c for c in (heritage.children if heritage else ())}
        return {
            "extends": self._type_names_in(clauses.get("extends_clause")),
            "implements": self._type_names_in(clauses.get("implements_clause")),
        }

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration body: (statement_block) @block)
        (method_definition body: (statement_block) @block)
        (arrow_function body: (statement_block) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        return """
        (import_statement) @imp
        (import_require_clause) @imp
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration name: (identifier) @name)
        (method_definition name: (property_identifier) @name)
        (class_declaration name: (type_identifier) @name)
        (variable_declarator name: (identifier) @name value: (arrow_function))
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        (comment) @comment
        """

    def _is_symbol_hidden(self, parent: typing.Any) -> bool:
        """A TypeScript declaration is module-local unless some ancestor exports it."""
        while parent:
            if parent.type == "export_statement":
                return False
            parent = parent.parent
        return True

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        if not name_node.parent:
            return None
        parent = name_node.parent.parent
        while parent:
            if parent.type == "class_declaration":
                for child in parent.children:
                    if child.type == "type_identifier":
                        return typing.cast("bytes", child.text).decode("utf-8")
            parent = parent.parent
        return None

    #: Declaration nodes an identifier may belong to. A `variable_declarator` counts because
    #: `const f = () => {}` declares a function without a `function_declaration`.
    _DECLARATION_TYPES = (
        "function_declaration",
        "method_definition",
        "class_declaration",
        "variable_declarator",
    )

    @classmethod
    def _declaration_wrapper(cls, name_node: typing.Any) -> typing.Any | None:
        """The declaration owning this identifier, widened outward to what the source exports.

        Two widenings, both load-bearing for the returned span: `const f = ...` reports the whole
        `lexical_declaration` rather than just the declarator, and an exported symbol reports the
        `export_statement` so the `export` keyword is inside the extracted skeleton.
        """
        parent = name_node.parent
        if not (parent and parent.type in cls._DECLARATION_TYPES):
            return None

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

    #: Class and function declarations this language exposes to the framework walk.
    SCM_FRAMEWORK_QUERY = "(class_declaration name: (type_identifier) @name) @cls\n(method_definition name: (property_identifier) @name) @fn\n(function_declaration name: (identifier) @name) @fn"

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope, target_name = self._split_scope(symbol_name)

        for name_node in self._named_nodes(tree, target_name):
            if self._get_symbol_scope(name_node) != target_scope:
                continue
            wrapper = self._declaration_wrapper(name_node)
            if wrapper is not None:
                return wrapper
        return None

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

    @staticmethod
    def _module_of(import_text: str) -> str:
        """The module an import statement names, stripped of syntax.

        Handles both spellings the query captures: `import x from "m"` and a bare
        `import "m"` / `require("m")`. Trailing semicolon and surrounding quotes come off last, so
        both paths converge on the same cleanup.
        """
        if " from " in import_text:
            module = import_text.split(" from ")[-1].strip()
        else:
            module = (
                import_text.replace("import ", "").replace("require(", "").replace(")", "").strip()
            )

        if module.endswith(";"):
            module = module[:-1].strip()
        if module.startswith(("'", '"')) and module.endswith(("'", '"')):
            module = module[1:-1]
        return module

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []

        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, self.SCM_IMPORT_QUERY)

        imports = {
            self._module_of(typing.cast("bytes", node.text).decode("utf-8").strip())
            for _, match_dict in QueryCursor(query).matches(tree.root_node)
            for node in match_dict.get("imp", [])
        }
        return sorted(imports)

    #: Nodes naming a base type directly, as opposed to holding a list of them.
    _BASE_NAME_TYPES = ("identifier", "type_identifier")

    def _base_names_in(self, clause: typing.Any) -> list[str]:
        """Base types named by one extends/implements clause, flattening any `type_list`."""
        names = []
        for node in clause.children:
            if node.type in self._BASE_NAME_TYPES:
                names.append(self._extract_marker_text(node))
            elif node.type == "type_list":
                names.extend(
                    self._extract_marker_text(sub)
                    for sub in node.children
                    if sub.type in self._BASE_NAME_TYPES
                )
        return names

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        return [
            name
            for child in target_node.children
            if child.type == "class_heritage"
            for clause in child.children
            if clause.type in ("extends_clause", "implements_clause")
            for name in self._base_names_in(clause)
        ]

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
        return []

    def get_default_directory_ignores(self) -> list[str]:
        return ["node_modules/", "dist/", "build/", "out/"]
