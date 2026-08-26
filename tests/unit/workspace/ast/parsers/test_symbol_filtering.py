# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The symbol filter every parser shares, and the one thing each language changes about it.

`TECH-035`. `_is_symbol_valid` was written out four times — Java, Rust and TypeScript
**byte-identical**, Kotlin differing by a single token (`self._is_symbol_private(...)` where the
others have `not self._is_symbol_public(...)`). Four copies of a filter is four places its two
rules can drift apart, and `check_class_health` found it independently: the pair
`{_is_symbol_valid, _is_symbol_public|_is_symbol_private}` was a separate connected component in
all four classes, i.e. the metric named this exact split.

The variance is one question — *is this declaration hidden from outside its module?* — so that is
the hook, and the filter itself moves to the base as a concrete default. The tier rule from
`TECH-034` still governs: **a tier supplies defaults, never prohibitions**, so a language that
needs different filtering still overrides `_is_symbol_valid` outright, as C, C++, Go and Python do.
"""

from __future__ import annotations

import typing

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

#: Every shipped parser. The filter was shared by four of them until 2026-08-26; C, C++, Go and
#: Python kept their own copies, and the declarative tier had a ninth that answered `True` to
#: everything. Three of the defects `FR-2` closed lived in those copies, which is the argument for
#: the list being all ten rather than a subset.
SHARED_FILTER_PARSERS = [
    CCodeStructure,
    CppCodeStructure,
    GoCodeStructure,
    JavaCodeStructure,
    KotlinCodeStructure,
    MarkdownCodeStructure,
    PythonCodeStructure,
    RustCodeStructure,
    SqlCodeStructure,
    TypeScriptCodeStructure,
]

#: The seven whose decorator answer is the shared one. C raises rather than answer, Go answers
#: `False` because the language has none, and C++ reads attributes off the node instead of the
#: marker table. Three deliberate exceptions, each pinned in `test_visibility_vocabulary.py`.
SHARED_DECORATOR_PARSERS = [
    JavaCodeStructure,
    KotlinCodeStructure,
    MarkdownCodeStructure,
    PythonCodeStructure,
    RustCodeStructure,
    SqlCodeStructure,
    TypeScriptCodeStructure,
]

#: The seven with an access concept of their own. SQL and markdown have none and keep the
#: `unknown` default; C has none either and is deliberately among them for the same reason.
ANSWER_THE_HOOK = [
    CppCodeStructure,
    GoCodeStructure,
    JavaCodeStructure,
    KotlinCodeStructure,
    PythonCodeStructure,
    RustCodeStructure,
    TypeScriptCodeStructure,
]


def _filter(parser: typing.Any, **overrides: typing.Any) -> bool:
    kwargs: dict[str, typing.Any] = {
        "sym_name": "thing",
        "name_node": None,
        "visibility": None,
        "decorator_filter": None,
        "framework_markers": {},
    }
    kwargs.update(overrides)
    return bool(parser._is_symbol_valid(**kwargs))


@pytest.mark.parametrize("parser_cls", SHARED_DECORATOR_PARSERS, ids=lambda c: c.__name__)
class TestTheSharedFilterIsInherited:
    def test_no_filter_requested_keeps_the_symbol(self, parser_cls: type) -> None:
        assert _filter(parser_cls()) is True

    def test_a_decorator_filter_rejects_a_symbol_without_it(self, parser_cls: type) -> None:
        assert _filter(parser_cls(), decorator_filter="Inject") is False

    def test_a_decorator_filter_keeps_a_symbol_carrying_it(self, parser_cls: type) -> None:
        markers = {"thing": {"decorators": ["Injectable"]}}

        assert _filter(parser_cls(), decorator_filter="Inject", framework_markers=markers) is True

    def test_a_public_filter_with_no_name_node_cannot_judge_and_keeps_it(
        self, parser_cls: type
    ) -> None:
        """`name_node` is optional in the signature; every copy guarded on it and so must this."""
        assert _filter(parser_cls(), visibility=["public"], name_node=None) is True

    def test_the_filter_is_not_redeclared_on_the_language(self, parser_cls: type) -> None:
        """The point of the exercise: NINE copies became one, and must not silently return.

        `check_class_health` would catch a regression as a new component, but only for a class in
        its baseline — this says it directly.
        """
        assert "_is_symbol_valid" not in vars(parser_cls), (
            f"{parser_cls.__name__} re-declares the shared filter"
        )


class TestTheVisibilityHookIsWhatLanguagesVary:
    """Each language answers one question, and it is the only thing that differs.

    The question changed on 2026-08-26. It was a boolean — *is this hidden?* — which could not
    express `internal`, could not tell a Java interface member from a class member, and left the
    filter with only one word it understood. It is now a value: `_get_symbol_visibility` returns
    one of `VISIBILITY`.

    It is also **static**, and bound as a class attribute rather than defined as a method, because
    a visibility rule is a pure function of one AST node. Defining it as a method made
    `check_class_health` report a new LCOM4 component in four parsers — the metric saying the rule
    was a separate concern wearing a method's clothes.
    """

    def test_the_default_is_unknown_not_public(self) -> None:
        """A language that has not answered must say so, rather than assert something it cannot
        know. `unknown` counts as visible, so nothing disappears — but nothing claims to be public
        on a language's behalf either."""
        assert SqlCodeStructure()._get_symbol_visibility(None) == "unknown"

    @pytest.mark.parametrize("parser_cls", ANSWER_THE_HOOK, ids=lambda c: c.__name__)
    def test_every_parser_with_an_access_concept_answers_it(self, parser_cls: type) -> None:
        assert "_get_symbol_visibility" in vars(parser_cls), (
            f"{parser_cls.__name__} has access levels but does not say what they map to"
        )
