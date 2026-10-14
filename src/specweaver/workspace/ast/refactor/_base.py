# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What every language's resolver shares: its files, their facts, and collecting verdicts.

A resolver judges each occurrence of a name `proven`, `unrelated`, `unsure` or `mention`. A file
that does not parse may hide occurrences, so any such file that holds the name is unsure.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.workspace.ast.parsers.factory import get_default_parsers
from specweaver.workspace.ast.refactor._family import ClassId, Parents, hierarchy, outside_bases
from specweaver.workspace.ast.refactor._model import Found, RenameRefusal, Spot

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from specweaver.workspace.ast.parsers.interfaces import (
        CodeStructureInterface,
        FileBindings,
        Reference,
    )


def _parsers(
    given: CodeStructureInterface, suffixes: tuple[str, ...]
) -> dict[str, CodeStructureInterface]:
    """A parser per suffix: `given` where it is that language's parser, the default elsewhere."""
    chosen: dict[str, CodeStructureInterface] = {}
    for exts, default in get_default_parsers().items():
        parser = given if isinstance(given, type(default)) else default
        for ext in exts:
            if ext in suffixes:
                chosen[ext] = parser
    return chosen


class Resolver:
    """The files of one language family, and the verdicts on one name in them."""

    SUFFIXES: ClassVar[tuple[str, ...]] = ()

    def __init__(self, files: Mapping[str, str], parser: CodeStructureInterface) -> None:
        self._parsers = _parsers(parser, self.SUFFIXES)
        self.code = {p: c for p, c in files.items() if p.endswith(tuple(self._parsers))}
        self._facts: dict[str, FileBindings] = {}
        self._symbols: dict[str, list[str]] = {}

    def find(self, path: str, symbol_name: str, new_name: str) -> Found | RenameRefusal:
        raise NotImplementedError

    def parser_for(self, path: str) -> CodeStructureInterface:
        return next(p for ext, p in self._parsers.items() if path.endswith(ext))

    def facts(self, path: str) -> FileBindings:
        if path not in self._facts:
            self._facts[path] = self.parser_for(path).file_bindings(self.code[path])
        return self._facts[path]

    def symbols(self, path: str) -> list[str]:
        if path not in self._symbols:
            self._symbols[path] = self.parser_for(path).list_symbols(self.code[path])
        return self._symbols[path]

    def refs(self, path: str, name: str) -> list[Reference]:
        return self.parser_for(path).find_references(self.code[path], name)

    def pick(self, path: str, symbol_name: str) -> str | RenameRefusal:
        """`symbol_name` as `list_symbols` writes it: a bare method name gets its one class."""
        symbols = self.symbols(path)
        name = symbol_name
        if name not in symbols:
            matches = sorted({s for s in symbols if s.rsplit(".", 1)[-1] == name and "." in s})
            if len(matches) > 1:
                return RenameRefusal(
                    f"'{name}' is ambiguous: {', '.join(matches)}; name it with its class"
                )
            name = matches[0] if matches else name
        if name not in symbols:
            return RenameRefusal(
                f"only functions, methods and classes can be renamed; '{symbol_name}' is none "
                f"of them in {path}"
            )
        if self.definitions(path, name) > 1:
            return RenameRefusal(f"'{name}' is defined more than once in {path}")
        if name.count(".") > 1:
            return RenameRefusal(
                f"'{name}' is nested; only top-level classes, their methods and functions rename"
            )
        return name

    def start(
        self,
        path: str,
        symbol_name: str,
        new_name: str,
        valid: Callable[[str], bool],
        language: str,
    ) -> tuple[str, str] | RenameRefusal:
        """`(symbol as listed, its short name)`, or why the rename cannot start."""
        name = self.pick(path, symbol_name)
        if isinstance(name, RenameRefusal):
            return name
        old = name.rsplit(".", 1)[-1]
        if new_name == old:
            return RenameRefusal(f"the new name is '{old}' already; nothing to change")
        if not valid(new_name):
            return RenameRefusal(f"'{new_name}' is not a free {language} name")
        return name, old

    def family(
        self,
        home: str,
        cls: str,
        old: str,
        resolve: Callable[[str, str], tuple[str, ...]],
        harmless: frozenset[str],
    ) -> set[ClassId] | RenameRefusal:
        """The override family of `cls`, or a refusal when a class in it has an outside base."""
        parents: Parents = {
            (p, name): [(b, resolve(p, b)) for b in bases]
            for p in sorted(self.code)
            for name, bases in self.facts(p).bases.items()
        }
        members = hierarchy(parents, (home, cls))
        outside = outside_bases(parents, members, harmless)
        if outside:
            return RenameRefusal(
                f"a class in the hierarchy of {cls} has a base outside the project "
                f"({', '.join(outside)}); renaming '{old}' could stop it overriding that base"
            )
        return members

    def module_kind(self, path: str, local: str) -> str:
        """What binds `local` at the module level of `path`: `def`, `import`, `other`, `none`
        or, when more than one does, `conflict`."""
        facts = self.facts(path)
        kinds = [
            k
            for k, hit in (
                ("def", local in facts.defs),
                ("import", local in facts.imports),
                ("other", local in facts.others),
            )
            if hit
        ]
        if len(kinds) > 1:
            return "conflict"
        return kinds[0] if kinds else "none"

    def definitions(self, path: str, name: str) -> int:
        owner, _, short = name.rpartition(".")
        scope = "class" if owner else "module"
        return sum(
            1
            for r in self.refs(path, short)
            if r.kind == "definition" and r.scope == scope and (r.owner or "") == owner
        )

    def collect(self, old: str, judge: Callable[[str, Reference], str]) -> Found:
        found = Found(old, {}, self.broken(old), [])
        for p in sorted(self.code):
            for ref in self.refs(p, old):
                verdict = judge(p, ref)
                if verdict == "proven":
                    found.proven.setdefault(p, []).append((ref.start_byte, ref.end_byte))
                elif verdict == "unsure":
                    found.unsure.append(Spot(p, ref.line))
                elif verdict == "mention":
                    found.mentions.append(Spot(p, ref.line))
        return found

    def broken(self, old: str) -> list[Spot]:
        """The first line holding `old` in each file that does not parse."""
        pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])")
        spots = []
        for p in sorted(self.code):
            grammar = getattr(self.parser_for(p), "parser", None)
            if (
                grammar is None
                or not grammar.parse(self.code[p].encode("utf-8")).root_node.has_error
            ):
                continue
            lines = self.code[p].splitlines()
            line = next((n for n, text in enumerate(lines, start=1) if pattern.search(text)), None)
            if line is not None:
                spots.append(Spot(p, line))
        return spots


def verdict(found: tuple[str, ...], target: tuple[str, ...], unsure: tuple[str, ...]) -> str:
    """`proven` when `found` is the target; `unsure` when it is a kind in `unsure`."""
    if found == target:
        return "proven"
    return "unsure" if found[0] in unsure else "unrelated"


def common(ref: Reference, unrelated: tuple[str, ...]) -> str:
    """The verdict on a kind no language judges itself: a mention, or an unsure use."""
    if ref.kind == "text":
        return "mention"
    return "unrelated" if ref.kind in unrelated else "unsure"
