# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Source is split where it means something, not every N characters.

Proves: B-SENS-03 FR-1, B-SENS-03 FR-2, B-SENS-03 FR-3, B-SENS-03 FR-4, B-SENS-03 FR-5

Retrieval over a brownfield estate is only as good as its units. A fixed-size window cuts a
function in half, so the half that gets retrieved is missing its signature or its return, and the
model is asked to reason about a fragment that never existed as code. Splitting on AST boundaries
means every unit is a thing a developer would recognise.

The origin metadata is the other half of the job: a retrieved chunk that cannot say which file and
symbol it came from cannot be cited, and an agent that cannot cite cannot be checked.
"""

from __future__ import annotations

import pytest

from specweaver.workspace.analyzers.chunking import Chunk, chunk_source
from specweaver.workspace.ast.parsers.factory import get_default_parsers

SOURCE = '''"""Module docstring."""

import os


def alpha(x):
    return x + 1


class Beta:
    """A class."""

    def go(self):
        return 2
'''


@pytest.fixture
def python_parser() -> object:
    return next(v for k, v in get_default_parsers().items() if ".py" in k)


def _chunk(parser: object, code: str = SOURCE, **kwargs: object) -> list[Chunk]:
    return chunk_source(code, path="mod.py", parser=parser, language="python", **kwargs)


def test_each_top_level_symbol_becomes_its_own_chunk(python_parser: object) -> None:
    symbols = {c.symbol for c in _chunk(python_parser)}

    assert "alpha" in symbols
    assert "Beta" in symbols


def test_a_nested_symbol_does_not_become_a_second_chunk(python_parser: object) -> None:
    """`Beta.go` lives inside `Beta`. Emitting both would index the same lines twice and make a
    retrieval hit ambiguous about which unit it found."""
    symbols = [c.symbol for c in _chunk(python_parser)]

    assert "Beta.go" not in symbols


def test_a_chunk_holds_the_whole_symbol(python_parser: object) -> None:
    """FR-1. The point of the capability: never half a function."""
    alpha = next(c for c in _chunk(python_parser) if c.symbol == "alpha")

    assert "def alpha(x):" in alpha.text
    assert "return x + 1" in alpha.text


def test_every_chunk_names_its_origin(python_parser: object) -> None:
    """FR-2. A hit that cannot be cited cannot be checked."""
    for chunk in _chunk(python_parser):
        assert chunk.path == "mod.py"
        assert chunk.language == "python"
        assert chunk.symbol is not None


def test_the_preamble_is_kept(python_parser: object) -> None:
    """FR-5. Imports and the module docstring belong to no symbol and are exactly what tells a
    reader what the file depends on. Dropping them is the silent loss this checks for."""
    text = "\n".join(c.text for c in _chunk(python_parser))

    assert "import os" in text
    assert "Module docstring." in text


def test_no_chunk_is_empty(python_parser: object) -> None:
    """The control for FR-5: padding coverage with blank chunks would satisfy it dishonestly."""
    assert all(c.text.strip() for c in _chunk(python_parser))


def test_an_oversized_symbol_is_split_into_declared_parts(python_parser: object) -> None:
    """FR-3. A single function can exceed any window. It is split, and the split is visible."""
    body = "\n".join(f"    x = {i}" for i in range(400))
    code = f"def huge():\n{body}\n"

    chunks = [c for c in _chunk(python_parser, code, max_chars=500) if c.symbol == "huge"]

    assert len(chunks) > 1
    assert [c.part for c in chunks] == list(range(1, len(chunks) + 1))
    assert {c.parts for c in chunks} == {len(chunks)}


def test_a_split_symbol_loses_no_lines(python_parser: object) -> None:
    """FR-3's real requirement. Truncating would also produce "more than one chunk"."""
    body = "\n".join(f"    x = {i}" for i in range(400))
    code = f"def huge():\n{body}\n"

    rejoined = "".join(c.text for c in _chunk(python_parser, code, max_chars=500))

    assert "x = 0" in rejoined
    assert "x = 399" in rejoined


def test_a_symbol_that_fits_is_one_part(python_parser: object) -> None:
    """The control for FR-3. Splitting everything would defeat the whole capability."""
    alpha = next(c for c in _chunk(python_parser) if c.symbol == "alpha")

    assert (alpha.part, alpha.parts) == (1, 1)


def test_unparseable_source_still_yields_chunks(python_parser: object) -> None:
    """FR-4. Brownfield estates contain files no parser handles. Returning nothing would drop
    them from the index silently, which reads as *this code does not exist*."""
    chunks = _chunk(python_parser, "!!! this is not python at all !!!\n")

    assert chunks
    assert "not python" in "".join(c.text for c in chunks)


def test_a_file_with_no_symbols_is_still_indexed(python_parser: object) -> None:
    """A config-shaped or script-shaped file has content worth retrieving."""
    chunks = _chunk(python_parser, "TIMEOUT = 30\nRETRIES = 3\n")

    assert chunks
    assert "TIMEOUT = 30" in "".join(c.text for c in chunks)


def test_an_empty_file_yields_nothing(python_parser: object) -> None:
    """The control for FR-4: degradation must not invent content."""
    assert _chunk(python_parser, "   \n\n") == []


class _RaisingParser:
    """A parser that cannot read this file at all.

    Tree-sitter is error-tolerant: handed nonsense it returns no symbols rather than raising, so
    real garbage never reaches the fallback branch. A parser that genuinely fails — a missing
    grammar, a binary file, a language tier not installed — does raise, and only a stub can stand
    in for that.
    """

    def list_symbols(self, code: str) -> list[str]:
        raise RuntimeError("no grammar for this language")

    def extract_symbol(self, code: str, name: str) -> str:
        raise AssertionError("must not be reached once listing failed")


class _NestedFirstParser:
    """Reports a method before the class that contains it.

    Symbol order is the parser's business and differs by language. If the chunker trusted it, the
    method would be emitted first, its text consumed, and the whole enclosing class would then be
    skipped — the file would lose its largest unit and nothing would say so.
    """

    def list_symbols(self, code: str) -> list[str]:
        return ["Beta.go", "Beta", "alpha"]

    def extract_symbol(self, code: str, name: str) -> str:
        bodies = {
            "Beta.go": "    def go(self):\n        return 2",
            "Beta": 'class Beta:\n    """A class."""\n\n    def go(self):\n        return 2',
            "alpha": "def alpha(x):\n    return x + 1",
        }
        return bodies[name]


def test_a_parser_that_fails_outright_still_yields_the_file() -> None:
    """FR-4. The branch real garbage never reaches."""
    chunks = chunk_source(SOURCE, path="mod.py", parser=_RaisingParser(), language="python")

    assert chunks
    assert "def alpha(x):" in "".join(c.text for c in chunks)


def test_a_class_survives_a_parser_that_lists_its_method_first() -> None:
    """FR-1 under hostile ordering. Consuming the method first would drop the class entirely."""
    chunks = chunk_source(SOURCE, path="mod.py", parser=_NestedFirstParser(), language="python")

    assert "Beta" in {c.symbol for c in chunks}
    assert "Beta.go" not in {c.symbol for c in chunks}
