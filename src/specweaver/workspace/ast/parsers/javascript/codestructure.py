# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""JavaScript: the TypeScript parser on the JavaScript grammar, with queries that grammar has.

JavaScript names a class with `identifier`, where TypeScript uses `type_identifier`, has no
interfaces, enums or abstract classes, and marks a private member with `#`; every query naming
those is replaced here. No resolver renames JavaScript, so it offers no rename, remove or move.
"""

from __future__ import annotations

import typing

import tree_sitter_javascript

from specweaver.workspace.ast.parsers import _ref_tools
from specweaver.workspace.ast.parsers import _visibility as _vis
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError
from specweaver.workspace.ast.parsers.tiers import ClassBasedParser, enclosing_name
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

if typing.TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import Visibility


def _visibility_of(name_node: typing.Any) -> Visibility:
    """`#name` is private to its class; otherwise `export` makes a symbol public."""
    if name_node.type == "private_property_identifier":
        return "private"
    return "public" if _vis.has_ancestor(name_node.parent, "export_statement") else "internal"


def _supertypes_of(node: typing.Any) -> dict[str, list[str]]:
    """JavaScript's `class_heritage` holds `extends` and one expression; there is no `implements`."""
    heritage = next((c for c in node.children if c.type == "class_heritage"), None)
    names = [
        typing.cast("bytes", c.text).decode("utf-8")
        for c in (heritage.children if heritage else ())
        if c.type in ("identifier", "member_expression")
    ]
    return {"extends": names, "implements": []}


class JavaScriptCodeStructure(TypeScriptCodeStructure, ClassBasedParser):
    grammar = staticmethod(tree_sitter_javascript.language)
    _get_symbol_visibility = staticmethod(_visibility_of)
    _supertypes_of = staticmethod(_supertypes_of)

    #: ES imports and re-exports, `require("m")` and `import("m")`, each with a literal name.
    SCM_IMPORT_QUERY = """
        (import_statement source: (string (string_fragment) @imp))
        (export_statement source: (string (string_fragment) @imp))
        (call_expression
          function: (identifier) @fn
          arguments: (arguments . (string (string_fragment) @imp) .)
          (#eq? @fn "require"))
        (call_expression
          function: (import)
          arguments: (arguments . (string (string_fragment) @imp)))
    """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:
        return """
        (function_declaration name: (identifier) @name)
        (method_definition name: (property_identifier) @name)
        (method_definition name: (private_property_identifier) @name)
        (class_declaration name: (identifier) @name)
        (variable_declarator name: (identifier) @name value: (arrow_function))
        """

    SCM_FRAMEWORK_QUERY = "(class_declaration name: (identifier) @name) @cls\n(method_definition name: (property_identifier) @name) @fn\n(function_declaration name: (identifier) @name) @fn"

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        return enclosing_name(name_node, ("class_declaration",), "identifier")

    @property
    def SCM_SKELETON_QUERY(self) -> str:
        return """
        (function_declaration body: (statement_block) @block)
        (method_definition body: (statement_block) @block)
        (arrow_function body: (statement_block) @block)
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:
        return "(comment) @comment"

    def _finder(self) -> typing.Any:
        raise CodeStructureError("renaming is not supported for JavaScript")

    def supported_intents(self) -> list[str]:
        # Past `Renames`, whose list adds rename, remove and move.
        return super(_ref_tools.Renames, self).supported_intents()

    def extract_imports(self, code: str) -> list[str]:
        return sorted(
            {self._text_of(node) for node in self._import_nodes(code, self.SCM_IMPORT_QUERY)}
        )

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        """As TypeScript: the class body and the statement block have the same shape here."""
        return super().add_symbol(code, target_parent, new_code)

    def get_binary_ignore_patterns(self) -> list[str]:
        return []

    def get_default_directory_ignores(self) -> list[str]:
        return ["node_modules/", "dist/", "build/", "out/", "coverage/"]
