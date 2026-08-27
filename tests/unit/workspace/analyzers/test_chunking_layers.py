# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Two views of the same file: what it offers, and what it does.

Proves: B-SENS-03 FR-12, B-SENS-03 NFR-6

A retrieval hit on a body tells you how something works. A hit on a signature tells you it exists
and what it promises — and that is the question asked first, so the two are separate layers and a
consumer can rank one above the other.

**Skeletons never merge.** Measured across 921 symbols in this repository: a skeleton is 99
non-whitespace characters at the median, so a 4,000 budget would hold about **forty** of them. Forty
signatures in one chunk matches everything, which is the low-discrimination problem that made
`FR-6` per-symbol instead of per-file in the first place `[agreed 2026-08-26]`.

**Skeletons never split** either — the largest measured is 1,563 against a budget of 4,000. The
pathological case still goes through the same emitter, so nothing is lost if one ever does.

**`FR-17` binds the body layer, both halves.** A skeleton chunk is a description and a signature
**concatenated**, so it is not a verbatim slice of the file and never could be. Totality and
verbatim-ness are claims about the body layer; the skeleton layer is a projection and is
deliberately incomplete.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers

SOURCE = '''"""What this module is for."""

import os


class Bag:
    """A bag."""

    def get(self):
        return 1

    def __secret(self):
        return 2


def free():
    return 3
'''


@pytest.fixture(scope="module")
def python_parser() -> typing.Any:
    return next(v for k, v in get_default_parsers().items() if ".py" in k)


def _chunks(parser: typing.Any, code: str = SOURCE, **kw: typing.Any) -> list[typing.Any]:
    return chunk_source(code, path="src/app/m.py", parser=parser, language="python", **kw)


def _layer(chunks: list[typing.Any], name: str) -> list[typing.Any]:
    return [c for c in chunks if c.layer == name]


class TestChunkSourceEmitsBothLayers:
    def test_every_symbol_has_a_skeleton(self, python_parser: typing.Any) -> None:
        """[Happy path] One per **reported symbol**, independent of how the body layer cut things.

        `Bag` fits, so the body layer holds one chunk for the whole class and none for its methods.
        The skeleton layer still holds `Bag.get` — that independence is the point of having layers.
        """
        skeletons = {c.symbol for c in _layer(_chunks(python_parser), "skeleton")}
        assert {"Bag", "Bag.get", "Bag.__secret", "free"} <= skeletons

    def test_a_skeleton_carries_the_description_and_the_signature(
        self, python_parser: typing.Any
    ) -> None:
        """[Happy path] `FR-6`'s output, one layer up."""
        bag = next(c for c in _layer(_chunks(python_parser), "skeleton") if c.symbol == "Bag")
        assert "A bag." in bag.text
        assert "class Bag" in bag.text

    def test_a_skeleton_holds_no_body(self, python_parser: typing.Any) -> None:
        """[Happy path] Stated as an absence: a skeleton that carried its body would be the body
        chunk again, and the layer would cost storage for nothing."""
        for chunk in _layer(_chunks(python_parser), "skeleton"):
            assert "return 1" not in chunk.text
            assert "return 3" not in chunk.text

    def test_the_body_layer_is_unchanged(self, python_parser: typing.Any) -> None:
        """[Boundary] Adding a layer must not move the other one."""
        bodies = _layer(_chunks(python_parser), "body")
        assert {n for c in bodies for n in c.symbols} == {"Bag", "free"}

    def test_every_chunk_declares_a_layer(self, python_parser: typing.Any) -> None:
        """[Boundary] No chunk may be in neither — a consumer filtering by layer would drop it."""
        assert all(c.layer in {"skeleton", "body"} for c in _chunks(python_parser))


class TestChunkSourceKeepsTheLayersIndependent:
    def test_skeletons_do_not_merge(self, python_parser: typing.Any) -> None:
        """[Hostile] The decision a measurement made `[agreed 2026-08-26]`.

        At a 4,000 budget forty median skeletons would fit in one chunk, and a chunk holding forty
        signatures matches everything. Bodies are big and varied, so merging them buys density;
        skeletons are small and alike, so merging them undoes the reason the layer exists.
        """
        code = "class Bag:\n" + "".join(
            f"    def get_{n}(self):\n        return {n}\n" for n in range(12)
        )
        for chunk in _layer(_chunks(python_parser, code), "skeleton"):
            assert len(chunk.symbols) == 1, chunk.symbols

    def test_bodies_still_merge(self, python_parser: typing.Any) -> None:
        """[Happy path] The control. Disabling merging outright would satisfy the test above and
        silently retire `FR-9`."""
        code = "class Bag:\n" + "".join(
            f"    def get_{n}(self):\n        return {n}\n" for n in range(12)
        )
        bodies = _layer(_chunks(python_parser, code, max_chars=120), "body")
        assert any(len(c.symbols) > 1 for c in bodies), [c.symbols for c in bodies]

    def test_the_preamble_is_in_both_layers(self, python_parser: typing.Any) -> None:
        """[Boundary] `[agreed 2026-08-26]`. It has no body to elide, so its skeleton is the same
        text — duplicated deliberately, because skeletons are ranked first and *what is this file
        for* would otherwise live only in the layer read second."""
        chunks = _chunks(python_parser)
        in_both = {c.layer for c in chunks if c.symbol == "<module>"}
        assert in_both == {"skeleton", "body"}


class TestChunkSourceTotalityBindsTheBodyLayer:
    def test_the_body_layer_loses_nothing(self, python_parser: typing.Any) -> None:
        """[Boundary] `FR-17`, first half, narrowed to the layer it can hold for."""
        joined = "".join(c.text for c in _layer(_chunks(python_parser), "body"))
        assert "".join(joined.split()) == "".join(SOURCE.split())

    def test_every_body_chunk_is_a_verbatim_slice(self, python_parser: typing.Any) -> None:
        """[Boundary] `FR-17`, second half, narrowed with it."""
        for chunk in _layer(_chunks(python_parser), "body"):
            assert chunk.text in SOURCE

    def test_a_skeleton_is_deliberately_not_a_slice(self, python_parser: typing.Any) -> None:
        """[Hostile] Said out loud rather than left as an exception someone later 'fixes'.

        A skeleton is a description and a signature concatenated — with the comment markers
        stripped — so it is not text the file contains, and no amount of care would make it so.
        That is why `FR-12` narrows both halves of `FR-17` rather than either one.
        """
        bag = next(c for c in _layer(_chunks(python_parser), "skeleton") if c.symbol == "Bag")
        assert bag.text not in SOURCE

    def test_a_skeleton_still_carries_its_scope(self, python_parser: typing.Any) -> None:
        """[Boundary] `FR-14`'s labels are not body-only: the skeleton layer is the one a
        visibility filter reads first."""
        by_name = {c.symbol: c for c in _layer(_chunks(python_parser), "skeleton")}
        assert by_name["Bag.__secret"].visibility == "private"
        assert by_name["Bag.get"].visibility == "public"
        assert by_name["Bag"].package == "src/app"
