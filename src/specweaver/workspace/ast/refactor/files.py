# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Plan a file's creation or deletion.

A file is created only where nothing is, in a language with a parser, from code that parses. A
file is deleted only when nothing uses it: no import of it, no proven or unsure use of one of its
top-level symbols in another file. The refusal names those files.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.refactor._model import RenameRefusal, Spot
from specweaver.workspace.ast.refactor.move import new_path_refusal
from specweaver.workspace.ast.refactor.rename import resolver_for

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface
    from specweaver.workspace.ast.refactor._base import Resolver


@dataclass
class FilePlan:
    """The files to write, and the one to delete."""

    changes: dict[str, str] = field(default_factory=dict)
    delete: str | None = None


def _parser_for(path: str) -> CodeStructureInterface | None:
    suffix = posixpath.splitext(path)[1].lower()
    return next((p for exts, p in get_default_parsers().items() if suffix in exts), None)


def plan_create(
    files: Mapping[str, str], path: str, code: str, parser: CodeStructureInterface
) -> FilePlan | RenameRefusal:
    """Create `path` holding `code`. `parser` is used when it reads `path`'s language."""
    refusal = new_path_refusal(files, path)
    if refusal:
        return refusal
    default = _parser_for(path)
    if default is None:
        return RenameRefusal(f"no parser reads {path}; create it as a file of a known language")
    reader = parser if isinstance(parser, type(default)) else default
    grammar = getattr(reader, "parser", None)
    if grammar is not None and grammar.parse(code.encode("utf-8")).root_node.has_error:
        return RenameRefusal(f"the code for {path} does not parse")
    return FilePlan({posixpath.normpath(path): code})


def plan_delete(
    files: Mapping[str, str], path: str, parser: CodeStructureInterface
) -> FilePlan | RenameRefusal:
    """Delete `path` when no other file uses it."""
    if path not in files:
        return RenameRefusal(f"{path} is not a file of the project")
    kind = resolver_for(path)
    if kind is None:
        return RenameRefusal(
            f"deleting is not supported for {path}: no resolver can tell who uses it"
        )
    resolver = kind(files, parser)
    users = _importers(resolver, path) + _symbol_users(resolver, path)
    if users:
        spots = sorted(set(users))
        return RenameRefusal(f"{path} is still used; nothing was deleted", spots)
    return FilePlan(delete=path)


def _line_at(code: str, byte: int) -> int:
    return code.encode("utf-8")[:byte].count(b"\n") + 1


def _importers(resolver: Resolver, path: str) -> list[Spot]:
    """The imports a move of the file would rewrite: each one is a user."""
    folder, name = posixpath.split(path)
    stem, ext = posixpath.splitext(name)
    edits = resolver.move_edits(path, posixpath.join(folder, f"{stem}_unused_name{ext}"))
    if isinstance(edits, RenameRefusal):
        return [Spot(path, 1)]
    spots = [
        Spot(p, _line_at(resolver.code[p], start))
        for p, spans in edits.spans.items()
        if p != path
        for start, _, _ in spans
    ]
    return spots + [s for s in edits.unsure if s.path != path]


def _symbol_users(resolver: Resolver, path: str) -> list[Spot]:
    """Every proven or unsure use of one of the file's top-level symbols, outside the file."""
    spots: list[Spot] = []
    for symbol in sorted({s for s in resolver.symbols(path) if "." not in s}):
        users = getattr(resolver, "symbol_users", None)
        found = (
            users(path, symbol) if users else resolver.find(path, symbol, f"{symbol}_unused_name")
        )
        if isinstance(found, RenameRefusal):
            spots.append(Spot(path, 1))  # who uses it cannot be told, so it may be used
            continue
        spots += [s for s in found.unsure if s.path != path]
        spots += [
            Spot(p, _line_at(resolver.code[p], start))
            for p, spans in found.proven.items()
            if p != path
            for start, _ in spans
        ]
    return spots
