# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Python CodeStructure parser for extracting exact code symbol skeletons."""

from __future__ import annotations

import logging
import typing

import tree_sitter_python
from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers import _docs
from specweaver.workspace.ast.parsers import _visibility as _vis
from specweaver.workspace.ast.parsers.interfaces import (
    CodeStructureError,
    FileBindings,
    Reference,
    Visibility,
)
from specweaver.workspace.ast.parsers.python import _references
from specweaver.workspace.ast.parsers.tiers import ClassBasedParser, enclosing_name

logger = logging.getLogger(__name__)


def _visibility_of(name_node: typing.Any) -> Visibility:
    """Python has no access keywords, so the name IS the modifier.

    `__init__` and `__mangled` differ by a trailing pair of underscores and by nothing else, and
    the old filter treated them alike. They are opposites: a dunder is protocol a caller is meant
    to use, while a single-leading `__` asks the interpreter to mangle the name precisely so
    outsiders cannot reach it. Measured 2026-08-26: `__mangled` was in the `exposes:` list of
    every generated `context.yaml`.
    """
    short = _vis.name_text(name_node)
    if short.startswith("__") and short.endswith("__"):
        return "public"
    if short.startswith("__"):
        return "private"
    if short.startswith("_"):
        return "internal"
    return "public"


class PythonCodeStructure(ClassBasedParser):
    """Python tree-sitter structural parser."""

    grammar = staticmethod(tree_sitter_python.language)
    _doc_of = staticmethod(_docs.docstring_doc)
    _get_symbol_visibility = staticmethod(_visibility_of)

    TYPE_DECLARATION_NODES: typing.ClassVar[tuple[str, ...]] = ("class_definition",)

    def _supertypes_of(self, node: typing.Any) -> dict[str, list[str]]:
        """Python has no interfaces, so there is no distinction here to lose."""
        bases = next((c for c in node.children if c.type == "argument_list"), None)
        return {"extends": self._type_names_in(bases), "implements": []}

    def find_references(self, code: str, name: str) -> list[Reference]:
        return _references.find_references(self.parser.parse(code.encode("utf-8")).root_node, name)

    def file_bindings(self, code: str) -> FileBindings:
        return _references.file_bindings(self.parser.parse(code.encode("utf-8")).root_node)

    def supported_intents(self) -> list[str]:
        return [*super().supported_intents(), "rename"]

    TAGS_QUERY: typing.ClassVar[str | None] = tree_sitter_python.TAGS_QUERY
    CALLER_SCOPE_NODES: typing.ClassVar[tuple[str, ...]] = (
        "function_definition",
        "class_definition",
    )

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

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        return enclosing_name(name_node, ("class_definition",), "identifier")

    #: Class and function declarations this language exposes to the framework walk.
    SCM_FRAMEWORK_QUERY = "(class_definition name: (identifier) @name) @cls\n(function_definition name: (identifier) @name) @fn"

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

    def _process_import_node(self, node: typing.Any, imports: set[str]) -> None:
        """Record the module an import statement names."""
        if node.type == "import_statement":
            imports.update(self._plain_import_modules(node))
        elif node.type == "import_from_statement":
            imports.update(self._from_import_modules(node))

    def _plain_import_modules(self, node: typing.Any) -> typing.Iterator[str]:
        """`import a.b` and `import a.b as c` both name `a.b`."""
        for child in node.children:
            if child.type == "dotted_name":
                yield self._extract_marker_text(child)
            elif child.type == "aliased_import":
                for aliased in self._children_of_type(child, "dotted_name"):
                    yield self._extract_marker_text(aliased)
                    break

    def _from_import_modules(self, node: typing.Any) -> typing.Iterator[str]:
        """The module a `from ... import ...` names, relative or not.

        The grammar wraps a relative module in `relative_import`, whose own text is the whole path —
        `.sibling`, `..pkg.mod`. Reading only the statement's direct `dotted_name` children found
        the imported NAME instead, so every relative import reported a symbol.
        """
        relative = next(iter(self._children_of_type(node, "relative_import")), None)
        if relative is None:
            yield from self._first_dotted_name(node)
            return

        prefix = self._extract_marker_text(relative)
        if next(iter(self._children_of_type(relative, "dotted_name")), None) is not None:
            yield prefix
            return

        # `from . import a, b` names no module of its own; each imported name is a submodule of the
        # package the dots point at, so both spellings of one dependency agree.
        for child in self._children_of_type(node, "dotted_name"):
            yield f"{prefix}{self._extract_marker_text(child)}"

    def _first_dotted_name(self, node: typing.Any) -> typing.Iterator[str]:
        """`from a.b import x` names `a.b` — the FIRST dotted_name, since `x` is one too."""
        for child in self._children_of_type(node, "dotted_name"):
            yield self._extract_marker_text(child)
            return

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
        block = self._find_target_block(node)
        member = self._member_margin(code_bytes, block, margin) if block else margin + 4
        indented_code = self._auto_indent(new_code, member).encode("utf-8")

        mutated = (
            code_bytes[:end_byte]
            + b"\n"
            + (b" " * member)
            + indented_code
            + b"\n"
            + code_bytes[end_byte:]
        )
        return mutated.decode("utf-8")

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.pyc", "*.pyo", "*.pyd"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["__pycache__/", ".pytest_cache/", ".tox/", ".venv/"]
