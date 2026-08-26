# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Properties the chunker must hold whatever language it is pointed at.

Proves: B-SENS-03 NFR-1, B-SENS-03 NFR-2, B-SENS-03 NFR-4, B-SENS-03 FR-17

**The numbers under this tag moved on 2026-08-26 and the claims did not.** `NFR-2` used to mean
*Total* and now means *Pure*; `NFR-3` used to mean *Pure* and now means *Budget*. So totality — every
non-blank character survives — is `FR-17`, purity is `NFR-2`, and determinism is `NFR-4`. Polyglot
is still `NFR-1`.

Left as it was, this file claimed the chunker proves a **budget** it does not measure.

These are the three claims the design makes about the module rather than about one behaviour, and
each is the kind that quietly stops being true. Polyglot support decays the moment a language
special case is added; totality decays the moment a branch forgets to emit its remainder; purity
decays the moment someone reaches for the file the text came from.
"""

from __future__ import annotations

import builtins
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pytest

from specweaver.workspace.analyzers.chunking import chunk_source

SOURCE = '''"""Header."""

import os

CONST = 1


def alpha(x):
    return x + 1


class Beta:
    def go(self):
        return 2
'''


class _MinimalParser:
    """Implements the whole surface the chunker is allowed to need, and nothing else.

    If the module ever reaches for `extract_skeleton`, a language table or a file extension, this
    raises `AttributeError` and the polyglot claim is measurably false.

    **The surface grew on 2026-08-26.** `FR-9` may not merge across a visibility level, so the
    chunker now asks `list_symbols(visibility=[level])` as well. That is the same method with an
    argument the interface already declares, not a new dependency — but a stub that did not accept
    it fell into the chunker's `except Exception` and reported every symbol as `unknown`, which
    merged everything. A degradation that silent is worth a stub that says so.
    """

    def list_symbols(self, code: str, visibility: list[str] | None = None) -> list[str]:
        if visibility is not None:
            return ["alpha", "Beta"] if "public" in visibility else []
        return ["alpha", "Beta"]

    def extract_symbol(self, code: str, name: str) -> str:
        bodies = {
            "alpha": "def alpha(x):\n    return x + 1",
            "Beta": "class Beta:\n    def go(self):\n        return 2",
        }
        return bodies[name]


def test_two_methods_are_the_whole_parser_contract() -> None:
    """NFR-1. Any installed language tier works without per-language code here."""
    chunks = chunk_source(SOURCE, path="m.x", parser=_MinimalParser(), language="whatever")

    assert {name for c in chunks for name in c.symbols} >= {"alpha", "Beta"}


def test_every_non_blank_character_survives() -> None:
    """NFR-2. Totality, stated as the thing that would actually be lost.

    Comparing whitespace-stripped text catches a dropped preamble, a dropped remainder and a
    truncated split at once — the three ways content has gone missing here.
    """
    chunks = chunk_source(SOURCE, path="m.x", parser=_MinimalParser(), language="whatever")

    rejoined = "".join(c.text for c in chunks)

    assert "".join(rejoined.split()) == "".join(SOURCE.split())


def test_totality_holds_when_a_symbol_is_split() -> None:
    """The harder half of NFR-2: splitting is where losing a line is easiest."""
    body = "\n".join(f"    x = {i}" for i in range(300))
    code = f"def huge():\n{body}\n"

    class _One:
        def list_symbols(self, c: str) -> list[str]:
            return ["huge"]

        def extract_symbol(self, c: str, n: str) -> str:
            return code.rstrip("\n")

    rejoined = "".join(
        c.text for c in chunk_source(code, path="m.x", parser=_One(), language="x", max_chars=400)
    )

    assert "".join(rejoined.split()) == "".join(code.split())


def test_the_chunker_never_opens_a_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-3. It is handed text and a path *string*; the path is a label, not a thing to read.

    Reaching for the file would make chunking fail on unsaved buffers and on content that never
    had a file — and would put I/O in a module the architecture keeps pure.
    """

    def _refuse(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("chunking opened a file")

    monkeypatch.setattr(builtins, "open", _refuse)

    assert chunk_source(SOURCE, path="m.x", parser=_MinimalParser(), language="x")


def test_the_same_input_gives_the_same_chunks() -> None:
    """NFR-3's other half: no clock, no randomness, no accumulated state between calls."""
    first = chunk_source(SOURCE, path="m.x", parser=_MinimalParser(), language="x")
    second = chunk_source(SOURCE, path="m.x", parser=_MinimalParser(), language="x")

    assert first == second
