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

from specweaver.workspace.ast.parsers.go.codestructure import GoCodeStructure
from specweaver.workspace.ast.parsers.java.codestructure import JavaCodeStructure
from specweaver.workspace.ast.parsers.kotlin.codestructure import KotlinCodeStructure
from specweaver.workspace.ast.parsers.rust.codestructure import RustCodeStructure
from specweaver.workspace.ast.parsers.typescript.codestructure import TypeScriptCodeStructure

#: Every parser whose filtering is now inherited rather than copied.
SHARED_FILTER_PARSERS = [
    JavaCodeStructure,
    KotlinCodeStructure,
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


@pytest.mark.parametrize("parser_cls", SHARED_FILTER_PARSERS, ids=lambda c: c.__name__)
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
        """The point of the exercise: four copies became one, and must not silently return.

        `check_class_health` would catch a regression as a new component, but only for a class in
        its baseline — this says it directly.
        """
        assert "_is_symbol_valid" not in vars(parser_cls), (
            f"{parser_cls.__name__} re-declares the shared filter"
        )


class TestTheHiddenHookIsWhatLanguagesVary:
    """Each language answers one question, and it is the only thing that differed."""

    def test_nothing_is_hidden_by_default(self) -> None:
        """A language that never opts in must not start filtering symbols out."""
        assert GoCodeStructure()._is_symbol_hidden(None) is False

    @pytest.mark.parametrize("parser_cls", SHARED_FILTER_PARSERS, ids=lambda c: c.__name__)
    def test_every_sharing_parser_answers_it(self, parser_cls: type) -> None:
        assert "_is_symbol_hidden" in vars(parser_cls), (
            f"{parser_cls.__name__} shares the filter but does not say what 'hidden' means"
        )
