# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A marked block in a text file: `<!-- sw:block <name> -->` … `<!-- sw:end <name> -->`.

One `bash` step fills a block's body; the worktree merge compares a file with its blocks emptied.
"""

from __future__ import annotations


def _markers(name: str) -> tuple[str, str]:
    return f"<!-- sw:block {name} -->", f"<!-- sw:end {name} -->"


def _span(text: str, name: str) -> tuple[int, int] | None:
    """Where the block's body lies: after its start marker, up to its end marker."""
    start, end = _markers(name)
    if text.count(start) != 1 or text.count(end) != 1:
        return None
    first, last = text.index(start) + len(start), text.index(end)
    return (first, last) if first <= last else None


def fill_block(text: str, name: str, body: str) -> str:
    """`text` with the body of block `name` replaced by `body`, on its own lines."""
    start, end = _markers(name)
    if start in body or end in body:
        msg = f"the output holds a marker of its own block ({start} or {end})"
        raise ValueError(msg)
    span = _span(text, name)
    if span is None:
        msg = f"needs one {start} and, after it, one {end}"
        raise ValueError(msg)
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = body.rstrip("\r\n").splitlines()
    inner = newline.join(lines) + newline if lines else ""
    return text[: span[0]] + newline + inner + text[span[1] :]


def outside_blocks(text: str, names: list[str]) -> str:
    """`text` with the named blocks' bodies emptied; a block without its markers is left as it is."""
    for name in names:
        span = _span(text, name)
        if span is not None:
            text = text[: span[0]] + text[span[1] :]
    return text
