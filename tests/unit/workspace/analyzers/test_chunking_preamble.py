# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The head of a file is a thing, and it has a name.

Proves: B-SENS-03 FR-15

A module's docstring, its imports and its top-level constants are usually the part that says what
the file depends on and what it is for — and they arrived as `symbol=''`, indistinguishable from
the blank line between two methods and from a binary blob no parser could read.

Measured on this repository: **617 top-level assignments** in `src/` are reported as symbols by no
parser, so this chunk is the only place they are addressable at all.

**`<module>` names the run before the first symbol, and nothing else** `[agreed 2026-08-26]`. Text
*between* symbols stays unnamed: a stray comment in the middle of a file is not the module's own
description, and indexing it as one would be worse than leaving it anonymous.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers

MODULE = "<module>"

SOURCE = '''"""What this module is for."""

import os

CONSTANT = 1


def alpha():
    return 1


def beta():
    return 2
'''


@pytest.fixture(scope="module")
def python_parser() -> object:
    return next(v for k, v in get_default_parsers().items() if ".py" in k)


def _chunks(parser: object, code: str = SOURCE, **kw: typing.Any) -> list[typing.Any]:
    return chunk_source(code, path="m.py", parser=parser, language="python", **kw)


class TestChunkSourceNamesThePreamble:
    def test_the_run_before_the_first_symbol_is_named(self, python_parser: object) -> None:
        """[Happy path] The claim."""
        preamble = [c for c in _chunks(python_parser) if c.symbol == MODULE]
        assert len(preamble) == 1
        assert "What this module is for" in preamble[0].text
        assert "import os" in preamble[0].text
        assert "CONSTANT = 1" in preamble[0].text

    def test_the_preamble_stops_at_the_first_symbol(self, python_parser: object) -> None:
        """[Boundary] It is the *head* of the file, not everything that is not a function."""
        preamble = next(c for c in _chunks(python_parser) if c.symbol == MODULE)
        assert "def alpha" not in preamble.text

    def test_the_preamble_reports_no_symbols(self, python_parser: object) -> None:
        """[Boundary] `<module>` is a name this chunker gives, not a symbol a parser reported.
        Putting it in `symbols` would make it indistinguishable from something the language
        actually declares."""
        preamble = next(c for c in _chunks(python_parser) if c.symbol == MODULE)
        assert preamble.symbols == ()

    def test_a_file_with_no_preamble_has_no_module_chunk(self, python_parser: object) -> None:
        """[Boundary] The control. A rule that always emitted one would pass every test above."""
        code = "def alpha():\n    return 1\n"
        assert [c for c in _chunks(python_parser, code) if c.symbol == MODULE] == []


class TestChunkSourceNamesNothingElseModule:
    def test_text_between_two_symbols_stays_unnamed(self, python_parser: object) -> None:
        """[Hostile] The half that decides whether `<module>` means anything.

        A rule that named every no-symbol run would satisfy the happy path and then index a stray
        mid-file comment as the module's own description.
        """
        code = (
            "import os\n\n"
            "def alpha():\n    return 1\n\n"
            "# a note that is about neither of them\n\n"
            "def beta():\n    return 2\n"
        )
        named = [c for c in _chunks(python_parser, code) if c.symbol == MODULE]
        assert len(named) == 1
        assert "a note that is about neither" not in named[0].text

    def test_a_class_header_is_not_a_module_preamble(self, python_parser: object) -> None:
        """[Hostile] A class that splits into its methods emits its own `class Foo:` line as a gap.
        That gap is inside a symbol, so it is emphatically not the head of the file."""
        body = "\n".join(f"    def m{n}(self):\n        value_{n} = {n} + 1" for n in range(6))
        code = f"import os\n\nclass Fat:\n{body}\n"
        chunks = _chunks(python_parser, code, max_chars=120)

        named = [c for c in chunks if c.symbol == MODULE]
        assert len(named) == 1
        assert "class Fat" not in named[0].text

    def test_a_file_that_does_not_parse_has_no_module_chunk(self, python_parser: object) -> None:
        """[Graceful degradation] There is no *first symbol*, so there is no *before* it. What that
        file gets instead is `FR-16`'s line window, in CB-2."""
        chunks = _chunks(python_parser, "<<<< %%% not code >>>>")
        assert chunks != []
        assert [c for c in chunks if c.symbol == MODULE] == []


class TestChunkSourcePreambleKeepsItsGuarantees:
    def test_nothing_is_lost(self, python_parser: object) -> None:
        """[Boundary] `FR-17`."""
        joined = "".join(c.text for c in _chunks(python_parser))
        assert "".join(joined.split()) == "".join(SOURCE.split())

    def test_every_chunk_is_a_verbatim_slice(self, python_parser: object) -> None:
        """[Boundary] `FR-17`'s second half, which totality does not imply."""
        for chunk in _chunks(python_parser):
            assert chunk.text in SOURCE

    def test_the_module_name_cannot_collide_with_a_real_symbol(self, python_parser: object) -> None:
        """[Hostile] `<module>` is not a legal identifier in any of the eight target languages, so
        no parser can report a symbol by that name. Asserted rather than assumed."""
        code = 'def alpha():\n    return "<module>"\n'
        named = {c.symbol for c in _chunks(python_parser, code)}
        assert MODULE not in named
