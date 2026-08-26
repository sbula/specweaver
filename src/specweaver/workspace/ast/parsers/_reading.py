# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading structure out of a parsed file.

Reading is separate from editing because `BaseTreeSitterParser` holding both is one class doing
four jobs.

Reading and editing turned out to share **nothing**: measured, they have zero cross-references and
each depends only on the per-language contract the base declares. That is what made splitting them
a move rather than a rewrite.

A mixin rather than a collaborator, so no parser's public API changes — every one of them still
answers `extract_symbol` and the rest exactly as before.
"""

from __future__ import annotations

import logging
import re
import typing

from tree_sitter import Query, QueryCursor

from specweaver.workspace.ast.parsers.interfaces import CodeStructureError, Visibility

logger = logging.getLogger(__name__)


#: `@trace(FR-1, FR-2)` in a comment. One tag per comma-separated entry.
_TRACE_PATTERN = re.compile(r"@trace\(([^)]+)\)")


def _trace_tags(comment_text: str) -> set[str]:
    """The traceability tags one comment declares, if any."""
    match = _TRACE_PATTERN.search(comment_text)
    return {part.strip() for part in match.group(1).split(",")} if match else set()


def _blankable_span(node: typing.Any) -> tuple[int, int] | None:
    """The byte range of a block's body, or None when there is nothing to blank.

    A leading docstring is kept: the skeleton is what a reader (or an LLM) sees instead of the
    body, and the docstring is the part of a body worth keeping.
    """
    start_cut = node.start_byte + 1
    end_cut = node.end_byte - 1

    first_child = node.children[0] if node.children else None
    if (
        first_child is not None
        and first_child.type == "expression_statement"
        and first_child.children
        and first_child.children[0].type == "string"
    ):
        start_cut = first_child.end_byte

    return (start_cut, end_cut) if start_cut < end_cut else None


class SymbolReadingMixin:
    """Extracting skeletons, symbols, bodies, listings and traceability tags."""

    # What this mixin needs from the parser it is mixed into. Declared for the type checker only:
    # it states the dependency instead of leaving `self.parser` to resolve by luck, and does not
    # touch the runtime MRO. `BaseTreeSitterParser` supplies all of it.
    if typing.TYPE_CHECKING:

        @property
        def language(self) -> typing.Any: ...
        @property
        def parser(self) -> typing.Any: ...
        @property
        def SCM_SKELETON_QUERY(self) -> str: ...
        @property
        def SCM_SYMBOL_QUERY(self) -> str: ...
        @property
        def SCM_COMMENT_QUERY(self) -> str: ...

        def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None: ...
        def _find_target_block(self, node: typing.Any) -> typing.Any | None: ...
        def _get_symbol_scope(self, name_node: typing.Any) -> str | None: ...
        def _extract_marker_text(self, node: typing.Any) -> str: ...
        def _extract_bases(self, target_node: typing.Any) -> list[str]: ...
        def _extract_decorators(self, target_node: typing.Any) -> list[str]: ...

    @staticmethod
    def _get_symbol_visibility(name_node: typing.Any) -> Visibility:
        """This declaration's access level, as a word from `VISIBILITY`.

        The one hook every language overrides, and a **static** one: the answer is a function of
        the node alone. Default is `unknown`, not `public` — a language that has not answered the
        question must say so rather than assert something it cannot know. SQL and markdown
        genuinely have no access concept and keep this default.
        """
        return "unknown"

    def _is_symbol_hidden(self, parent: typing.Any) -> bool:
        """Whether this declaration is hidden from outside its module.

        The **only** thing the shared filter varied by across four languages, so it is the hook.
        Default is "nothing is hidden": a language that has not opted in must not silently start
        dropping symbols. Java, Rust and TypeScript answer *"has no `public` modifier"*; Kotlin
        answers *"has `private`, `protected` or `internal`"* — the same question with the polarity
        its grammar happens to use.
        """
        return False

    def _is_symbol_valid(
        self,
        sym_name: str,
        name_node: typing.Any | None,
        visibility: list[str] | None,
        decorator_filter: str | None,
        framework_markers: dict[str, typing.Any],
    ) -> bool:
        """Filter a symbol by the requested visibility and decorator.

        Shared by Java, Kotlin, Rust and TypeScript, which differ by at most one token; the pair
        `{_is_symbol_valid, _is_symbol_public|_is_symbol_private}` is its own cohesive component.

        A **default, not a prohibition**: a language whose filtering is
        genuinely different still overrides this outright, as C, C++, Go, Python and the
        declarative tier all do.
        """
        if (
            visibility
            and "public" in visibility
            and name_node
            and self._is_symbol_hidden(name_node.parent)
        ):
            return False

        if decorator_filter:
            decorators = framework_markers.get(sym_name, {}).get("decorators", [])
            if not any(decorator_filter in d for d in decorators):
                return False

        return True

    #: The tree-sitter query naming this language's class and function declarations, captured as
    #: `@name` plus `@cls`/`@fn`. Data, because it is the ONLY thing the four framework-aware
    #: parsers vary by; the walk below is shared. Empty means "report nothing",
    #: so a language that never sets it is not obliged to.
    SCM_FRAMEWORK_QUERY: str = ""

    def extract_framework_markers(self, code: str) -> dict[str, dict[str, list[str]]]:
        """Decorators, and bases for a class, per declared symbol.

        A **default, not a prohibition**: `go`, `c` and `cpp` override it outright, and `rust`
        extends it — it calls `super()` and then records trait impls, which is why this lives on
        the reading mixin rather than on one tier. The declarative tier reports nothing.
        """
        from tree_sitter import Query, QueryCursor

        if not code.strip() or not self.SCM_FRAMEWORK_QUERY:
            return {}

        tree = self.parser.parse(code.encode("utf-8"))
        cursor = QueryCursor(Query(self.language, self.SCM_FRAMEWORK_QUERY))

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

    def extract_skeleton(self, code: str) -> str:
        if not code.strip():
            return code

        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)

        query = Query(self.language, self.SCM_SKELETON_QUERY)
        cursor = QueryCursor(query)
        captures = cursor.captures(tree.root_node)

        nodes_to_blank = [
            span for node in captures.get("block", []) if (span := _blankable_span(node))
        ]
        # Back to front, so each replacement leaves earlier offsets valid.
        nodes_to_blank.sort(key=lambda x: x[0], reverse=True)

        skeleton = code_bytes
        for start_byte, end_byte in nodes_to_blank:
            skeleton = skeleton[:start_byte] + b" ... " + skeleton[end_byte:]

        return skeleton.decode("utf-8")

    def extract_symbol(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot extract '{symbol_name}' from empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")
        return typing.cast("bytes", node.text).decode("utf-8")

    def extract_symbol_body(self, code: str, symbol_name: str) -> str:
        if not code.strip():
            raise CodeStructureError(f"Cannot extract body of '{symbol_name}' from empty code.")
        code_bytes = code.encode("utf-8")
        tree = self.parser.parse(code_bytes)
        node = self._find_symbol_node(tree, symbol_name)
        if not node:
            raise CodeStructureError(f"Symbol '{symbol_name}' not found in the AST.")

        target_block = self._find_target_block(node)
        if not target_block:
            raise CodeStructureError(f"Body block for symbol '{symbol_name}' not found.")
        return typing.cast("bytes", target_block.text).decode("utf-8")

    def _scoped_name(self, name_node: typing.Any) -> str:
        """`Class.method` when the symbol has a scope, the bare name otherwise."""
        sym_name = typing.cast("bytes", name_node.text).decode("utf-8")
        scope = self._get_symbol_scope(name_node)
        return f"{scope}.{sym_name}" if scope else sym_name

    def _declared_names(self, code: str) -> list[tuple[str, typing.Any]]:
        """Every declaration this grammar reports, as `(scoped_name, name_node)` in source order.

        Shared by `list_symbols` and `extract_symbol_visibility` so the two can never disagree
        about what a symbol is called. Two copies of the same lookup are two places it can drift.
        """
        if not code.strip():
            return []
        tree = self.parser.parse(code.encode("utf-8"))
        cursor = QueryCursor(Query(self.language, self.SCM_SYMBOL_QUERY))
        return [
            (self._scoped_name(name_node), name_node)
            for _match_id, match_dict in cursor.matches(tree.root_node)
            for name_node in match_dict.get("name", [])
        ]

    def extract_symbol_visibility(self, code: str, symbol_name: str) -> Visibility:
        """The access level of one symbol, as a word from `VISIBILITY`. Never raises.

        `unknown` is the answer for a name that is not there, an empty name, an empty file and
        source no grammar can read. All four are reached during a real scan, and none of them is
        worth failing a whole repository over.
        """
        if not symbol_name:
            return "unknown"
        for name, name_node in self._declared_names(code):
            if name == symbol_name:
                return self._get_symbol_visibility(name_node)
        return "unknown"

    def list_symbols(
        self, code: str, visibility: list[str] | None = None, decorator_filter: str | None = None
    ) -> list[str]:
        framework_markers = {}
        if decorator_filter:
            framework_markers = self.extract_framework_markers(code)

        symbols = [
            name
            for name, name_node in self._declared_names(code)
            if self._is_symbol_valid(
                name,
                name_node,
                visibility,
                decorator_filter,
                framework_markers,
            )
        ]
        return list(dict.fromkeys(symbols))  # de-duplicated, first-seen order preserved

    def extract_traceability_tags(self, code: str) -> set[str]:
        if not code.strip():
            return set()
        tree = self.parser.parse(code.encode("utf-8"))
        query = Query(self.language, self.SCM_COMMENT_QUERY)
        cursor = QueryCursor(query)
        return {
            tag
            for _, match_dict in cursor.matches(tree.root_node)
            for comment_node in match_dict.get("comment", [])
            for tag in _trace_tags(typing.cast("bytes", comment_node.text).decode("utf-8"))
        }
