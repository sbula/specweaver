# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Plan a rename across a project's files: the new content of each file, or a refusal.

A rename changes the definition and every proven use. One unsure use refuses the whole rename,
and names the spot. A name in a comment, a doc or a config file is reported, never changed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.workspace.ast.refactor._model import (
    MAX_SPOTS,
    RenamePlan,
    RenameRefusal,
    Spot,
    listing,
)
from specweaver.workspace.ast.refactor.python import PythonResolver

__all__ = ["MAX_SPOTS", "RenamePlan", "RenameRefusal", "Spot", "listing", "plan_rename"]

_PYTHON = (".py", ".pyi")

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface


def plan_rename(
    files: Mapping[str, str],
    path: str,
    symbol_name: str,
    new_name: str,
    parser: CodeStructureInterface,
) -> RenamePlan | RenameRefusal:
    """Rename `symbol_name` in `path` to `new_name`, across `files` (path → content)."""
    if not path.endswith(_PYTHON):
        return RenameRefusal(f"rename works on Python files only, not on {path}")
    if path not in files:
        return RenameRefusal(f"{path} is not a file of the project")

    found = PythonResolver(files, parser).find(path, symbol_name, new_name)
    if isinstance(found, RenameRefusal):
        return found
    if found.unsure:
        spots = sorted(set(found.unsure))
        return RenameRefusal(
            f"{len(spots)} unsure use(s) of '{found.old}'; nothing was changed: {listing(spots)}",
            spots,
        )
    changes = {p: _splice(files[p], spans, new_name) for p, spans in sorted(found.proven.items())}
    return _checked(files, changes, new_name, parser) or RenamePlan(
        changes, sorted(set(found.mentions) | set(_text_mentions(files, found.old)))
    )


def _splice(code: str, spans: list[tuple[int, int]], new_name: str) -> str:
    data = code.encode("utf-8")
    out, at = [], 0
    for start, end in sorted(set(spans)):
        out += [data[at:start], new_name.encode("utf-8")]
        at = end
    out.append(data[at:])
    return b"".join(out).decode("utf-8")


def _checked(
    files: Mapping[str, str], changes: dict[str, str], new_name: str, parser: CodeStructureInterface
) -> RenameRefusal | None:
    """A refusal when the new name is already used in a changed file, or a file stops parsing."""
    taken = sorted(
        Spot(p, r.line)
        for p in changes
        for r in parser.find_references(files[p], new_name)
        if r.kind != "text"
    )
    if taken:
        return RenameRefusal(
            f"'{new_name}' is already used in a file the rename changes: {listing(taken)}", taken
        )
    grammar = getattr(parser, "parser", None)
    if grammar is None:
        return None
    broken = [
        Spot(p, 1)
        for p, new in changes.items()
        if grammar.parse(new.encode("utf-8")).root_node.has_error
        and not grammar.parse(files[p].encode("utf-8")).root_node.has_error
    ]
    if broken:
        return RenameRefusal(
            f"the rename would leave files that do not parse: {listing(broken)}", broken
        )
    return None


def _text_mentions(files: Mapping[str, str], name: str) -> list[Spot]:
    word = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    return [
        Spot(p, n)
        for p, text in files.items()
        if not p.endswith(_PYTHON)
        for n, line in enumerate(text.splitlines(), start=1)
        if word.search(line)
    ]
