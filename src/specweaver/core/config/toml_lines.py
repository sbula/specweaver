# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The line a key sits on in a TOML text.

Neither `tomllib` nor `tomlkit` reports where a key sits, so the line is found by scanning: the
deepest table header that is a prefix of the key path, then the line in that table whose key —
dotted or not — is the path or the nearest part of it, which covers inline tables, whose keys share
their parent's line. The inside of a multi-line string is never read as a key.
"""

from __future__ import annotations

import re

_HEADER = re.compile(r"^\s*\[+\s*(.+?)\s*\]+\s*(#.*)?$")
_PART = re.compile(r'"([^"]*)"|\'([^\']*)\'|([^.\s]+)')


def _header_parts(raw: str) -> tuple[str, ...]:
    return tuple(next(g for g in match.groups() if g is not None) for match in _PART.finditer(raw))


def line_of(text: str, *keys: str) -> int:
    """The line of the first of `keys` (dotted, as an error names them) found in `text`, else 1."""
    for key in keys:
        line = _find_line(text, _header_parts(key))
        if line is not None:
            return line
    return 1


def path_line(text: str, path: tuple[str, ...]) -> int:
    """The line of a key path in `text`, else 1."""
    return _find_line(text, path) or 1


def _find_line(text: str, path: tuple[str, ...]) -> int | None:
    """The line assigning `path`, else its deepest table's header; None when neither is there."""
    lines = _code_lines(text.splitlines())
    tables = _tables(lines)
    for start, parts in sorted(tables, key=lambda table: -len(table[1])):
        if path[: len(parts)] == parts:
            end = min((s for s, _ in tables if s > start), default=len(lines) + 1)
            assigned = _assignment_in(lines, start, end, path[len(parts) :])
            return assigned or (start if parts else None)
    return None


def _code_lines(lines: list[str]) -> list[str]:
    """`lines` with the inside of every multi-line string blanked, so it is never read as a key."""
    code: list[str] = []
    quote: str | None = None
    for line in lines:
        code.append("" if quote else line)
        for mark in ('"""', "'''"):
            if (quote is None or quote == mark) and line.count(mark) % 2:
                quote = None if quote else mark
    return code


def _tables(lines: list[str]) -> list[tuple[int, tuple[str, ...]]]:
    """Every table header as (line number, key parts); the top level is (0, ())."""
    tables: list[tuple[int, tuple[str, ...]]] = [(0, ())]
    for index, line in enumerate(lines):
        header = _HEADER.match(line)
        if header:
            tables.append((index + 1, _header_parts(header.group(1))))
    return tables


_ASSIGNED_KEY = re.compile(r"^\s*([^=#\[][^=]*?)\s*=")


def _assignment_in(lines: list[str], start: int, end: int, rest: tuple[str, ...]) -> int | None:
    """The line inside a table whose key, dotted or not, is `rest` or the nearest part of it."""
    best: tuple[int, int] | None = None
    for number in range(start + 1, end):
        found = _ASSIGNED_KEY.match(lines[number - 1])
        if not found:
            continue
        parts = _header_parts(found.group(1))
        if parts and rest[: len(parts)] == parts and (best is None or len(parts) > best[0]):
            best = (len(parts), number)
    return best[1] if best else None
