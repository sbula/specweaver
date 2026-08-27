# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How big a piece of source counts as, and how to make it smaller.

Split out of `chunking.py` on 2026-08-27, when that file passed the 600-line ceiling. The seam is
real rather than convenient: sizing answers *how much is this* and *cut it here*, and knows nothing
about symbols, layers or scope. Everything here is a pure function of a string.
"""

from __future__ import annotations


def weight(text: str) -> int:
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


def slice_long_line(line: str, max_chars: int) -> list[str]:
    """A single line, cut only if it alone exceeds the budget.

    Cutting mid-line produces a fragment that is not lexically whole, which is what this module
    exists to avoid — so it is the last resort **after** the last resort, and the ordinary path
    returns the line untouched.

    It is needed because a line boundary is not guaranteed to exist. A minified bundle or a
    single-line JSON has none, and before this a 800,000-character file came back as **one** chunk
    against a budget of 4,000. Whatever embeds that either fails or silently truncates. Found by a
    retrospective red/blue on 2026-08-26.
    """
    if weight(line) <= max_chars:
        return [line]
    return [line[at : at + max_chars] for at in range(0, len(line), max_chars)] or [line]


def emit_split(text: str, max_chars: int) -> list[str]:
    """Break oversized text on line boundaries, keeping every line.

    Splitting mid-line would produce a fragment that is not even lexically whole, which is the
    failure this module exists to avoid — just at a smaller scale.
    """
    parts: list[str] = []
    current = ""
    carried = 0
    for line in text.splitlines(keepends=True):
        for piece in slice_long_line(line, max_chars):
            piece_weight = weight(piece)
            if current and carried + piece_weight > max_chars:
                parts.append(current)
                current = ""
                carried = 0
            current += piece
            carried += piece_weight
    if current:
        parts.append(current)
    return parts or [text]
