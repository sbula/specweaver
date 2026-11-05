# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which project file or folder an import names: the one thing each language adds to the boundary check.

An import is given exactly as the language's parser lists it. A package file (`__init__.py`,
`mod.rs`, `lib.rs`, `index.ts`) and a Go import name their folder. An import that reaches nothing in
the project (a library, a missing file, a path out of the project) names None. Pure: it reads only
the `files` it is given.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING, Any

from specweaver.commons.languages import LANGUAGE_SUFFIXES, language_of
from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.refactor.rename import resolver_for

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

_PACKAGE_FILES = frozenset(
    {
        "__init__.py",
        "mod.rs",
        "lib.rs",
        "main.rs",
        *(f"index{s}" for s in (".ts", ".tsx", ".js", ".jsx")),
    }
)
_SCRIPT_SUFFIXES = (*LANGUAGE_SUFFIXES["typescript"], ".d.ts", *LANGUAGE_SUFFIXES["javascript"])
_INCLUDE = re.compile(r'#include\s*"([^"]+)"')


def _named(path: str) -> str:
    """A package file names its folder; any other file names itself."""
    return posixpath.dirname(path) if posixpath.basename(path) in _PACKAGE_FILES else path


def _python(resolver: Any, path: str, written: str) -> str | None:
    found = resolver.resolve_module(written, path)
    return _named(found[1]) if found[0] == "module" else None


def _jvm(resolver: Any, path: str, written: str) -> str | None:
    """A type, a type's static member, or a package (`.*`, or a type the package lacks)."""
    name = written.removesuffix(".*")
    for candidate in (name, name.rpartition(".")[0]):
        found: tuple[str, ...] = resolver.resolve_text(path, candidate) if candidate else ()
        if found[:1] == ("def",):
            return found[1]
    package = name if written.endswith(".*") else name.rpartition(".")[0]
    folders = {posixpath.dirname(p) for p in resolver.code if resolver.facts(p).package == package}
    return _nearest(folders, path)


def _nearest(folders: set[str], path: str) -> str | None:
    """The folder sharing the longest path prefix with `path` (main beside main, tests beside
    tests), or None when two are equally near."""
    shared = {f: len(posixpath.commonpath([f, path]).split("/")) for f in folders}
    best = max(shared.values(), default=0)
    nearest = [f for f, n in shared.items() if n == best]
    return nearest[0] if len(nearest) == 1 else None


def _rust(resolver: Any, path: str, written: str) -> str | None:
    segments = written.split(" as ")[0].removesuffix("::*").split("::")
    found = resolver.resolve_path(path, segments)
    if found[0] == "def":
        return _named(found[1])
    if found[0] == "module":
        file = resolver.module_file(found[1], found[2])
        return _named(file) if file else None
    return None


def _go(resolver: Any, path: str, written: str) -> str | None:
    # The module root itself names the project root, which is no folder a rule can name.
    return resolver.import_dir(written) or None


def _c(resolver: Any, path: str, written: str) -> str | None:
    quoted = _INCLUDE.fullmatch(written.strip())
    found: str | None = resolver.include(path, quoted.group(1)) if quoted else None
    return found


#: How each language's resolver answers; the resolver is the one that renames the language's files.
_PICK: dict[str, Callable[[Any, str, str], str | None]] = {
    "python": _python,
    "java": _jvm,
    "kotlin": _jvm,
    "rust": _rust,
    "go": _go,
    "c": _c,
    "cpp": _c,
}


def _script_target(code: set[str], path: str, written: str) -> str | None:
    """A relative specifier: the file itself, the file with a script ending, or a folder's index."""
    if not written.startswith("."):
        return None
    # Only project files are candidates, so a path that climbs out of the project matches none.
    base = posixpath.normpath(posixpath.join(posixpath.dirname(path), written))
    if base in code:
        return base
    stem = re.sub(r"\.[mc]?jsx?$", "", base)
    for candidate, named in (
        *((f"{stem}{s}", f"{stem}{s}") for s in _SCRIPT_SUFFIXES),
        *((f"{stem}/index{s}", stem) for s in _SCRIPT_SUFFIXES),
    ):
        if candidate in code:
            return named
    return None


def _scripts(files: Mapping[str, str]) -> Callable[[str, str], str | None]:
    """TypeScript and JavaScript as one family: a `.ts` file may import a real `.js` file."""
    code = {p for p in files if p.endswith(_SCRIPT_SUFFIXES)}
    return lambda path, written: _script_target(code, path, written)


def targets_for(files: Mapping[str, str], language: str) -> Callable[[str, str], str | None] | None:
    """`target(path, written)` for every file of `language` in `files`, or None for no such language.

    Built once per project and language: a resolver reads all of the language's files.
    """
    if language in ("typescript", "javascript"):
        return _scripts(files)
    pick = _PICK.get(language)
    if pick is None:
        return None
    suffix = LANGUAGE_SUFFIXES[language][0]
    resolver_class = resolver_for(f"x{suffix}")
    parser = next(p for exts, p in get_default_parsers().items() if suffix in exts)
    resolver = resolver_class(files, parser) if resolver_class else None
    return lambda path, written: pick(resolver, path, written)


def import_target(files: Mapping[str, str], path: str, written: str) -> str | None:
    """The project file or folder the import `written` in `path` names, or None."""
    language = language_of(path)
    target = targets_for(files, language) if language else None
    return target(path, written) if target else None
