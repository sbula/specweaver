# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Small neighbours are combined, and a private one is never combined with a public one.

Proves: B-SENS-03 FR-9

Twelve three-line getters became twelve chunks. Each is a few tokens of near-identical shape, so
they match everything and discriminate nothing — the low-information-density case cAST's greedy
merge exists for, and the other half of the split it publishes alongside.

**Merging is where this feature can do real harm**, which is why the visibility guard has its own
test and its own mutant: a public getter combined with a private helper puts the private one into
every result that asks for the public interface. That is the thing `FR-2`'s filter was fixed to
prevent, undone one layer up.

`Chunk.symbols` arrives here rather than in SF-06 because `FR-9` cannot be honest without it: a
merged chunk holds several symbols and `symbol` cannot name it, and anonymous chunks are the defect
this whole capability exists to remove.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers


@pytest.fixture(scope="module")
def python_parser() -> object:
    for exts, parser in get_default_parsers().items():
        if ".py" in exts:
            return parser
    raise AssertionError("no Python parser registered")


def _getters(count: int, prefix: str = "get") -> str:
    body = "\n".join(f"    def {prefix}_{n}(self):\n        return {n}\n" for n in range(count))
    return f"class Bag:\n{body}"


def _chunks(parser: object, code: str, **kw: typing.Any) -> list[typing.Any]:
    return chunk_source(code, path="m.py", parser=parser, language="python", **kw)


class TestChunkSourceMergesSmallNeighbours:
    def test_twelve_getters_do_not_become_twelve_chunks(self, python_parser: object) -> None:
        """[Happy path] The claim. `max_chars` is small enough to force the class to split into
        its methods, so without merging this is twelve."""
        chunks = _chunks(python_parser, _getters(12), max_chars=120)
        assert 1 < len(chunks) < 12, [c.symbols for c in chunks]

    def test_a_merged_chunk_names_everything_inside_it(self, python_parser: object) -> None:
        """[Happy path] The half that makes merging honest. A merged chunk with no names is an
        anonymous chunk, which is the defect this capability exists to remove."""
        chunks = _chunks(python_parser, _getters(12), max_chars=120)
        merged = [c for c in chunks if len(c.symbols) > 1]
        assert merged, [c.symbols for c in chunks]
        assert all(name.startswith("Bag.get_") for c in merged for name in c.symbols)

    def test_every_getter_appears_exactly_once_across_the_chunks(
        self, python_parser: object
    ) -> None:
        """[Boundary] Merging must not duplicate or drop a symbol on the way."""
        chunks = _chunks(python_parser, _getters(12), max_chars=120)
        seen = [name for c in chunks for name in c.symbols]
        assert sorted(seen) == sorted(f"Bag.get_{n}" for n in range(12))

    def test_an_unmerged_chunk_still_names_its_symbol(self, python_parser: object) -> None:
        """[Boundary] `symbols` is set for every chunk, not only merged ones — otherwise a
        consumer needs two rules to read one field."""
        code = "class Solo:\n    def only(self):\n        return 1\n"
        chunks = [c for c in _chunks(python_parser, code, max_chars=4000) if c.symbol]
        assert [c.symbols for c in chunks] == [("Solo",)]

    def test_merging_respects_the_budget(self, python_parser: object) -> None:
        """[Boundary] **Split-then-merge must not undo the split.**

        It looks as though it should: the split produces small siblings, and merging combines
        small siblings. It cannot, because both obey the same budget — the class was over it, so
        its methods cannot all merge back into one. More than one chunk, always.
        """
        chunks = _chunks(python_parser, _getters(40), max_chars=200)
        assert len(chunks) > 1
        solid = [len("".join(c.text.split())) for c in chunks]
        assert max(solid) <= 200, solid


