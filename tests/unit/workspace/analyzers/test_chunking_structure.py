# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""An oversized symbol is cut where the code has a seam, not where the count runs out.

Proves: B-SENS-03 FR-8, B-SENS-03 FR-10

Measured on this repository 2026-08-26: **97 of 1,102 top-level symbols exceed the budget**, and
every one of them was cut on line boundaries. `ContainerSubprocessExecutor` became six parts, and
part 3 began in the middle of a method — a fragment that never existed as code, which is the exact
failure this module's docstring says it exists to prevent, one level down.

Splitting on nested symbols instead leaves **15** still oversized. `FR-10` keeps line cutting for
those, as a last resort rather than the only one.

**Nesting is a property of the tree, not of the name.** `S` is inside `P` when `P` is a reported
symbol, `S` is named `P.<rest>`, **and** `S`'s text lies within `P`'s — all three. A dot alone is
not enough: `FR-7` made `public.orders` a top-level SQL object whose name contains one, and the
filter this replaces dropped every qualified table and function from the index.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers


@pytest.fixture(scope="module")
def parsers() -> dict[str, typing.Any]:
    found = {}
    for exts, parser in get_default_parsers().items():
        for ext in exts:
            found[ext.lstrip(".")] = parser
    return found


def _method(name: str, statements: int) -> str:
    body = "\n".join(f"        value_{name}_{n} = {n} + 1" for n in range(statements))
    return f"    def {name}(self):\n{body}\n"


def _fat_class(methods: int, statements: int) -> str:
    bodies = "\n".join(_method(f"m{i}", statements) for i in range(methods))
    return f"class Fat:\n{bodies}\n"


def _chunks(parser: object, code: str, lang: str = "python", **kw: typing.Any) -> list[typing.Any]:
    return chunk_source(code, path=f"m.{lang}", parser=parser, language=lang, **kw)


class TestChunkSourceSplitsOnNestedSymbols:
    def test_an_oversized_class_becomes_its_methods(self, parsers: dict[str, typing.Any]) -> None:
        """[Happy path] The claim itself. Every chunk names a method, not a numbered slice."""
        code = _fat_class(methods=6, statements=20)
        chunks = _chunks(parsers["py"], code, max_chars=400)

        named = {name for c in chunks for name in c.symbols}
        assert named == {f"Fat.m{i}" for i in range(6)}

    def test_no_chunk_is_a_numbered_slice_of_the_class(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Happy path] Stated as an absence, because emitting the methods AND the old line parts
        would satisfy the assertion above while doubling the index."""
        chunks = _chunks(parsers["py"], _fat_class(methods=6, statements=20), max_chars=400)
        assert all(c.parts == 1 for c in chunks), [
            (c.symbol, c.part, c.parts) for c in chunks if c.parts != 1
        ]

    def test_a_class_that_fits_stays_one_chunk(self, parsers: dict[str, typing.Any]) -> None:
        """[Boundary] The control. Splitting is what *over budget* triggers, not what class means —
        a rule that always split would satisfy both assertions above."""
        code = _fat_class(methods=2, statements=1)
        named = [n for c in _chunks(parsers["py"], code, max_chars=4000) for n in c.symbols]
        assert named == ["Fat"]

    def test_a_method_too_big_even_alone_falls_back_to_lines(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Boundary] `FR-10`. When a symbol has no nested symbols left and is still over budget,
        line cutting is what remains — now the last resort rather than the only one."""
        code = _fat_class(methods=1, statements=200)
        chunks = [c for c in _chunks(parsers["py"], code, max_chars=300) if c.symbols]

        assert {n for c in chunks for n in c.symbols} == {"Fat.m0"}
        assert max(c.parts for c in chunks) > 1

    def test_splitting_recurses(self, parsers: dict[str, typing.Any]) -> None:
        """[Boundary] A nested class inside an oversized class must itself be reached, or depth two
        is silently line-cut while depth one is not.

        Asserted on the **methods being reached whole**, not on what they are called. A first draft
        expected `Outer.Inner.deep_0` and failed: Python scopes a symbol to its *immediately*
        enclosing class only, so a nested class's method is reported as `Inner.deep_0`. That is a
        parser property, and asserting it here would have been this test claiming something it does
        not own — and a name that cannot say which `Inner` it came from is a real gap, recorded for
        SF-06's `FR-13`.
        """
        inner = "    class Inner:\n" + "\n".join(
            f"        def deep_{n}(self):\n            v_{n} = {n} + 1" for n in range(6)
        )
        code = f"class Outer:\n{inner}\n"
        chunks = _chunks(parsers["py"], code, max_chars=120)

        deep = [name for c in chunks for name in c.symbols if "deep_" in name]
        assert len(deep) == 6, [c.symbols for c in chunks]
        assert all(c.parts == 1 for c in chunks)


