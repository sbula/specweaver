# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every language's access levels, mapped onto one vocabulary.

Proves: B-SENS-03 FR-1, FR-3, FR-4

Ten languages disagree about visibility, and a consumer filtering across them cannot work on raw
keywords. `FR-1` normalises them to five words. Two rows carry the reasoning the rest inherit:

**Go has no `private`.** A lowercase identifier is visible to its whole package, so it maps to
`internal`. Mapping it to `private` would hide code from the package-mates entitled to use it.

**A member with no modifier takes its container's rule.** Inside a class that is the language
default — package-private in Java, private in Rust. Inside an interface or trait it is implicitly
public. Java and Rust both read "no modifier" as hidden today, which is right for a class and wrong
for an interface, and this file is where that is fixed.

The literals here are what each language's specification says, **not** what the parsers answered
before this boundary. `test_visibility_vocabulary.py` holds the latter, and the two disagree on
purpose until CB-3 wires the filter to this hook.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.parsers.interfaces import VISIBILITY

from .test_visibility_vocabulary import _BY_CLASS, FIXTURES, UNFILTERED


@pytest.fixture(scope="module")
def parsers() -> dict[str, typing.Any]:
    return {_BY_CLASS[type(p).__name__]: p for p in get_default_parsers().values()}


#: symbol name -> the level its language's specification gives it.
EXPECTED: dict[str, dict[str, str]] = {
    "python": {
        "Store": "public",
        "Store.__init__": "public",  # dunder: interface, not accident
        "Store.__repr__": "public",
        "Store.get": "public",
        "Store._helper": "internal",
        "Store.__mangled": "private",  # leading only, no trailing -- name-mangled
        "free": "public",
        "_private_free": "internal",
    },
    "java": {
        "Shape": "public",
        "Shape.area": "public",  # interface member, implicitly public by JLS
        "Shape.name": "public",
        "Circle": "public",
        "Circle.area": "public",
        "Circle.log": "protected",
        "Circle.packagePrivate": "internal",  # no modifier inside a CLASS
        "Circle.helper": "private",
        "Circle.name": "public",
    },
    "kotlin": {
        "Shape": "public",
        "Shape.area": "public",
        "Circle": "public",
        "Circle.area": "public",
        "Circle.log": "protected",
        "Circle.mod": "internal",
        "Circle.helper": "private",
        "free": "public",
    },
    "typescript": {
        "Circle": "public",
        "Circle.area": "public",
        "Circle.log": "protected",  # today reported as visible -- FR-3
        "Circle.helper": "private",  # today reported as visible -- FR-3
        "Hidden": "internal",  # not exported
        "Hidden.run": "internal",
        "free": "public",
        "notExported": "internal",
    },
    "rust": {
        "Shape": "public",
        "name": "public",  # trait member; arrives unscoped today, SF-03 FR-18 fixes the NAME
        "Circle": "public",
        "Circle.area": "public",
        "Circle.crate_only": "internal",  # pub(crate)
        "Circle.helper": "private",
        "free": "public",
        "private_free": "private",
    },
    "go": {
        "Circle": "public",
        "Circle.Area": "public",
        "Circle.helper": "internal",  # NOT private -- FR-4
        "Free": "public",
        "notExported": "internal",
    },
    "cpp": {
        "Widget": "public",
        "Widget.visible": "public",
        "Widget.guarded": "protected",
        "Widget.secret": "private",
        "Plain": "public",  # struct members default to public
        "Plain.open": "public",
        "free_fn": "public",
    },
    # No access concept at all. `unknown` rather than `public`, so nothing downstream reads a
    # claim the language never made.
    "c": {name: "unknown" for name in ["Point", "Colour", "helper", "public_fn"]},
    "sql": {name: "unknown" for name in ["public", "orders", "summary", "analytics", "total"]},
    "markdown": {name: "unknown" for name in ["Title", "Title.Section", "Title.Section.Deep"]},
}