class TestChunkSourceNeverMergesAcrossVisibility:
    """The one thing `FR-9` can get dangerously wrong."""

    def test_a_public_getter_is_not_merged_with_a_private_helper(
        self, python_parser: object
    ) -> None:
        """[Hostile] A private symbol inside a public chunk reaches every result that asks for the
        public interface — `FR-2`'s filter undone one layer up, where no filter can see it."""
        code = (
            "class Bag:\n"
            "    def get_a(self):\n        return 1\n"
            "    def __secret(self):\n        return 2\n"
            "    def get_b(self):\n        return 3\n"
        )
        chunks = _chunks(python_parser, code, max_chars=60)

        # The budget matters and the first draft got it wrong. At 90 the class fits whole, so
        # nothing splits, nothing merges, and the loop below iterates one chunk named `Bag` --
        # passing while proving nothing. The mutant said so: the guard could be deleted and no
        # test noticed. At 60 the class splits and two of these methods WOULD merge without it.
        assert len(chunks) > 1, "fixture must force the class to split, or this proves nothing"
        assert any("Bag.__secret" in c.symbols for c in chunks), chunks

        for chunk in chunks:
            names = set(chunk.symbols)
            assert not (names & {"Bag.__secret"} and names - {"Bag.__secret"}), chunk.symbols

    def test_symbols_of_one_level_still_merge_around_a_private_one(
        self, python_parser: object
    ) -> None:
        """[Boundary] The control. A guard that refused every merge would satisfy the test above.

        Two public getters on either side of a private helper are **not** neighbours: merging them
        would reorder the file. So they stay separate, and this asserts the guard is a boundary
        rather than an off switch — merging still happens elsewhere in the same file.
        """
        code = (
            "class Bag:\n"
            + "".join(f"    def get_{n}(self):\n        return {n}\n" for n in range(6))
            + "    def __secret(self):\n        return 9\n"
        )
        chunks = _chunks(python_parser, code, max_chars=110)
        assert any(len(c.symbols) > 1 for c in chunks), [c.symbols for c in chunks]


class TestChunkSourceMergeKeepsItsGuarantees:
    def test_nothing_is_lost(self, python_parser: object) -> None:
        """[Boundary] `FR-17`. A merged span covers the text between its symbols, so a comment
        between two merged methods travels with them rather than becoming its own chunk."""
        code = _getters(10)
        for budget in (60, 120, 4000):
            joined = "".join(c.text for c in _chunks(python_parser, code, max_chars=budget))
            assert "".join(joined.split()) == "".join(code.split()), f"lost content at {budget}"

    def test_every_chunk_is_a_verbatim_slice_of_the_file(self, python_parser: object) -> None:
        """[Hostile] A merged chunk must be text that **exists in the source**, not a splice.

        Totality is not enough to catch this and did not: it compares non-whitespace characters, so
        losing the blank run between two methods passes it while producing
        `... return 1clas s Beta:` — a chunk whose content never existed and which no reader could
        locate in the file.

        Found by mutating the fix and getting SILENT back. The assertion that catches it is
        containment, not accounting.
        """
        code = _getters(8)
        for budget in (60, 120, 400, 4000):
            for chunk in _chunks(python_parser, code, max_chars=budget):
                assert chunk.text in code, (budget, chunk.symbols, chunk.text[:60])

    def test_a_merged_chunk_keeps_what_sat_between_its_symbols(self, python_parser: object) -> None:
        """[Boundary] Said directly as well, because the containment check above would also pass if
        merging never happened. A comment between two merged methods travels with them."""
        code = (
            "class Bag:\n"
            "    def get_a(self):\n        return 1\n\n"
            "    # a note between them\n\n"
            "    def get_b(self):\n        return 2\n"
        )
        # 64 sits in a narrow window and both ends of it matter: the class weighs 70, so above
        # that nothing splits and nothing merges; below ~62 the two getters plus the comment no
        # longer fit together. A fixture outside that window passes while proving nothing, which
        # is how the visibility test in this file was vacuous until a mutant said so.
        merged = [c for c in _chunks(python_parser, code, max_chars=64) if len(c.symbols) > 1]
        assert merged, [c.symbols for c in _chunks(python_parser, code, max_chars=64)]
        assert all("a note between them" in c.text for c in merged)

    def test_the_same_input_gives_the_same_chunks(self, python_parser: object) -> None:
        """[Boundary] `NFR-4`. Greedy merging makes ordering load-bearing."""
        code = _getters(10)
        first = [(c.symbols, c.text) for c in _chunks(python_parser, code, max_chars=120)]
        second = [(c.symbols, c.text) for c in _chunks(python_parser, code, max_chars=120)]
        assert first == second

    def test_the_parser_is_asked_for_visibility_a_bounded_number_of_times(
        self, python_parser: object
    ) -> None:
        """[Boundary] `extract_symbol_visibility` re-parses the file on every call, so asking per
        symbol is O(N) parses of one file. The vocabulary is closed, so the bound is a constant
        rather than a guess."""
        calls: list[typing.Any] = []
        real = type(python_parser).list_symbols

        class _Counting:
            def __getattr__(self, item: str) -> typing.Any:
                return getattr(python_parser, item)

            def list_symbols(self, code: str, **kw: typing.Any) -> list[str]:
                calls.append(kw.get("visibility"))
                return real(python_parser, code, **kw)

        _chunks(_Counting(), _getters(30), max_chars=120)
        visibility_calls = [c for c in calls if c is not None]
        assert len(visibility_calls) <= 5, visibility_calls
