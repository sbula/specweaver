# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Plan a file's move: its new content at the new path, and every import of it rewritten.

All or none, as a rename: an import the language cannot rewrite for certain refuses the move
and names the spot. A move may not leave its `context.yaml` module. A doc line naming the old
path or module is reported, never changed.
"""

from __future__ import annotations

import posixpath
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from specweaver.workspace.ast.refactor._model import RenameRefusal, Spot
from specweaver.workspace.ast.refactor.rename import CODE_SUFFIXES, resolver_for

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface
    from specweaver.workspace.ast.refactor._base import Resolver

_PROTECTED = frozenset({"context.yaml", ".env", ".git", ".specweaver"})


@dataclass
class MovePlan:
    """The moved file's new path and content, every other changed file, and the mentions."""

    old_path: str
    new_path: str
    changes: dict[str, str]
    mentions: list[Spot] = field(default_factory=list)


def module_of_path(files: Mapping[str, str], path: str) -> str:
    """The folder of the nearest `context.yaml` above `path` (`""` for the root)."""
    folder = posixpath.dirname(path)
    while True:
        if posixpath.join(folder, "context.yaml") in files or (
            not folder and "context.yaml" in files
        ):
            return folder
        if not folder:
            return ""
        folder = posixpath.dirname(folder)


def new_path_refusal(files: Mapping[str, str], new_path: str) -> RenameRefusal | None:
    """Why a file cannot be written at `new_path`: outside the project, protected, or there."""
    normal = posixpath.normpath(new_path)
    if new_path.startswith("/") or normal.startswith("..") or ":" in new_path:
        return RenameRefusal(f"{new_path} is outside the project")
    if any(part in _PROTECTED for part in normal.split("/")):
        return RenameRefusal(f"{new_path} is protected")
    if normal in files:
        return RenameRefusal(f"{new_path} exists already")
    return None


def _target_refusal(files: Mapping[str, str], path: str, new_path: str) -> RenameRefusal | None:
    if path not in files:
        return RenameRefusal(f"{path} is not a file of the project")
    refusal = new_path_refusal(files, new_path)
    if refusal:
        return refusal
    normal = posixpath.normpath(new_path)
    if posixpath.splitext(path)[1] != posixpath.splitext(new_path)[1]:
        return RenameRefusal(f"{new_path} has another ending than {path}")
    if module_of_path(files, path) != module_of_path(files, normal):
        return RenameRefusal(f"{new_path} is in another module (another context.yaml) than {path}")
    return None


def plan_move(
    files: Mapping[str, str], path: str, new_path: str, parser: CodeStructureInterface
) -> MovePlan | RenameRefusal:
    """Move `path` to `new_path` across `files` (path → content)."""
    refusal = _target_refusal(files, path, new_path)
    if refusal:
        return refusal
    kind = resolver_for(path)
    if kind is None:
        return RenameRefusal(f"moving is not supported for {path}")
    resolver = kind(files, parser)
    new_path = posixpath.normpath(new_path)
    edits = resolver.move_edits(path, new_path)
    if isinstance(edits, RenameRefusal):
        return edits
    if edits.unsure:
        spots = sorted(set(edits.unsure))
        return RenameRefusal(
            f"{len(spots)} import(s) of {path} cannot be rewritten for certain; nothing was changed",
            spots,
        )
    changes = {p: _apply(files[p], spans) for p, spans in sorted(edits.spans.items()) if p != path}
    changes[new_path] = _apply(files[path], edits.spans.get(path, []))
    broken = [
        Spot(p, 1)
        for p, text in changes.items()
        if _newly_broken(resolver, p, files.get(p, files[path]), text, path)
    ]
    if broken:
        return RenameRefusal("the move would leave files that do not parse", broken)
    return MovePlan(
        path,
        new_path,
        dict(sorted(changes.items())),
        _mentions(files, [path, *resolver.module_names(path)]),
    )


def _apply(code: str, spans: list[tuple[int, int, str]]) -> str:
    data = code.encode("utf-8")
    out, at = [], 0
    for start, end, new in sorted(set(spans)):
        out += [data[at:start], new.encode("utf-8")]
        at = end
    out.append(data[at:])
    return b"".join(out).decode("utf-8")


def _newly_broken(resolver: Resolver, path: str, old: str, new: str, moved: str) -> bool:
    parser = resolver.parser_for(moved if path not in resolver.code else path)
    grammar = getattr(parser, "parser", None)
    if grammar is None:
        return False
    errors = [grammar.parse(t.encode("utf-8")).root_node.has_error for t in (old, new)]
    return errors == [False, True]


def _mentions(files: Mapping[str, str], names: list[str]) -> list[Spot]:
    patterns = [re.compile(rf"(?<![\w./]){re.escape(n)}(?![\w/])") for n in names if n]
    return sorted(
        Spot(p, n)
        for p, content in files.items()
        if not p.endswith(CODE_SUFFIXES)
        for n, line in enumerate(content.splitlines(), start=1)
        if any(pattern.search(line) for pattern in patterns)
    )
