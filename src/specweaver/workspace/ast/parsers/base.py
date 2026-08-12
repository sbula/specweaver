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

        Every parser had the identical five lines of `__init__` plus two pass-through properties to
        hold this one value (`TECH-034`). Declared as a static method rather than a class attribute
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

    @abstractmethod
    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        """Hook to filter symbols by visibility/decorators."""

    @abstractmethod
    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        """Finds the bounding node for a given symbol name."""

    @abstractmethod
    def _find_target_block(self, node: typing.Any) -> typing.Any | None:
        """Finds the inner block/body node of a given symbol node."""

    @abstractmethod
    def _format_replacement(self, code_bytes: bytes, node: typing.Any, new_code: str) -> bytes:
        """Hook to format a full symbol replacement."""

    @abstractmethod
    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        """Hook to format injecting new code into an existing block body."""

    def _get_symbol_scope(self, name_node: typing.Any) -> str | None:
        """Returns the scope (e.g., class name or receiver) of a symbol."""
        return None

    def _extract_marker_text(self, node: typing.Any) -> str:
        return typing.cast("bytes", node.text).decode("utf-8").strip()

    # -----------------------------------------------------------------------
    # Tree-walking helpers shared by every language parser
    # -----------------------------------------------------------------------
    #
    # `TECH-023`. Nine parsers each hand-rolled the same nested walk — query the tree, decode a
    # captured name, compare it, then descend through two or three levels of `if child.type == ...`
    # — and every one of them was over the complexity ceiling for it. The nesting *was* the
    # complexity; the per-language part is only which node types matter, which stays in the
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