_CASES = [(lang, sym, level) for lang, m in EXPECTED.items() for sym, level in m.items()]


class TestExtractSymbolVisibilityVocabulary:
    def test_the_vocabulary_is_exactly_five_words(self) -> None:
        """[Happy path] A closed set. An eleventh language may not quietly add a sixth."""
        assert VISIBILITY == ("public", "protected", "internal", "private", "unknown")

    def test_every_expectation_uses_a_word_in_the_vocabulary(self) -> None:
        """[Boundary] Guards this file against itself: a typo here would otherwise read as a
        parser defect."""
        assert {level for _, _, level in _CASES} <= set(VISIBILITY)

    @pytest.mark.parametrize("lang", sorted(EXPECTED), ids=str)
    def test_every_symbol_the_parser_lists_has_an_expectation(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] The coverage guard. Without it a parser could stop reporting a symbol and
        this file would get quieter rather than redder."""
        assert set(EXPECTED[lang]) == set(UNFILTERED[lang])


@pytest.mark.parametrize(("lang", "symbol", "level"), _CASES, ids=lambda v: str(v))
class TestExtractSymbolVisibilityPerLanguage:
    """[Happy path] One case per symbol per language — the whole mapping, asserted as data."""

    def test_the_symbol_maps_to_its_specified_level(
        self, parsers: dict[str, typing.Any], lang: str, symbol: str, level: str
    ) -> None:
        assert parsers[lang].extract_symbol_visibility(FIXTURES[lang], symbol) == level


@pytest.mark.parametrize("lang", sorted(EXPECTED), ids=str)
class TestExtractSymbolVisibilityDegrades:
    def test_an_unknown_symbol_is_unknown_not_an_error(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] A name that is not in the file. `unknown` rather than a raise: this is called
        per symbol during a scan, and one bad name must not take the scan down."""
        assert parsers[lang].extract_symbol_visibility(FIXTURES[lang], "NoSuchSymbol") == "unknown"

    def test_an_empty_file_is_unknown(self, parsers: dict[str, typing.Any], lang: str) -> None:
        """[Boundary] Nothing to judge."""
        assert parsers[lang].extract_symbol_visibility("", "anything") == "unknown"

    def test_unparseable_source_is_unknown(self, parsers: dict[str, typing.Any], lang: str) -> None:
        """[Graceful degradation] tree-sitter is error-tolerant; the answer must be a word from the
        vocabulary either way, never an exception."""
        assert parsers[lang].extract_symbol_visibility("<<<< %%% >>>>", "x") in VISIBILITY

    def test_an_empty_symbol_name_is_unknown(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] An empty name matches nothing, and must not match everything."""
        assert parsers[lang].extract_symbol_visibility(FIXTURES[lang], "") == "unknown"


class TestListSymbolsIsUntouchedByThisBoundary:
    """[Boundary] CB-2 adds a hook and wires it to nothing. CB-1's net must stay green.

    Stated here rather than left implicit: if this boundary changed `list_symbols`, the
    characterization file would be the thing that failed, and the cause would be one file away
    from the failure.
    """

    @pytest.mark.parametrize("lang", sorted(EXPECTED), ids=str)
    def test_the_unfiltered_listing_has_not_moved(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        assert parsers[lang].list_symbols(FIXTURES[lang]) == UNFILTERED[lang]

    @pytest.mark.parametrize("lang", sorted(EXPECTED), ids=str)
    def test_empty_code_with_a_decorator_filter_still_returns_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] CB-2 moved `list_symbols`' early return into `_declared_names`, which puts
        `extract_framework_markers` ahead of it rather than behind.

        For C that matters twice over: it raises on a decorator filter, and the raise must still
        NOT fire when there is nothing to filter. Behaviour is unchanged, and unchanged is exactly
        the kind of claim that goes untested until a refactor breaks it.
        """
        assert parsers[lang].list_symbols("", decorator_filter="Inject") == []
