# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the chunker does when something it depends on is missing or absurd.

Proves: B-SENS-03 FR-9, B-SENS-03 FR-10

Both cases here were found by a retrospective red/blue review on 2026-08-26, after SF-01 to SF-05
had shipped. Neither was reachable by a mutant — the mutation corpus asks *"is this line load
bearing?"*, and these are paths no line was written for.

**The visibility guard failed open.** `_levels` catches every exception per level, so a parser whose
visibility support is broken or absent left every symbol recorded as `unknown` — and `unknown`
equals `unknown`, so a private symbol merged into a public chunk. That is `FR-2`'s filter undone one
layer up, in the same direction the original defect failed.

**A file with no newlines was one chunk, whatever its size.** Splitting is on line boundaries, so a
minified bundle or a single-line JSON produced one piece of 800,000 characters against a budget of
4,000.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers


def _body(code: str, **kw: typing.Any) -> list[typing.Any]:
    """`chunk_source`, body layer only.

    `FR-12` adds a skeleton per reported symbol, so the class itself is named there even when the
    body layer split it away — and a skeleton never ends in a newline. Every claim in this file is
    about how the body was cut.
    """
    return [c for c in chunk_source(code, **kw) if c.layer == "body"]


MIXED = (
    "class Bag:\n"
    "    def get_a(self):\n        return 1\n"
    "    def __secret(self):\n        return 2\n"
    "    def get_b(self):\n        return 3\n"
)


@pytest.fixture(scope="module")
def python_parser() -> typing.Any:
    return next(v for k, v in get_default_parsers().items() if ".py" in k)


class _NoVisibility:
    """A parser that cannot answer a visibility question at all.

    Not hypothetical: `supported_parameters()` exists precisely because some parsers do not support
    every filter, and any parser outside this repository is free to raise.
    """

    def __init__(self, real: typing.Any) -> None:
        self._real = real

    def __getattr__(self, name: str) -> typing.Any:
        return getattr(self._real, name)

    def list_symbols(self, code: str, **kw: typing.Any) -> list[str]:
        if kw.get("visibility") is not None:
            raise RuntimeError("visibility unavailable")
        return list(self._real.list_symbols(code))


class TestChunkSourceMergingFailsClosed:
    def test_a_parser_with_no_visibility_support_merges_nothing(
        self, python_parser: typing.Any
    ) -> None:
        """[Hostile] The guard must fail **closed**.

        With every level unavailable, all symbols read as `unknown` — and `unknown` equals
        `unknown`, so before this fix they all merged together. A private symbol reached every
        result that asked for the public interface, which is exactly the defect `FR-2` closed one
        layer down.
        """
        chunks = _body(
            MIXED, path="m.py", parser=_NoVisibility(python_parser), language="python", max_chars=60
        )
        merged = [c for c in chunks if len(c.symbols) > 1]
        assert merged == [], [c.symbols for c in chunks]

    def test_the_symbols_still_all_appear(self, python_parser: typing.Any) -> None:
        """[Boundary] Failing closed means *not merging*, not *not indexing*. Refusing to emit
        would be a worse answer than merging was."""
        chunks = _body(
            MIXED, path="m.py", parser=_NoVisibility(python_parser), language="python", max_chars=60
        )
        assert {n for c in chunks for n in c.symbols} == {
            "Bag.get_a",
            "Bag.__secret",
            "Bag.get_b",
        }

    def test_a_working_parser_still_merges(self, python_parser: typing.Any) -> None:
        """[Happy path] The control. Failing closed everywhere would satisfy both tests above and
        silently disable `FR-9`."""
        code = "class Bag:\n" + "".join(
            f"    def get_{n}(self):\n        return {n}\n" for n in range(8)
        )
        chunks = _body(code, path="m.py", parser=python_parser, language="python", max_chars=120)
        assert any(len(c.symbols) > 1 for c in chunks), [c.symbols for c in chunks]


class TestChunkSourceSplitsALineThatIsItselfTooBig:
    def test_a_file_with_no_newlines_is_still_split(self, python_parser: typing.Any) -> None:
        """[Hostile] A minified bundle, a single-line JSON, a generated blob.

        Splitting is on line boundaries, so a file with none produced **one** chunk of whatever
        size it happened to be — 800,000 characters against a budget of 4,000, measured. Whatever
        embeds that either fails or silently truncates, and `NFR-3`'s *raw length is unbounded* was
        about indentation, not about this.
        """
        one_line = "x=1;" * 20_000
        chunks = _body(
            one_line, path="bundle.min.js", parser=python_parser, language="python", max_chars=4000
        )
        assert len(chunks) > 1
        assert max(len(c.text) for c in chunks) <= 4000 * 4

    def test_nothing_is_lost_when_a_line_is_cut(self, python_parser: typing.Any) -> None:
        """[Boundary] `FR-17` on the new path. Cutting mid-line is a last resort, not a licence to
        drop what does not fit."""
        one_line = "x=1;" * 20_000
        chunks = _body(
            one_line, path="bundle.min.js", parser=python_parser, language="python", max_chars=4000
        )
        assert "".join(c.text for c in chunks) == one_line

    def test_a_mid_line_cut_is_flagged_as_a_line_window(self, python_parser: typing.Any) -> None:
        """[Boundary] `FR-16`. Cutting inside a line produces something even less like a whole unit
        than cutting between lines does, so it says so."""
        one_line = "x=1;" * 20_000
        chunks = _body(
            one_line, path="bundle.min.js", parser=python_parser, language="python", max_chars=4000
        )
        assert all(c.is_line_window for c in chunks)

    def test_an_ordinary_file_is_still_cut_on_lines(self, python_parser: typing.Any) -> None:
        """[Happy path] The control. A mid-line cut must be the exception — a rule that always cut
        at N characters is the fixed-size window this whole capability replaced."""
        code = "def huge():\n" + "".join(f"    value_{n} = {n} + 1\n" for n in range(300))
        chunks = _body(code, path="m.py", parser=python_parser, language="python", max_chars=300)
        assert all(c.text.endswith("\n") for c in chunks[:-1]), [c.text[-20:] for c in chunks[:-1]]
