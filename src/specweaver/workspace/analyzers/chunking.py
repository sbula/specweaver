# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Splits source into units a developer would recognise, for retrieval over a large estate.

A fixed-size window cuts a function in half. Whichever half is retrieved is missing its signature
or its return, so the model reasons about a fragment that never existed as code. Splitting on AST
boundaries means every unit is a whole thing.

Each chunk carries where it came from, because a retrieved fragment that cannot name its file and
symbol cannot be cited, and an agent that cannot cite cannot be checked.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

#: Big enough to hold most real symbols whole, small enough that a chunk stays a useful retrieval
#: unit. Symbols above it are split rather than truncated.
_DEFAULT_MAX_CHARS = 4000


@dataclass(frozen=True)
class Chunk:
    """One retrievable unit, and enough provenance to cite it.

    `part`/`parts` are `1`/`1` for anything that fitted. They are not decoration: a reader given
    part 2 of 3 needs to know the unit continues, or they will read a mid-symbol fragment as the
    whole definition.
    """

    text: str
    path: str
    symbol: str
    language: str
    part: int = 1
    parts: int = 1


def _top_level(symbols: list[str]) -> list[str]:
    """Drop nested names — a method's text is already inside its class's chunk.

    Emitting both would index the same lines twice and leave a hit ambiguous about which unit it
    found.
    """
    return [name for name in symbols if "." not in name]


def _weight(text: str) -> int:
    """How much of `text` counts towards the budget: its non-whitespace characters.

    Counting every character let **indentation decide where code was cut**. Deeply nested Java and
    flat Python were judged by different standards for the same amount of code, and reformatting a
    file moved its chunk boundaries without a line of it changing — which, once anything is
    embedded, costs a re-index of the whole repository.

    cAST measures the same way, and for the same reason: consistency across coding styles and
    languages. The trade is that *raw* length is then unbounded; `NFR-3` states it rather than
    leaving it to be discovered.
    """
    return len("".join(text.split()))


def _split(text: str, max_chars: int) -> list[str]:
    """Break oversized text on line boundaries, keeping every line.

    Splitting mid-line would produce a fragment that is not even lexically whole, which is the
    failure this module exists to avoid — just at a smaller scale.
    """
    parts: list[str] = []
    current = ""
    weight = 0
    for line in text.splitlines(keepends=True):
        line_weight = _weight(line)
        if current and weight + line_weight > max_chars:
            parts.append(current)
            current = ""
            weight = 0
        current += line
        weight += line_weight
    if current:
        parts.append(current)
    return parts or [text]


def _emit(text: str, path: str, symbol: str, language: str, max_chars: int) -> list[Chunk]:
    if not text.strip():
        return []
    pieces = _split(text, max_chars)
    return [
        Chunk(
            text=piece,
            path=path,
            symbol=symbol,
            language=language,
            part=index,
            parts=len(pieces),
        )
        for index, piece in enumerate(pieces, start=1)
    ]


def chunk_source(
    code: str,
    *,
    path: str,
    parser: Any,
    language: str,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> list[Chunk]:
    """Split `code` into semantic chunks, falling back to line windows when it will not parse.

    A brownfield estate contains files no parser handles. Returning nothing for those would drop
    them from the index silently, which a reader cannot distinguish from *this code does not
    exist* — so unparseable content is still chunked, under an empty symbol name.

    Whatever belongs to no symbol — the module docstring, imports, top-level statements — is kept
    as a preamble chunk. It is usually the part that says what the file depends on.
    """
    try:
        symbols = _top_level(parser.list_symbols(code))
    except Exception:
        logger.debug("Chunking %s: symbol listing failed, falling back to line windows", path)
        symbols = []

    chunks: list[Chunk] = []
    remainder = code
    for name in symbols:
        try:
            body = parser.extract_symbol(code, name)
        except Exception:
            logger.debug("Chunking %s: could not extract %r, skipping", path, name)
            continue
        if not body.strip() or body not in remainder:
            continue
        head, _, remainder = remainder.partition(body)
        if head.strip():
            chunks.extend(_emit(head, path, "", language, max_chars))
        chunks.extend(_emit(body, path, name, language, max_chars))

    if remainder.strip():
        chunks.extend(_emit(remainder, path, "", language, max_chars))
    return chunks
