# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Plan a rename across a project's files: the new content of each file, or a refusal.

A rename changes the definition and every proven use. One unsure use refuses the whole rename,
and names the spot. A name in a comment, a doc or a config file is reported, never changed.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from specweaver.commons.languages import LANGUAGE_SUFFIXES
from specweaver.workspace.ast.refactor._model import (
    MAX_SPOTS,
    RenamePlan,
    RenameRefusal,
    Spot,
    listing,
)
from specweaver.workspace.ast.refactor.c_family import CppResolver, CResolver
from specweaver.workspace.ast.refactor.go import GoResolver
from specweaver.workspace.ast.refactor.jvm import JvmResolver
from specweaver.workspace.ast.refactor.python import PythonResolver
from specweaver.workspace.ast.refactor.rust import RustResolver
from specweaver.workspace.ast.refactor.typescript import TypeScriptResolver

__all__ = [
    "CODE_SUFFIXES",
    "MAX_SPOTS",
    "RenamePlan",
    "RenameRefusal",
    "Spot",
    "family_of",
    "listing",
    "plan_rename",
    "resolver_for",
]

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface
    from specweaver.workspace.ast.refactor._base import Resolver

_BY_LANGUAGE: dict[str, type[Resolver]] = {
    "python": PythonResolver,
    "java": JvmResolver,
    "kotlin": JvmResolver,
    "typescript": TypeScriptResolver,
    "rust": RustResolver,
    "go": GoResolver,
    "c": CResolver,
    "cpp": CppResolver,
}

#: Which resolver renames a symbol defined in a file with this ending.
_RESOLVERS: dict[str, type[Resolver]] = {
    suffix: resolver
    for language, resolver in _BY_LANGUAGE.items()
    for suffix in LANGUAGE_SUFFIXES[language]
}

#: Endings of source code; every other file is text, where a name is only ever a mention.
CODE_SUFFIXES = (*(s for suffixes in LANGUAGE_SUFFIXES.values() for s in suffixes), ".sql")


def resolver_for(path: str) -> type[Resolver] | None:
    """The resolver for a file with this ending, or None when the language has none."""
    return next((r for ext, r in _RESOLVERS.items() if path.endswith(ext)), None)


def family_of(path: str) -> tuple[str, ...]:
    """The endings searched when renaming a symbol of `path`: its language and its partners."""
    resolver = resolver_for(path)
    return resolver.SUFFIXES if resolver else ()


def plan_rename(
    files: Mapping[str, str],
    path: str,
    symbol_name: str,
    new_name: str,
    parser: CodeStructureInterface,
) -> RenamePlan | RenameRefusal:
    """Rename `symbol_name` in `path` to `new_name`, across `files` (path → content)."""
    kind = resolver_for(path)
    if kind is None:
        return RenameRefusal(f"rename is not supported for {path}")
    if path not in files:
        return RenameRefusal(f"{path} is not a file of the project")

    resolver = kind(files, parser)
    found = resolver.find(path, symbol_name, new_name)
    if isinstance(found, RenameRefusal):
        return found
    if found.unsure:
        spots = sorted(set(found.unsure))
        return RenameRefusal(
            f"{len(spots)} unsure use(s) of '{found.old}'; nothing was changed",
            spots,
        )
    changes = {p: _splice(files[p], spans, new_name) for p, spans in sorted(found.proven.items())}
    return _checked(files, changes, new_name, resolver) or RenamePlan(
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
    files: Mapping[str, str], changes: dict[str, str], new_name: str, resolver: Resolver
) -> RenameRefusal | None:
    """A refusal when the new name is already used in a changed file, or a file stops parsing."""
    taken = sorted(
        Spot(p, r.line)
        for p in changes
        for r in resolver.parser_for(p).find_references(files[p], new_name)
        if r.kind != "text"
    )
    if taken:
        return RenameRefusal(f"'{new_name}' is already used in a file the rename changes", taken)
    broken = [Spot(p, 1) for p, new in changes.items() if _newly_broken(resolver, p, files[p], new)]
    if broken:
        return RenameRefusal("the rename would leave files that do not parse", broken)
    return None


def _newly_broken(resolver: Resolver, path: str, old: str, new: str) -> bool:
    grammar = getattr(resolver.parser_for(path), "parser", None)
    if grammar is None:
        return False
    errors = [grammar.parse(t.encode("utf-8")).root_node.has_error for t in (old, new)]
    return errors == [False, True]


def _text_mentions(files: Mapping[str, str], name: str) -> list[Spot]:
    word = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    return [
        Spot(p, n)
        for p, text in files.items()
        if not p.endswith(CODE_SUFFIXES)
        for n, line in enumerate(text.splitlines(), start=1)
        if word.search(line)
    ]
