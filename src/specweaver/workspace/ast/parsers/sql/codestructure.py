# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SQL CodeStructure parser for extracting exact code symbol skeletons."""

from __future__ import annotations

import logging
import typing

import tree_sitter_sql

from specweaver.workspace.ast.parsers.tiers import DeclarativeParser

logger = logging.getLogger(__name__)


class SqlCodeStructure(DeclarativeParser):
    """SQL tree-sitter structural parser."""

    grammar = staticmethod(tree_sitter_sql.language)

    @property
    def SCM_SKELETON_QUERY(self) -> str:  # noqa: N802
        return """
        (create_table (column_definitions) @block)
        (create_view (create_query) @block)
        (create_function (function_body) @block)
        """

    @property
    def SCM_SYMBOL_QUERY(self) -> str:  # noqa: N802
        # Captured on `object_reference`, not on the `identifier` inside it. A reference holds one
        # identifier per name part, so capturing the identifier reported `public.orders` as TWO
        # symbols -- `public` and `orders` -- and put a chunk named after a schema into the index.
        # The reference's own text is already the whole name, qualified or not.
        return """
        (create_table (object_reference) @name)
        (create_view (object_reference) @name)
        (create_function (object_reference) @name)
        """

    @property
    def SCM_COMMENT_QUERY(self) -> str:  # noqa: N802
        return """
        """

    def _find_symbol_node(self, tree: typing.Any, symbol_name: str) -> typing.Any | None:
        """SQL has no scoping, so the name is matched exactly as reported.

        The name node **is** the `object_reference` since the capture moved up, so the statement is
        one level above it rather than two.

        No type guard here, deliberately. `_named_nodes` yields only `name` captures from
        `SCM_SYMBOL_QUERY`, and this query captures nothing but `object_reference` — so a guard on
        the type could never be false. The mutation corpus said so: neutralising it changed no
        observable behaviour and no test noticed, which is what an equivalent mutant looks like.
        A branch that cannot be taken is decoration for the same reason a test that cannot fail is.

        **Strictness lives in `_named_nodes`**, which matches a name's text exactly — so `orders`
        does not resolve to `public.orders`. That is where `FR-7`'s mutant points.
        """
        for name_node in self._named_nodes(tree, symbol_name):
            return name_node.parent
        return None

    def _format_body_injection(
        self, code_bytes: bytes, target_block: typing.Any, new_code: str, margin: int
    ) -> bytes:
        return code_bytes

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
        ]

    def supported_parameters(self) -> list[str]:
        return []

    def get_binary_ignore_patterns(self) -> list[str]:
        return ["*.sqlite", "*.db", "*.mdf", "*.ldf"]

    def get_default_directory_ignores(self) -> list[str]:
        return ["data/", "migrations/"]

    def add_symbol(self, code: str, target_parent: str | None, new_code: str) -> str:
        code_bytes = code.encode("utf-8")
        indented_code = self._auto_indent(new_code, 0).encode("utf-8")
        if not code.endswith("\n"):
            return (code_bytes + b"\n\n" + indented_code).decode("utf-8")
        return (code_bytes + b"\n" + indented_code).decode("utf-8")
