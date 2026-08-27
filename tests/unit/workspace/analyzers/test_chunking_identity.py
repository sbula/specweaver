# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What makes a chunk the same chunk, so a re-index can update instead of rebuild.

Proves: B-SENS-03 FR-13

`path + symbol + part` already identifies **which** chunk this is. What was missing is *did it
change* — and without that, re-indexing an estate means wiping the store and embedding everything
again. That is the same cost `TECH-070` is about, on the vector side.

**The hash covers every label, not only the text.** A chunk whose text is unchanged but whose
`visibility` was corrected from `public` to `private` is a **different row**: a consumer filtering
by visibility would keep serving the old answer. Hashing the text alone would leave that row
looking current.

Contained names and the scoped name — `FR-13`'s other two halves — landed in SF-04 CB-4, because
`FR-9` could not merge honestly without them.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

from specweaver.workspace.analyzers.chunking import Chunk, chunk_source, content_hash
from specweaver.workspace.ast.parsers.factory import get_default_parsers

SOURCE = '''"""Doc."""

import os


class Bag:
    def get(self):
        return 1


def free():
    return 2
'''


@pytest.fixture(scope="module")
def python_parser() -> typing.Any:
    return next(v for k, v in get_default_parsers().items() if ".py" in k)


def _chunks(parser: typing.Any, code: str = SOURCE, **kw: typing.Any) -> list[Chunk]:
    return chunk_source(code, path="src/app/m.py", parser=parser, language="python", **kw)


#: Every label except the hash itself, with a value guaranteed to differ from any real one.
OTHER_LABELS: dict[str, typing.Any] = {
    "text": "something else entirely",
    "path": "src/other/elsewhere.py",
    "symbol": "SomethingElse",
    "language": "kotlin",
    "part": 7,
    "parts": 9,
    "symbols": ("A.b", "A.c"),
    "is_line_window": True,
    "visibility": "protected",
    "package": "src/other",
    "unit": "src/other-unit",
    "layer": "skeleton",
}


class TestChunkSourceGivesEveryChunkAHash:
    def test_every_chunk_carries_one(self, python_parser: typing.Any) -> None:
        """[Happy path] A hex sha256, on every chunk of both layers."""
        for chunk in _chunks(python_parser):
            assert len(chunk.content_hash) == 64
            assert set(chunk.content_hash) <= set("0123456789abcdef")

    def test_the_same_input_gives_the_same_hash(self, python_parser: typing.Any) -> None:
        """[Boundary] `NFR-4`. A hash that moved between runs would make every re-index a rebuild,
        which is the cost this field exists to avoid."""
        first = [c.content_hash for c in _chunks(python_parser)]
        second = [c.content_hash for c in _chunks(python_parser)]
        assert first == second

    def test_different_chunks_of_one_file_differ(self, python_parser: typing.Any) -> None:
        """[Boundary] The control at the other end: a constant would satisfy the test above."""
        hashes = [c.content_hash for c in _chunks(python_parser)]
        assert len(set(hashes)) == len(hashes)


@pytest.mark.parametrize("label", sorted(OTHER_LABELS), ids=str)
class TestContentHashCoversEveryLabel:
    """One case per label, because *every label* is the requirement and a summary is not a proof."""

    def test_changing_it_changes_the_hash(self, python_parser: typing.Any, label: str) -> None:
        """[Happy path] A chunk whose text is unchanged but whose `visibility` was corrected is a
        different row. Hashing the text alone would leave the stale one looking current."""
        original = _chunks(python_parser)[0]
        altered = dataclasses.replace(original, **{label: OTHER_LABELS[label]})
        assert content_hash(altered) != content_hash(original), label


class TestContentHashIsNotItsOwnInput:
    def test_the_hash_field_does_not_feed_the_hash(self, python_parser: typing.Any) -> None:
        """[Hostile] Otherwise the value depends on whatever it happened to hold, and recomputing
        it on a stored chunk would give a different answer than computing it on a fresh one."""
        original = _chunks(python_parser)[0]
        tampered = dataclasses.replace(original, content_hash="0" * 64)
        assert content_hash(tampered) == content_hash(original)

    def test_a_chunk_agrees_with_its_own_recomputation(self, python_parser: typing.Any) -> None:
        """[Boundary] What the emitter stored is what the function computes — otherwise a reader
        checking freshness would find every row stale."""
        for chunk in _chunks(python_parser):
            assert chunk.content_hash == content_hash(chunk)

    def test_two_identical_chunks_hash_alike(self) -> None:
        """[Boundary] Content-addressed: the same content in two files is the same content, and a
        store may collapse them. Built by hand rather than from a parser, so the claim is about the
        function and nothing else."""
        one = Chunk(text="x", path="a.py", symbol="s", language="python")
        two = Chunk(text="x", path="a.py", symbol="s", language="python")
        assert content_hash(one) == content_hash(two)
