# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a chunk sits, so a reader can ask whether it is inside their own boundary.

Proves: B-SENS-03 FR-14

The filter that matters is not *"is this public"* but *"is this public **to me**"*. Inside a module
you must see its internals, because you are changing them; outside you must not, or you couple to
something free to change. That question needs two radii and a level, and none of them were on a
chunk.

**Two radii, because the two cases are different sizes.** A helper shared inside one package is
legitimately internal; another service's internals are a different question entirely, at a
different distance. One field cannot answer both.

**`unit` is `""` when the caller supplies no markers** `[agreed 2026-08-26]` — *not known*, rather
than falling back to `package`. A chunk claiming a unit boundary the caller never established would
answer *"is this outside my service?"* from a guess, which is the same failure as reporting
`public` for a language that has no such concept.
"""

from __future__ import annotations

import typing

import pytest

from specweaver.workspace.analyzers.chunking import chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers

MIXED = (
    "class Bag:\n"
    "    def get_a(self):\n        return 1\n"
    "    def __secret(self):\n        return 2\n"
)


@pytest.fixture(scope="module")
def python_parser() -> typing.Any:
    return next(v for k, v in get_default_parsers().items() if ".py" in k)


def _chunks(parser: typing.Any, code: str, path: str = "src/app/mod/thing.py", **kw: typing.Any):
    return chunk_source(code, path=path, parser=parser, language="python", **kw)


class TestChunkSourceLabelsThePackage:
    def test_the_package_is_the_chunks_directory(self, python_parser: typing.Any) -> None:
        """[Happy path] Java's package-private is literally this radius: the directory."""
        for chunk in _chunks(python_parser, MIXED):
            assert chunk.package == "src/app/mod"

    def test_a_file_at_the_root_has_an_empty_package(self, python_parser: typing.Any) -> None:
        """[Boundary] No directory, so nothing to claim."""
        for chunk in _chunks(python_parser, MIXED, path="thing.py"):
            assert chunk.package == ""

    def test_a_windows_path_is_split_too(self, python_parser: typing.Any) -> None:
        """[Hostile] `pathlib` is platform-dependent and this runs wherever a scan runs. A rule
        that only understood `/` would give a Windows chunk the whole path as its package."""
        for chunk in _chunks(python_parser, MIXED, path=r"C:\repo\app\mod\thing.py"):
            assert chunk.package == r"C:\repo\app\mod"


class TestChunkSourceLabelsTheUnit:
    def test_the_unit_is_the_nearest_marker_directory(self, python_parser: typing.Any) -> None:
        """[Happy path] The wider radius: a crate, a service, a build unit."""
        markers = frozenset({"src/app/pyproject.toml", "pyproject.toml"})
        for chunk in _chunks(python_parser, MIXED, markers=markers):
            assert chunk.unit == "src/app"

    def test_the_nearest_marker_wins_not_the_first(self, python_parser: typing.Any) -> None:
        """[Boundary] A repository root and a nested package both hold a manifest. The chunk
        belongs to the nested one — a rule taking any match would put every file in the repo root."""
        # The MARKER FILES are what gets sorted, not their directories -- and the fixture has to
        # make the outer one come first, or a rule taking the first match gets the right answer by
        # accident. `src/app/build.gradle` sorts before `src/app/mod/go.mod`, so first-match yields
        # `src/app` and longest-match yields `src/app/mod`.
        #
        # The first draft used `src/app/pyproject.toml`, which sorts AFTER `mod/go.mod`, so the
        # mutant produced the correct answer and came back SILENT. A comment in `_unit_of` claiming
        # otherwise was wrong too, and is corrected there.
        markers = frozenset({"pyproject.toml", "src/app/build.gradle", "src/app/mod/go.mod"})
        for chunk in _chunks(python_parser, MIXED, markers=markers):
            assert chunk.unit == "src/app/mod"

    def test_no_markers_means_not_known(self, python_parser: typing.Any) -> None:
        """[Hostile] **Not** a fallback to `package` `[agreed 2026-08-26]`.

        A chunk claiming a unit the caller never established answers *"is this outside my
        service?"* from a guess. Empty says *not known*, which a query-time filter can act on
        honestly.
        """
        for chunk in _chunks(python_parser, MIXED):
            assert chunk.unit == ""
            assert chunk.package != ""

    def test_a_marker_outside_this_path_is_ignored(self, python_parser: typing.Any) -> None:
        """[Hostile] A prefix match on strings would make `src/apple` a unit of `src/app/mod`."""
        markers = frozenset({"src/apple/pyproject.toml", "src/app-extra/pyproject.toml"})
        for chunk in _chunks(python_parser, MIXED, markers=markers):
            assert chunk.unit == ""

    def test_a_longer_sibling_directory_is_not_this_ones_unit(
        self, python_parser: typing.Any
    ) -> None:
        """[Hostile] The boundary in the other direction, and the case the first draft missed.

        A marker at `src/app` must not claim a file at `src/application/…`. The earlier fixture
        used `src/apple` against `src/app/mod`, where a bare-prefix match fails anyway — so the
        mutant that removed the separator check came back SILENT. The path has to be the longer of
        the two for the check to be doing anything.
        """
        markers = frozenset({"src/app/pyproject.toml"})
        chunks = _chunks(python_parser, MIXED, path="src/application/thing.py", markers=markers)
        assert chunks
        for chunk in chunks:
            assert chunk.unit == ""


