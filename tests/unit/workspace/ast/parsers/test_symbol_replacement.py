# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The splice every parser shares, and the one thing three of them change about it.

`TECH-037`. `_format_replacement` was written out **ten** times. Six were character-for-character
identical (`go`, `java`, `kotlin`, `python`, `rust`, `typescript`); `sql` was the same logic with
two lines reordered; `c`, `cpp` and `markdown` differed in exactly one respect — they splice the
new code in verbatim instead of re-indenting it to the node's column.

So the shared thing is "replace the node's byte span", and the variance is one question: *does the
incoming code get re-indented?* That is the hook, and it keeps `TECH-034`'s tier rule — a default,
never a prohibition.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.ast.parsers.c.codestructure import CCodeStructure
from specweaver.workspace.ast.parsers.cpp.codestructure import CppCodeStructure
from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.markdown.codestructure import MarkdownCodeStructure
from specweaver.workspace.ast.parsers.python.codestructure import PythonCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.parsers.sql.codestructure import SqlCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

#: Parsers that re-indent the replacement to the node's column.
INDENTING = [
    GoCodeStructure,
    JavaCodeStructure,
    KotlinCodeStructure,
    PythonCodeStructure,
    RustCodeStructure,
    SqlCodeStructure,
    TypeScriptCodeStructure,
]

#: Parsers that splice verbatim. C-family braces and Markdown sections carry their own layout, so
#: re-indenting them would corrupt the block rather than align it.
VERBATIM = [CCodeStructure, CppCodeStructure, MarkdownCodeStructure]

ALL_PARSERS = INDENTING + VERBATIM


class _Node:
    """The three attributes `_format_replacement` reads off a tree-sitter node."""

    def __init__(self, start_byte: int, end_byte: int, column: int) -> None:
        self.start_byte = start_byte
        self.end_byte = end_byte
        self.start_point = (0, column)


@pytest.mark.parametrize("parser_cls", ALL_PARSERS, ids=lambda c: c.__name__)
class TestFormatReplacement:
    def test_the_node_span_is_replaced_and_the_rest_is_untouched(self, parser_cls: type) -> None:
        code = b"HEADold bodyTAIL"
        node = _Node(start_byte=4, end_byte=12, column=0)

        out = parser_cls()._format_replacement(code, node, "new body")

        assert out.startswith(b"HEAD")
        assert out.endswith(b"TAIL")
        assert b"old body" not in out

    def test_an_empty_replacement_deletes_the_span(self, parser_cls: type) -> None:
        node = _Node(start_byte=4, end_byte=12, column=0)

        assert parser_cls()._format_replacement(b"HEADold bodyTAIL", node, "") == b"HEADTAIL"

    def test_the_splice_is_not_redeclared_on_the_language(self, parser_cls: type) -> None:
        """Ten copies became one. A regression would silently restore a per-language splice."""
        assert "_format_replacement" not in vars(parser_cls), (
            f"{parser_cls.__name__} re-declares the shared splice"
        )


@pytest.mark.parametrize("parser_cls", INDENTING, ids=lambda c: c.__name__)
def test_an_indenting_parser_aligns_to_the_node_column(parser_cls: type) -> None:
    node = _Node(start_byte=0, end_byte=0, column=4)

    out = parser_cls()._format_replacement(b"", node, "a\nb")

    assert b"    b" in out, f"{parser_cls.__name__} did not indent the continuation line"


@pytest.mark.parametrize("parser_cls", VERBATIM, ids=lambda c: c.__name__)
def test_a_verbatim_parser_leaves_the_replacement_alone(parser_cls: type) -> None:
    node = _Node(start_byte=0, end_byte=0, column=4)

    assert parser_cls()._format_replacement(b"", node, "a\nb") == b"a\nb"


@pytest.mark.parametrize("parser_cls", VERBATIM, ids=lambda c: c.__name__)
def test_a_verbatim_parser_says_so_by_overriding_the_hook(parser_cls: type) -> None:
    """The variance must be declared, not inherited by accident."""
    assert "_replacement_bytes" in vars(parser_cls)


@pytest.mark.parametrize("parser_cls", INDENTING, ids=lambda c: c.__name__)
def test_an_indenting_parser_takes_the_default(parser_cls: type) -> None:
    assert "_replacement_bytes" not in vars(parser_cls)


def test_a_typing_cast_is_not_required_of_a_plain_int_node() -> None:
    """The extracted helper must not depend on tree-sitter's node type, only its attributes."""
    out = GoCodeStructure()._format_replacement(b"ab", _Node(1, 2, 0), "X")

    assert out == b"aX"
    assert isinstance(out, bytes)
