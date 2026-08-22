# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Abstract base class for Tree-sitter CodeStructure parsers."""

from __future__ import annotations

import logging
import typing
from abc import ABC, abstractmethod

from tree_sitter import Language, Parser, Query, QueryCursor

from specweaver.workspace.ast.parsers._editing import SymbolEditingMixin
from specweaver.workspace.ast.parsers._reading import SymbolReadingMixin
from specweaver.workspace.ast.parsers.interfaces import (
    CodeStructureInterface,
)

logger = logging.getLogger(__name__)


class BaseTreeSitterParser(SymbolReadingMixin, SymbolEditingMixin, CodeStructureInterface, ABC):
    """Base class centralizing Tree-sitter AST mutation and extraction."""

    @staticmethod
    @abstractmethod
    def grammar() -> object:
        """The tree-sitter language pointer for this parser.

        Holding this one value would otherwise cost every parser the identical five lines of
        `__init__` plus two pass-through properties. Declared as a static method rather than a class attribute
        because a bare callable in a class body is a method to the type checker, and would be
        handed `self`; subclasses assign `grammar = staticmethod(tree_sitter_x.language)`.

        TypeScript is the only parser needing a non-default entry point
        (`language_typescript`), which a callable expresses and a module reference would not.
        """

    def __init__(self) -> None:
        self._language = Language(self.grammar())
        self._parser = Parser(self._language)

    @property
    def language(self) -> Language:
        return self._language

    @property
    def parser(self) -> Parser:
        return self._parser

    @property
    @abstractmethod
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        """Tree-sitter query for skeletons."""

    @property
    @abstractmethod
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        """Tree-sitter query for extracting symbols."""

    @property
    @abstractmethod
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        """Tree-sitter query for extracting comments/trace tags."""

    # The grammar's own tags query, when it ships one. A module constant, so reading it is an
    # import rather than file I/O and this boundary stays pure-logic.
    TAGS_QUERY: typing.ClassVar[str | None] = None

    # Declarations a call can sit inside. Joined outward, so a method's calls are attributed to
    # `Impl.go` and not `go` — the node hash is built from the qualified name.
    CALLER_SCOPE_NODES: typing.ClassVar[tuple[str, ...]] = ()

    def extract_call_sites(self, code: str) -> dict[str, list[str]]:
        """What each symbol calls, from the grammar's tags query."""
        if not code.strip() or not self.TAGS_QUERY:
            return {}

        from tree_sitter import Query, QueryCursor

        tree = self.parser.parse(code.encode("utf-8"))
        calls: dict[str, list[str]] = {}
        cursor = QueryCursor(Query(self.language, self.TAGS_QUERY))
        for _pattern, captured in cursor.matches(tree.root_node):
            # `name` is shared with the definition patterns, so a match without `reference.call`
            # would contribute the declaration's own name as though something had called it.
            if "reference.call" not in captured:
                continue
            for node in captured.get("name", []):
                caller = self._enclosing_symbol(node)
                callee = node.text
                if callee is None:
                    continue
                calls.setdefault(caller, []).append(callee.decode("utf-8"))
        return calls

    def _enclosing_symbol(self, node: typing.Any) -> str:
        """The qualified name of the declaration a node sits in, or "" for the file itself."""
        names: list[str] = []
        current = node.parent
        while current is not None:
            if current.type in self.CALLER_SCOPE_NODES:
                declared = self._declared_type_name(current)
                if declared:
                    names.append(declared)
            current = current.parent
        return ".".join(reversed(names))

    # Node types that declare a type. Empty means the language has no such concept, or that this
    # ticket has not reached it — either way the parser reports nothing rather than guessing.
    TYPE_DECLARATION_NODES: typing.ClassVar[tuple[str, ...]] = ()

    def extract_supertypes(self, code: str) -> dict[str, dict[str, list[str]]]:
        """Walk for type declarations and ask the language what each one inherits."""
        if not code.strip() or not self.TYPE_DECLARATION_NODES:
            return {}

        found: dict[str, dict[str, list[str]]] = {}
        stack = [self.parser.parse(code.encode("utf-8")).root_node]
        while stack:
            node = stack.pop()
            stack.extend(node.children)
            if node.type not in self.TYPE_DECLARATION_NODES:
                continue
            name = self._declared_type_name(node)
            if not name:
                continue
            # MERGED, not assigned. One type can be declared across several nodes -- Rust spreads
            # `Impl` over `struct Impl;` and every `impl Trait for Impl` block -- and assigning let
            # whichever node the walk reached last silently erase the others. The walk order is an
            # implementation detail of this loop, so the result was not even stable.
            entry = found.setdefault(name, {"extends": [], "implements": []})
            for kind, supertypes in self._supertypes_of(node).items():
                seen = entry.setdefault(kind, [])
                seen.extend(s for s in supertypes if s not in seen)
        return found

    # `field_identifier` is how C and C++ spell a member's name; it appears in no other
    # grammar here, so naming it once costs nothing and saves a language override.
    _NAME_NODE_TYPES: typing.ClassVar[tuple[str, ...]] = (
        "identifier",
        "type_identifier",
        "field_identifier",
    )

    def _declared_type_name(self, node: typing.Any) -> str | None:
        """The declared name of a type or function.

        Most grammars spell it as a direct identifier child. C and C++ do not: a
        `function_definition` holds `primitive_type`, `function_declarator`, `compound_statement`,
        and the name lives inside the declarator. Descending one level when no direct child matches
        keeps that in one place rather than in two language overrides.
        """
        for child in node.children:
            if child.type in self._NAME_NODE_TYPES:
                return str(self._extract_marker_text(child))
        for child in node.children:
            if not child.type.endswith("declarator"):
                continue
            for grandchild in child.children:
                if grandchild.type in self._NAME_NODE_TYPES:
                    return str(self._extract_marker_text(grandchild))
        return None

    def _supertypes_of(self, node: typing.Any) -> dict[str, list[str]]:
        """What this type inherits. A language that separates the two kinds overrides this."""
        return {"extends": [], "implements": []}

    @staticmethod
    def _type_names_in(node: typing.Any | None) -> list[str]:
        """The bare type names in a clause, so `Base<T>` contributes `Base`."""
        if node is None:
            return []
        names: list[str] = []
        stack = [node]
        while stack:
            current = stack.pop(0)
            # `Base<T>` is a dependency on `Base`. `T` is a type parameter, not a supertype, so the
            # argument list is never descended into.
            if current.type in ("type_arguments", "type_parameters"):
                continue
            if current.type in ("type_identifier", "identifier", "scoped_type_identifier"):
                names.append(current.text.decode("utf-8"))
                continue
            stack = list(current.children) + stack
        return names

    @abstractmethod
    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        """Finds the bounding node for a given symbol name."""

    @abstractmethod
    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        """Finds the inner block/body node of a given symbol node."""

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        """Returns the scope (e.g., class name or receiver) of a symbol."""
        return None

    def _extract_marker_text(self, node: typing.Any) -> str:
        return typing.cast("bytes", node.text).decode("utf-8").strip()

    # -----------------------------------------------------------------------
    # Tree-walking helpers shared by every language parser
    # -----------------------------------------------------------------------
    #
    # Nine parsers need the same nested walk — query the tree, decode a captured name, compare it,
    # then descend through two or three levels of `if child.type == ...`. Hand-rolled, each one is
    # over the complexity ceiling, because the nesting *is* the complexity; the per-language part is
    # only which node types matter, which stays in the
    # subclass where it belongs.

    @staticmethod
    def _split_scope(symbol_name: str) -> tuple[str | None, str]:
        """`("Class", "method")` for a dotted name, `(None, name)` for a bare one.

        Splits on the FIRST dot, matching every parser's original behaviour.
        """
        if "." in symbol_name:
            scope, name = symbol_name.split(".", 1)
            return scope, name
        return None, symbol_name

    def _named_nodes(self, tree: typing.Any, target_name: str) -> typing.Iterator[typing.Any]:
        """Every `name` capture in `SCM_SYMBOL_QUERY` whose text is exactly `target_name`."""
        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        for _, match_dict in QueryCursor(query).matches(tree.root_node):
            for name_node in match_dict.get("name", []):
                if typing.cast("bytes", name_node.text).decode("utf-8") == target_name:
                    yield name_node

    def _named_matches(
        self, tree: typing.Any, target_name: str, *, strip: bool = False
    ) -> typing.Iterator[tuple[typing.Any, dict[str, typing.Any]]]:
        """Like `_named_nodes`, but hands back the whole match.

        Parsers that return a separately-captured `block` rather than the identifier's parent need
        the other captures, not just the name node.
        """
        query = Query(self.language, self.SCM_SYMBOL_QUERY)
        for _, match_dict in QueryCursor(query).matches(tree.root_node):
            for name_node in match_dict.get("name", []):
                text = typing.cast("bytes", name_node.text).decode("utf-8")
                if (text.strip() if strip else text) == target_name:
                    yield name_node, match_dict

    @staticmethod
    def _children_of_type(node: typing.Any, *types: str) -> typing.Iterator[typing.Any]:
        """Direct children of `node` whose type is one of `types`."""
        return (child for child in getattr(node, "children", []) if child.type in types)

    @staticmethod
    def _text_of(node: typing.Any) -> str:
        """A node's source text, decoded."""
        return typing.cast("bytes", node.text).decode("utf-8")