class TestChunkSourceLabelsTheVisibility:
    def test_a_symbol_carries_its_level(self, python_parser: typing.Any) -> None:
        """[Happy path] The level `FR-1` computes, on the chunk that holds the symbol."""
        chunks = _chunks(python_parser, MIXED, max_chars=40)
        by_name = {n: c.visibility for c in chunks for n in c.symbols}

        # The budget has to force the class apart or there is one chunk named `Bag` and this
        # asserts nothing. `MIXED` weighs ~55 non-whitespace characters, so 60 was too generous --
        # the same vacuous-fixture trap a mutant caught in the FR-9 visibility test.
        assert "Bag.get_a" in by_name, [c.symbols for c in chunks]

        assert by_name["Bag.get_a"] == "public"
        assert by_name["Bag.__secret"] == "private"

    def test_a_merged_chunk_carries_the_level_its_members_share(
        self, python_parser: typing.Any
    ) -> None:
        """[Boundary] Its own assertion, because `FR-9`'s guard test passes either way.

        The guard proves members of different levels never merge. It does not prove the resulting
        chunk is *labelled* with the level they share — taking the first member's, or `unknown`,
        would satisfy every existing test.
        """
        code = "class Bag:\n" + "".join(
            f"    def get_{n}(self):\n        return {n}\n" for n in range(8)
        )
        merged = [c for c in _chunks(python_parser, code, max_chars=120) if len(c.symbols) > 1]
        assert merged
        assert all(c.visibility == "public" for c in merged)

    def test_a_gap_is_unknown(self, python_parser: typing.Any) -> None:
        """[Boundary] Text belonging to no symbol has no level to report."""
        code = '"""Doc."""\n\nimport os\n\n\ndef alpha():\n    return 1\n'
        preamble = next(c for c in _chunks(python_parser, code) if c.symbol == "<module>")
        assert preamble.visibility == "unknown"

    def test_visibility_is_unknown_when_the_parser_cannot_say(
        self, python_parser: typing.Any
    ) -> None:
        """[Hostile] The same fail-closed path the retrospective red/blue opened. A chunk must not
        claim a level derived from a lookup that never succeeded."""

        class _NoVisibility:
            def __getattr__(self, name: str) -> typing.Any:
                return getattr(python_parser, name)

            def list_symbols(self, code: str, **kw: typing.Any) -> list[str]:
                if kw.get("visibility") is not None:
                    raise RuntimeError("unavailable")
                return list(python_parser.list_symbols(code))

        chunks = _chunks(_NoVisibility(), MIXED, max_chars=40)
        assert chunks
        assert all(c.visibility == "unknown" for c in chunks)


class TestChunkSourceScopeKeepsItsGuarantees:
    def test_nothing_is_lost(self, python_parser: typing.Any) -> None:
        """[Boundary] `FR-17`. Labels are added; content is not touched."""
        # Body layer only: `FR-17` binds it, because a skeleton is a description and a
        # signature concatenated rather than a slice of the file.
        joined = "".join(
            c.text for c in _chunks(python_parser, MIXED, max_chars=40) if c.layer == "body"
        )
        assert "".join(joined.split()) == "".join(MIXED.split())

    def test_the_chunker_still_opens_no_file(self, python_parser: typing.Any) -> None:
        """[Boundary] `NFR-2`. `unit` is resolved from a marker set the caller supplies, never by
        walking a filesystem — the whole reason the parameter exists."""
        import builtins

        opened: list[str] = []
        real = builtins.open

        def _spy(*args: typing.Any, **kw: typing.Any) -> typing.Any:
            opened.append(str(args[0]))
            return real(*args, **kw)

        builtins.open = _spy
        try:
            _chunks(python_parser, MIXED, markers=frozenset({"src/app/pyproject.toml"}))
        finally:
            builtins.open = real
        assert opened == []
