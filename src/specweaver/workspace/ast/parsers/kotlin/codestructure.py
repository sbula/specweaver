# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import typing

import tree_sitter_kotlin
from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers import _visibility as _vis
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError, Visibility
from specweaver.workspace.ast.parsers.tiers import ClassBasedParser

logger = logging.getLogger(__name__)


def _visibility_of(name_node: typing.Any) -> Visibility:
    """Kotlin is public by default and says the other three out loud, so no container check.

    `internal` is Kotlin's own word and means here what it means everywhere else in this
    vocabulary: visible inside this module, not outside it.
    """
    return _vis.keyword_level(name_node.parent, "modifiers", _vis.KOTLIN_ACCESS) or "public"


class KotlinCodeStructure(ClassBasedParser):
    grammar = staticmethod(tree_sitter_kotlin.language)
    _get_symbol_visibility = staticmethod(_visibility_of)

    TYPE_DECLARATION_NODES: typing.ClassVar[tuple[str, ...]] = ("class_declaration",)

    def _supertypes_of(self, node: typing.Any) -> dict[str, list[str]]:
        """Kotlin holds both kinds in one list, so every supertype is reported as extension.

        `class Impl : Base(), Runner` distinguishes them only by the constructor call on `Base`, and
        `by` delegation or a base with no explicit invocation breaks that convention. Settled with
        the user: report extension only rather than be right most of the time.
        """
        specifiers = next((c for c in node.children if c.type == "delegation_specifiers"), None)
        return {"extends": self._type_names_in(specifiers), "implements": []}

    # Held here because `tree-sitter-kotlin` ships no `.scm` of any kind. Original work, written
    # from the grammar by inspection.
    #
    # POSITIONAL, unavoidably: `call_expression` exposes no field names, so unlike every other
    # language here the pattern cannot state which child is the callee. The second line is
    # constrained to an identifier that FOLLOWS something — without that, `obj.deep()` matches the
    # receiver as well, because a receiver is an identifier too. `test_kotlin_call_query.py` pins
    # every shape so a grammar change surfaces as a red rather than as a thinner graph.
    TAGS_QUERY: typing.ClassVar[str | None] = """
        (call_expression (identifier) @name) @reference.call
        (call_expression (navigation_expression (_) (identifier) @name)) @reference.call
        """
    CALLER_SCOPE_NODES: typing.ClassVar[tuple[str, ...]] = (
        "class_declaration",
        "function_declaration",
    )

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (function_declaration (function_body (block) @block))
        (anonymous_initializer (block) @block)
        """

    @property
    def SCM_IMPORT_QUERY(self) -> str:  # noqa: N802
        #: The grammar emits `(import)`; `(import_header)` is Kotlin's own spec vocabulary and not a
        #: node type here, so querying it raised rather than matching nothing.
        return """
        (import) @imp
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

    def _is_symbol_hidden(self, parent: typing.Any) -> bool:
        """Kotlin is public by default, so only an explicit modifier hides a declaration."""
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

    #: Declaration nodes a Kotlin identifier may belong to.
    _DECLARATION_TYPES = ("function_declaration", "class_declaration", "object_declaration")

    #: Class and function declarations this language exposes to the framework walk.
    SCM_FRAMEWORK_QUERY = "(class_declaration name: (identifier) @name) @cls\n(function_declaration name: (identifier) @name) @fn\n(object_declaration name: (identifier) @name) @cls"

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
            if child.type == "function_body":
                for sub in child.children:
                    if sub.type == "block":
                        return sub
            elif child.type == "class_body":
                return child
        return None

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

    def _base_names_in(self, specifier: typing.Any) -> list[str]:
        """Base types one delegation specifier names, directly or via a constructor invocation.

        `class A : B` names `B` as a bare `user_type`; `class A : B()` wraps it in a
        `constructor_invocation`. Both are the same base from the caller's point of view.
        """
        names = []
        for node in specifier.children:
            if node.type == "user_type":
                names.append(self._extract_marker_text(node))
            elif node.type == "constructor_invocation":
                names.extend(
                    self._extract_marker_text(sub)
                    for sub in node.children
                    if sub.type == "user_type"
                )
        return names

    def _extract_bases(self, target_node: typing.Any) -> list[str]:
        return [
            name
            for child in target_node.children
            if child.type == "delegation_specifiers"
            for specifier in child.children
            if specifier.type == "delegation_specifier"
            for name in self._base_names_in(specifier)
        ]

    def _extract_decorators(self, target_node: typing.Any) -> list[str]:
        """Annotation names on a declaration, `@` stripped, first occurrence order preserved."""
        decorators: list[str] = []
        for child in target_node.children:
            if child.type != "modifiers":
                continue
            for mod in child.children:
                if mod.type != "annotation":
                    continue
                name = self._extract_marker_text(mod).removeprefix("@")
                if name not in decorators:
                    decorators.append(name)
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
        return ["*.class", "*.jar"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["target/", "build/", ".gradle/"]