class TestChunkSourceNestingIsNotPunctuation:
    """`FR-7` made a dot mean two different things. The chunker must read the tree instead."""

    def test_a_qualified_sql_object_is_chunked(self, parsers: dict[str, typing.Any]) -> None:
        """[Hostile] The hazard SF-03's plan handed forward.

        `public.orders` is a **top-level** object whose name contains a dot. The filter this
        replaces read a dot as *nested* and dropped it, so every qualified table and function in
        an estate would have been missing from the index with nothing to show it.
        """
        code = "CREATE TABLE public.orders (id INT);\nCREATE VIEW summary AS SELECT 1;\n"
        named = {n for c in _chunks(parsers["sql"], code, lang="sql") for n in c.symbols}
        assert named == {"public.orders", "summary"}

    def test_a_real_nested_symbol_is_still_treated_as_nested(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Happy path] The other half. A rule that called everything top-level would pass the
        test above and index every method twice."""
        code = "class Beta:\n    def go(self):\n        return 1\n"
        named = [n for c in _chunks(parsers["py"], code, max_chars=4000) for n in c.symbols]
        assert named == ["Beta"]

    def test_a_dotted_name_whose_prefix_is_not_a_symbol_is_top_level(
        self, parsers: dict[str, typing.Any]
    ) -> None:
        """[Hostile] Said as a rule rather than as SQL. Three conditions, ANDed: the prefix must be
        a reported symbol, the name must extend it, and the text must actually be inside."""
        code = "CREATE FUNCTION analytics.total() RETURNS INT AS $$ SELECT 1 $$ LANGUAGE SQL;\n"
        named = {n for c in _chunks(parsers["sql"], code, lang="sql") for n in c.symbols}
        assert named == {"analytics.total"}


class TestChunkSourceStructureKeepsItsOldGuarantees:
    """The behaviour SF-04 replaces sat under real guarantees. They still hold."""

    def test_nothing_is_lost(self, parsers: dict[str, typing.Any]) -> None:
        """[Boundary] `FR-17` across the new split path, at several budgets."""
        code = _fat_class(methods=5, statements=30)
        for budget in (80, 400, 4000):
            joined = "".join(c.text for c in _chunks(parsers["py"], code, max_chars=budget))
            assert "".join(joined.split()) == "".join(code.split()), f"lost content at {budget}"

    def test_no_chunk_is_empty(self, parsers: dict[str, typing.Any]) -> None:
        """[Boundary] A split that produced blank chunks would satisfy totality and still be wrong."""
        chunks = _chunks(parsers["py"], _fat_class(methods=4, statements=25), max_chars=200)
        assert all(c.text.strip() for c in chunks)

    def test_the_same_input_gives_the_same_chunks(self, parsers: dict[str, typing.Any]) -> None:
        """[Boundary] `NFR-4`. Recursion makes ordering load-bearing in a way it was not before."""
        code = _fat_class(methods=4, statements=25)
        first = [(c.symbol, c.part, c.text) for c in _chunks(parsers["py"], code, max_chars=200)]
        second = [(c.symbol, c.part, c.text) for c in _chunks(parsers["py"], code, max_chars=200)]
        assert first == second

    def test_unparseable_source_still_yields_chunks(self, parsers: dict[str, typing.Any]) -> None:
        """[Graceful degradation] `FR-16` is SF-05's, but the fallback must not break on the way."""
        assert _chunks(parsers["py"], "<<<< %%% >>>>", max_chars=4000) != []
