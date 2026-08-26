# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`list_symbols(visibility=...)` returns what was asked for, and only that.

Proves: B-SENS-03 FR-2

Before this boundary the filter understood exactly one word. `_is_symbol_valid` read
`visibility and "public" in visibility and ...`, so **every other value fell through to
`return True`** and handed back the whole file. Asking for `["private"]` — the safest-sounding
request there is — was the one that returned the most.

A filter whose whole job is to withhold, failing open, is the worst direction for it to fail in.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.ast.parsers.factory import get_default_parsers

from .test_visibility_mapping import EXPECTED
from .test_visibility_vocabulary import _BY_CLASS, FIXTURES, UNFILTERED


@pytest.fixture(scope="module")
def parsers() -> dict[str, typing.Any]:
    return {_BY_CLASS[type(p).__name__]: p for p in get_default_parsers().values()}


def _with_level(lang: str, *levels: str) -> list[str]:
    """The symbols whose mapped level is one of `levels`, in the parser's own order.

    Built from `EXPECTED` -- the specification table -- and ordered by `UNFILTERED`, so the
    expectation comes from what each language *says*, never from what the filter answers.
    """
    asked = set(levels)
    # `unknown` counts as visible, so it answers a request that names `public` -- and only that
    # one. Encoded here rather than special-cased per language, because it is one rule (`AD-5`).
    wanted = {
        sym
        for sym, level in EXPECTED[lang].items()
        if ("public" in asked if level == "unknown" else level in asked)
    }
    return [sym for sym in UNFILTERED[lang] if sym in wanted]


@pytest.mark.parametrize("lang", sorted(EXPECTED), ids=str)
@pytest.mark.parametrize("level", ["public", "protected", "internal", "private"], ids=str)
class TestListSymbolsReturnsOnlyTheLevelAsked:
    """[Happy path] One request, one level, every language."""

    def test_a_single_level_request(
        self, parsers: dict[str, typing.Any], lang: str, level: str
    ) -> None:
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=[level]) == _with_level(
            lang, level
        )


@pytest.mark.parametrize("lang", sorted(EXPECTED), ids=str)
class TestListSymbolsCombinesLevels:
    def test_the_interface_request_returns_public_and_protected(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Happy path] `["public", "protected"]` is the request a cross-module reader makes.

        It returned **public only** before this boundary: the old filter tested membership of the
        word `public` and then ignored the rest of the list, so a protected member was dropped by
        a request that explicitly named it.
        """
        assert parsers[lang].list_symbols(
            FIXTURES[lang], visibility=["public", "protected"]
        ) == _with_level(lang, "public", "protected")

    def test_asking_for_every_level_returns_the_whole_file(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] The control at the far end. A filter that dropped everything would satisfy
        each single-level assertion above by returning empty; this one it cannot."""
        every = ["public", "protected", "internal", "private", "unknown"]
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=every) == UNFILTERED[lang]


@pytest.mark.parametrize("lang", ["c", "sql", "markdown"], ids=str)
class TestListSymbolsWhereTheLanguageCannotSay:
    """A language with no access concept answers `unknown`, and `unknown` counts as visible."""

    def test_a_public_request_returns_everything(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Graceful degradation] Hiding these would empty the index for two of the eight target
        languages. C returned NOTHING for every request before this boundary."""
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=["public"]) == UNFILTERED[lang]

    def test_a_private_request_returns_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] `unknown` is treated as visible, not as a wildcard. It answers a request for
        the visible set; it does not answer a request for a level the language never had."""
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=["private"]) == []


@pytest.mark.parametrize("lang", sorted(EXPECTED), ids=str)
class TestListSymbolsHostileRequests:
    def test_a_level_that_does_not_exist_returns_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] The fail-open itself, inverted. This returned the entire file on nine of ten
        parsers, and one of the two live callers passes whatever an agent typed."""
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=["nonsense"]) == []

    def test_a_real_level_beside_a_nonsense_one_still_works(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] One bad word must not poison the request, and must not widen it either."""
        assert parsers[lang].list_symbols(
            FIXTURES[lang], visibility=["public", "nonsense"]
        ) == _with_level(lang, "public")

    def test_an_empty_request_list_filters_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Hostile] `[]` means *no filter*, for every parser.

        Three answers came from this one input before: eight parsers returned everything, while C
        and C++ tested `visibility is None` or membership and returned nothing. One shared filter
        is what removes the disagreement.
        """
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=[]) == UNFILTERED[lang]

    def test_no_request_at_all_filters_nothing(
        self, parsers: dict[str, typing.Any], lang: str
    ) -> None:
        """[Boundary] The unfiltered path must survive the rewrite untouched."""
        assert parsers[lang].list_symbols(FIXTURES[lang], visibility=None) == UNFILTERED[lang]
