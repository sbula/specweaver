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


def _parent_of(name: str, texts: dict[str, str]) -> str | None:
    """The symbol this one is nested in, or None when it stands on its own.

    **Containment decides.** A symbol is nested when its text lies inside another symbol's, and the
    parent is the smallest such symbol — which is what "nested" means in a tree.

    A dot decides nothing, and cannot. `FR-7` made `public.orders` a top-level SQL object whose
    name contains one; the rule this replaces — *drop every name with a dot* — dropped every
    qualified table and function in an estate from the index. And scoped names go only one level
    deep: Python reports a nested class's method as `Inner.deep_0`, never
    `Outer.Inner.deep_0`, so at depth two the name has no prefix that is a symbol at all. The
    dotted prefix is kept only as a **fast path** for the common single-level case; containment is
    the rule behind it and answers both.
    """
    body = texts.get(name, "")
    if not body:
        return None

    prefix, dot, _ = name.rpartition(".")
    if dot and prefix in texts and body in texts[prefix]:
        return prefix

    smallest: str | None = None
    for other, other_body in texts.items():
        if other == name or len(other_body) <= len(body) or body not in other_body:
            continue
        if smallest is None or len(other_body) < len(texts[smallest]):
            smallest = other
    return smallest


def _children_of(parent: str, order: list[str], parents: dict[str, str | None]) -> list[str]:
    """The symbols nested directly in `parent`, in source order."""
    return [name for name in order if parents.get(name) == parent]


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


@dataclass(frozen=True)
class _Cut:
    """Everything a cut needs to know about the file it is cutting.

    Bundled because `_walk` and `_emit_unit` are mutually recursive and would otherwise pass six
    arguments back and forth at every level, which is how the two loops came to be written out
    twice in the first place.
    """

    path: str
    language: str
    max_chars: int
    texts: dict[str, str]
    order: list[str]
    parents: dict[str, str | None]


def _walk(text: str, names: list[str], cut: _Cut) -> list[Chunk]:
    """Cut `text` at each of `names`, in source order, losing nothing between them.

    The file and a class are the same problem at two scales — a run of symbols with text around
    them — so this is written once and used by both. Whatever sits between the symbols is emitted
    **unnamed**: it belongs to no symbol, and naming it after the container would put the container
    in the index beside its own members.
    """
    chunks: list[Chunk] = []
    remainder = text
    for name in names:
        body = cut.texts.get(name, "")
        if not body.strip() or body not in remainder:
            continue
        head, _, remainder = remainder.partition(body)
        if head.strip():
            chunks.extend(_emit(head, cut.path, "", cut.language, cut.max_chars))
        chunks.extend(_emit_unit(body, name, cut))
    if remainder.strip():
        chunks.extend(_emit(remainder, cut.path, "", cut.language, cut.max_chars))
    return chunks


def _emit_unit(text: str, name: str, cut: _Cut) -> list[Chunk]:
    """One symbol, cut on structure while it can be and on lines only when it cannot.

    The recursion terminates by construction: each child's text is strictly shorter than its
    parent's, and a symbol with no children falls through to the line split.
    """
    if _weight(text) <= cut.max_chars:
        return _emit(text, cut.path, name, cut.language, cut.max_chars)

    children = _children_of(name, cut.order, cut.parents)
    if not children:
        return _emit(text, cut.path, name, cut.language, cut.max_chars)  # FR-10: the last resort

    return _walk(text, children, cut)


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
        order = parser.list_symbols(code)
    except Exception:
        logger.debug("Chunking %s: symbol listing failed, falling back to line windows", path)
        order = []

    texts: dict[str, str] = {}
    for name in order:
        try:
            texts[name] = parser.extract_symbol(code, name)
        except Exception:
            logger.debug("Chunking %s: could not extract %r, skipping", path, name)

    parents = {name: _parent_of(name, texts) for name in order}
    cut = _Cut(path, language, max_chars, texts, order, parents)
    return _walk(code, [n for n in order if parents[n] is None], cut)
