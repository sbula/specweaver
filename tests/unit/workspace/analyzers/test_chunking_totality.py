# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A chunk says whether it is a whole unit, and no path loses anything.

Proves: B-SENS-03 FR-16, B-SENS-03 FR-17

**`FR-16`.** A file no parser can read is still indexed, because a file missing from the index is
indistinguishable from *this code does not exist*. But until now it was also indistinguishable from
a module preamble: both arrived carrying no symbol at all. A consumer cannot rank a binary blob
below real code without being told which it is.

**`FR-17` is two claims, and the second is not implied by the first.** Totality compares
non-whitespace characters, so a merge that dropped the blank run between two symbols satisfied it
while producing `... return 1clas s Beta:` — a chunk whose content never existed in the file and
which no reader could locate in it. That was found in SF-04 CB-4 by mutating the fix and getting
SILENT back. The assertion that catches it is **containment**, and this file states both claims
across **every** path rather than only the one where the defect happened to surface.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers


@pytest.fixture(scope="module")
def python_parser() -> object:
    return next(v for k, v in get_default_parsers().items() if ".py" in k)


class _RaisingParser:
    """A parser that fails outright, as a missing grammar does."""

    def list_symbols(self, code: str, **kw: typing.Any) -> list[str]:
        raise RuntimeError("no grammar for this language")

    def extract_symbol(self, code: str, name: str) -> str:
        raise RuntimeError("no grammar for this language")


def _chunks(parser: object, code: str, **kw: typing.Any) -> list[typing.Any]:
    return chunk_source(code, path="m.py", parser=parser, language="python", **kw)


#: One case per path through the chunker. `FR-17` binds all of them, not the one where the defect
#: was found.
PATHS: dict[str, str] = {
    "preamble and symbols": '"""Doc."""\n\nimport os\n\n\ndef alpha():\n    return 1\n',
    "merged neighbours": "class Bag:\n"
    + "".join(f"    def get_{n}(self):\n        return {n}\n" for n in range(8)),
    "structure split": "class Fat:\n"
    + "".join(
        f"    def m{n}(self):\n" + "".join(f"        v_{n}_{i} = {i}\n" for i in range(12))
        for n in range(4)
    ),
    "line fallback": "def huge():\n" + "".join(f"    value_{n} = {n} + 1\n" for n in range(300)),
    "no symbols at all": "# just a comment\n# and another\n",
    "unparseable": "<<<< %%% not code at all >>>>\n",
}


class TestChunkSourceFlagsALineWindow:
    def test_a_file_the_parser_cannot_read_is_flagged(self) -> None:
        """[Graceful degradation] `FR-16`. Indexed, and marked as not a whole unit."""
        chunks = _chunks(_RaisingParser(), "some bytes no grammar handles\n")
        assert chunks
        assert all(c.is_line_window for c in chunks)

    def test_an_ordinary_symbol_is_not_flagged(self, python_parser: object) -> None:
        """[Happy path] The control. A flag set on everything says nothing."""
        chunks = [c for c in _chunks(python_parser, "def alpha():\n    return 1\n") if c.symbols]
        assert chunks
        assert not any(c.is_line_window for c in chunks)

    def test_the_preamble_is_not_a_line_window(self, python_parser: object) -> None:
        """[Boundary] It is a whole unit — the head of the file, cut at a real boundary."""
        code = '"""Doc."""\nimport os\n\n\ndef alpha():\n    return 1\n'
        preamble = next(c for c in _chunks(python_parser, code) if c.symbol == "<module>")
        assert not preamble.is_line_window

    def test_the_last_resort_line_cut_is_flagged(self, python_parser: object) -> None:
        """[Boundary] `FR-10`'s fallback is the same fallback reached for a different reason.

        The design's `FR-16` names only the unreadable file, but a consumer ranking by *is this a
        whole unit* needs both marked — a symbol sliced at line 400 is no more a unit than a binary
        blob is.
        """
        code = "def huge():\n" + "".join(f"    value_{n} = {n} + 1\n" for n in range(300))
        cut = [c for c in _chunks(python_parser, code, max_chars=300) if c.parts > 1]
        assert cut
        assert all(c.is_line_window for c in cut)

    def test_a_symbol_that_fits_is_never_flagged(self, python_parser: object) -> None:
        """[Boundary] The pair for the assertion above: cutting is what sets it, not size."""
        code = "def small():\n    return 1\n"
        assert not any(c.is_line_window for c in _chunks(python_parser, code, max_chars=4000))


@pytest.mark.parametrize("path", sorted(PATHS), ids=str)
class TestChunkSourceLosesNothingOnAnyPath:
    """`FR-17`, stated once per path rather than once per defect."""

    def test_every_non_blank_character_survives(self, python_parser: object, path: str) -> None:
        """[Boundary] Totality."""
        code = PATHS[path]
        for budget in (60, 300, 4000):
            joined = "".join(c.text for c in _chunks(python_parser, code, max_chars=budget))
            assert "".join(joined.split()) == "".join(code.split()), (path, budget)

    def test_every_chunk_is_a_verbatim_slice_of_the_file(
        self, python_parser: object, path: str
    ) -> None:
        """[Hostile] The second claim, which totality does not imply.

        A merge that dropped the blank run between two symbols satisfied totality and produced text
        that never existed. Containment is what catches that, and it is asserted here on every
        path — including the ones where no merge happens, because a rule that only holds where it
        was tested is not a rule.
        """
        code = PATHS[path]
        for budget in (60, 300, 4000):
            for chunk in _chunks(python_parser, code, max_chars=budget):
                assert chunk.text in code, (path, budget, chunk.symbols, chunk.text[:50])

    def test_no_chunk_is_empty(self, python_parser: object, path: str) -> None:
        """[Boundary] Blank chunks would satisfy both claims above and still be waste."""
        for budget in (60, 300, 4000):
            assert all(
                c.text.strip() for c in _chunks(python_parser, PATHS[path], max_chars=budget)
            )


class TestChunkSourceLosesNothingWhenTheParserFails:
    def test_the_whole_file_survives_a_parser_that_raises(self) -> None:
        """[Graceful degradation] `FR-17` on the path that has no symbols to anchor to."""
        code = "".join(f"line {n} of something unparseable\n" for n in range(80))
        chunks = _chunks(_RaisingParser(), code, max_chars=200)

        joined = "".join(c.text for c in chunks)
        assert "".join(joined.split()) == "".join(code.split())
        assert all(c.text in code for c in chunks)
