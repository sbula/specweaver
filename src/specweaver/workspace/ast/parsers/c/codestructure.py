# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tree-sitter CodeStructureInterface implementation for C."""

import logging
import typing

import tree_sitter_c
from tree_sitter import Query

from specweaver.workspace.ast.parsers import _c_family
from specweaver.workspace.ast.parsers._ref_tools import Renames
from specweaver.workspace.ast.parsers.interfaces import CodeStructureError, Visibility
from specweaver.workspace.ast.parsers.tiers import FunctionBasedParser

logger = logging.getLogger(__name__)


def _refuse_decorator_filter(
    sym_name: str,
    name_node: typing.Any,
    decorator_filter: str,
    framework_markers: dict[str, typing.Any],
) -> bool:
    """C has no decorators, so a request to filter by one has no truthful answer.

    Refusing is the right call and it is the only parser that makes it: returning nothing would
    read as *no symbol carries that annotation*, which is a claim about the code rather than about
    the question.
    """
    logger.error("Decorator filtering requested but not supported in C parsers")
    raise CodeStructureError("Decorator filtering is not supported in C parsers")


_TYPE_NODES = frozenset(
    {"struct_specifier", "enum_specifier", "union_specifier", "type_definition"}
)


def _static_is_private(name_node: typing.Any) -> Visibility:
    """`static` keeps a C function or variable inside its file: private; otherwise public.

    A type has no linkage, so for a struct, enum or typedef C cannot say.
    """
    node = name_node
    while node is not None and node.type not in ("function_definition", "declaration"):
        if node.type in _TYPE_NODES:
            return "unknown"
        node = node.parent
    if node is None:
        return "unknown"
    storage = (c for c in node.children if c.type == "storage_class_specifier")
    return "private" if any(c.text == b"static" for c in storage) else "public"


class CCodeStructure(Renames, FunctionBasedParser):
    """AST parser for C source files."""

    grammar = staticmethod(tree_sitter_c.language)
    _matches_decorator = staticmethod(_refuse_decorator_filter)
    _get_symbol_visibility = staticmethod(_static_is_private)

    # Held here because this grammar ships no tags query. Original work, written from
    # the grammar by inspection rather than adapted from upstream.
    TAGS_QUERY: typing.ClassVar[str | None] = """
        (call_expression function: (identifier) @name) @reference.call
        """
    CALLER_SCOPE_NODES: typing.ClassVar[tuple[str, ...]] = ("function_definition",)

    def _finder(self) -> typing.Any:
        return _c_family

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
        return [i for i in super().supported_intents() if i != "framework_markers"]

    def supported_parameters(self) -> list[str]:
        return []

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        target_scope, target_name = self._split_scope(symbol_name)

        for name_node, match_dict in self._named_matches(tree, target_name):
            if self._get_symbol_scope(name_node) == target_scope:
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

    def _replacement_bytes(self, new_code: str, node: typing.Any) -> bytes:
        """Verbatim: brace blocks carry their own indentation."""
        del node
        return new_code.encode("utf-8")

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        logger.debug("extract_framework_markers called for C parser (returning empty)")
        return {}

    def extract_imports(self, code: str) -> list[str]:
        if not code.strip():
            return []
        logger.debug("extract_imports called for C parser")
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
        logger.debug("add_symbol called for target_parent=%s", target_parent)
        if not target_parent:
            return code + "\n\n" + new_code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        parent_node = self._find_symbol_node(tree, target_parent)
        if not parent_node:
            from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

            logger.error("Target parent '%s' not found during add_symbol", target_parent)
            raise CodeStructureError(f"Target parent '{target_parent}' not found.")

        target_block = self._find_target_block(parent_node)
        if not target_block:
            from specweaver.workspace.ast.parsers.interfaces import CodeStructureError

            logger.error("Body block for symbol '%s' not found during add_symbol", target_parent)
            raise CodeStructureError(f"Body block for symbol '{target_parent}' not found.")

        end_byte = typing.cast("int", target_block.end_byte) - 1
        margin = typing.cast("int", parent_node.start_point[1])
        member = self._member_margin(code_bytes, target_block, margin)
        indented_code = self._auto_indent(new_code, member)

        return (
            code_bytes[:end_byte]
            + b"\n"
            + indented_code.encode("utf-8")
            + b"\n"
            + code_bytes[end_byte:]
        ).decode("utf-8")
