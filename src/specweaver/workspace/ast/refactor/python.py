# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which occurrences of a name are uses of one Python symbol, across a project.

Each occurrence is proven, unrelated, unsure or a text mention. Proven: the definition, an
import that resolves to it (also through a re-export), a bare name that resolves to it, a call
on `self` in its class or a subclass, a call on its class or its module. Unrelated: a name that
its own file binds to something else. Anything else in code is unsure.
"""

from __future__ import annotations

import keyword
from typing import TYPE_CHECKING

from specweaver.workspace.ast.refactor._family import ClassId, hierarchy, outside_bases
from specweaver.workspace.ast.refactor._model import Found, RenameRefusal, Spot

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from specweaver.workspace.ast.parsers.interfaces import (
        CodeStructureInterface,
        FileBindings,
        Reference,
    )

#: Bases that give a class no method a rename could stop overriding.
_HARMLESS_BASES = frozenset(
    {"object", "ABC", "abc.ABC", "Protocol", "typing.Protocol", "Generic", "typing.Generic"}
)
_ROOTS = ("", "src/")
_UNSURE = ("unknown", "free", "other")

#: `("def", file, name)` · `("module", file)` · `("external",)` · `("unknown",)` · `("free",)`
#: · `("other",)`
Resolved = tuple[str, ...]


def _parent_dir(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _join(directory: str, rest: str) -> str:
    return f"{directory}/{rest}" if directory else rest


class PythonResolver:
    """Resolves names across the Python files of one project."""

    def __init__(self, files: Mapping[str, str], parser: CodeStructureInterface) -> None:
        self._parser = parser
        self._code = {p: c for p, c in files.items() if p.endswith((".py", ".pyi"))}
        self._facts: dict[str, FileBindings] = {}
        self._symbols: dict[str, list[str]] = {}

    # --- files and modules ------------------------------------------------------------------

    def facts(self, path: str) -> FileBindings:
        if path not in self._facts:
            self._facts[path] = self._parser.file_bindings(self._code[path])
        return self._facts[path]

    def symbols(self, path: str) -> list[str]:
        if path not in self._symbols:
            self._symbols[path] = self._parser.list_symbols(self._code[path])
        return self._symbols[path]

    def _module_file(self, base: str) -> str | None:
        return next((c for c in (f"{base}.py", f"{base}/__init__.py") if c in self._code), None)

    def _is_project_package(self, dotted: str) -> bool:
        top = dotted.split(".")[0]
        return any(
            p == f"{root}{top}.py" or p.startswith(f"{root}{top}/")
            for root in _ROOTS
            for p in self._code
        )

    def resolve_module(self, module: str, from_file: str) -> Resolved:
        """The file a module name means, seen from `from_file`."""
        if module.startswith("."):
            return self._relative_module(module, from_file)
        for root in _ROOTS:
            target = self._module_file(root + module.replace(".", "/"))
            if target:
                return ("module", target)
        return ("unknown",) if self._is_project_package(module) else ("external",)

    def _relative_module(self, module: str, from_file: str) -> Resolved:
        rest = module.lstrip(".")
        directory = _parent_dir(from_file)
        for _ in range(len(module) - len(rest) - 1):
            if not directory:
                return ("unknown",)
            directory = _parent_dir(directory)
        base = _join(directory, rest.replace(".", "/")) if rest else directory
        target = self._module_file(base) if base else None
        return ("module", target) if target else ("unknown",)

    def _submodule(self, package_file: str, name: str) -> str | None:
        if not package_file.endswith("__init__.py"):
            return None
        return self._module_file(_join(_parent_dir(package_file), name))

    def resolve_name(
        self, path: str, local: str, seen: frozenset[tuple[str, str]] = frozenset()
    ) -> Resolved:
        """What the module-level name `local` of `path` stands for."""
        facts = self.facts(path)
        kinds = [local in facts.defs, local in facts.imports, local in facts.others]
        if (path, local) in seen or sum(kinds) > 1:
            return ("unknown",)
        if kinds[0]:
            return ("def", path, local)
        if kinds[1]:
            module, imported = facts.imports[local]
            found = self.resolve_module(module, path)
            if found[0] != "module" or imported is None:
                return found
            sub = self._submodule(found[1], imported)
            if sub:
                return ("module", sub)
            return self.resolve_name(found[1], imported, seen | {(path, local)})
        if kinds[2]:
            return ("other",)
        return ("unknown",) if facts.wildcards else ("free",)

    def resolve_dotted(self, path: str, text: str) -> Resolved:
        """What a module-level dotted name like `app.greeter.Greeter` stands for."""
        parts = text.split(".")
        if not all(p.isidentifier() for p in parts):
            return ("unknown",)
        found = self.resolve_name(path, parts[0])
        for part in parts[1:]:
            if found[0] != "module":
                return found if found[0] == "external" else ("unknown",)
            sub = self._submodule(found[1], part)
            found = ("module", sub) if sub else self.resolve_name(found[1], part)
        return found

    # --- classes -----------------------------------------------------------------------------

    def _parents(self) -> dict[ClassId, list[tuple[str, Resolved]]]:
        return {
            (p, cls): [(b, self.resolve_dotted(p, b)) for b in bases]
            for p in sorted(self._code)
            for cls, bases in self.facts(p).bases.items()
        }

    # --- the rename --------------------------------------------------------------------------

    def find(self, path: str, symbol_name: str, new_name: str) -> Found | RenameRefusal:
        name = self._target(path, symbol_name)
        if isinstance(name, RenameRefusal):
            return name
        old = name.rsplit(".", 1)[-1]
        refusal = _bad_new_name(old, new_name)
        if refusal:
            return refusal
        if "." in name:
            return self._find_method(path, name.split(".")[0], old)
        return self._collect(old, lambda p, r: self._top_level(path, old, p, r))

    def _target(self, path: str, symbol_name: str) -> str | RenameRefusal:
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
                f"only functions, methods and classes can be renamed; '{symbol_name}' is none of them in {path}"
            )
        if self._definitions(path, name) > 1:
            return RenameRefusal(f"'{name}' is defined more than once in {path}")
        if name.count(".") > 1:
            return RenameRefusal(
                f"'{name}' is nested; only top-level classes, their methods and functions rename"
            )
        short = name.rsplit(".", 1)[-1]
        if short.startswith("__") and short.endswith("__"):
            return RenameRefusal(f"'{short}' is a special method; Python calls it by that name")
        return name

    def _definitions(self, path: str, name: str) -> int:
        owner, _, short = name.rpartition(".")
        scope = "class" if owner else "module"
        return sum(
            1
            for r in self._parser.find_references(self._code[path], short)
            if r.kind == "definition" and r.scope == scope and (r.owner or "") == owner
        )

    def _collect(self, old: str, judge: Callable[[str, Reference], str]) -> Found:
        found = Found(old, {}, [], [])
        for p in sorted(self._code):
            for ref in self._parser.find_references(self._code[p], old):
                verdict = judge(p, ref)
                if verdict == "proven":
                    found.proven.setdefault(p, []).append((ref.start_byte, ref.end_byte))
                elif verdict == "unsure":
                    found.unsure.append(Spot(p, ref.line))
                elif verdict == "mention":
                    found.mentions.append(Spot(p, ref.line))
        return found

    def _top_level(self, home: str, old: str, p: str, ref: Reference) -> str:
        """The verdict on one occurrence of the top-level symbol `old` defined in `home`."""
        target: Resolved = ("def", home, old)
        if ref.kind == "definition":
            return "proven" if p == home and ref.scope == "module" else "unrelated"
        if ref.kind == "import":
            return self._in_module(self.resolve_module(ref.module or "", p), old, target)
        if ref.kind == "bare":
            return self._bare_top_level(home, p, ref, target)
        if ref.kind == "attribute":
            if ref.receiver_binding not in ("module_def", "import"):
                return "unsure"
            return self._in_module(self.resolve_dotted(p, ref.receiver or ""), old, target)
        return _common(ref)

    def _in_module(self, module: Resolved, old: str, target: Resolved) -> str:
        """The verdict on `old` read from `module`: an import from it, or `module.old`."""
        if module[0] != "module":
            return "unsure" if module[0] in _UNSURE else "unrelated"
        return _verdict(self.resolve_name(module[1], old), target)

    def _bare_top_level(self, home: str, p: str, ref: Reference, target: Resolved) -> str:
        if ref.binding == "module_def":
            return "proven" if p == home else "unrelated"
        if ref.binding == "import":
            return _verdict(self.resolve_name(p, _text_at(self._code[p], ref)), target)
        return "unrelated" if ref.binding in ("local", "class", "module_other") else "unsure"

    def _find_method(self, home: str, cls: str, old: str) -> Found | RenameRefusal:
        parents = self._parents()
        family = hierarchy(parents, (home, cls))
        outside = outside_bases(parents, family, _HARMLESS_BASES)
        if outside:
            return RenameRefusal(
                f"a class in the hierarchy of {cls} has a base outside the project "
                f"({', '.join(outside)}); renaming '{old}' could stop it overriding that base"
            )
        return self._collect(old, lambda p, r: self._method(family, p, r))

    def _method(self, family: set[ClassId], p: str, ref: Reference) -> str:
        """The verdict on one occurrence of the method's name; `family` is its override family."""
        if ref.kind == "definition":
            in_family = ref.scope == "class" and (p, ref.owner) in family
            return "proven" if in_family else "unrelated"
        if ref.kind == "bare":
            return "unsure" if ref.binding == "class" and (p, ref.owner) in family else "unrelated"
        if ref.kind == "attribute":
            return self._method_attribute(family, p, ref)
        if ref.kind in ("import", "scope_escape"):
            return "unrelated"
        return _common(ref)

    def _method_attribute(self, family: set[ClassId], p: str, ref: Reference) -> str:
        """The verdict on `receiver.<name>`: `self`, a class, or something unknown."""
        if ref.receiver in ("self", "cls"):
            return _member((p, ref.owner) if ref.owner else None, family)
        if ref.receiver_binding not in ("module_def", "import"):
            return "unsure"
        found = self.resolve_dotted(p, ref.receiver or "")
        if found[0] == "def":
            return _member((found[1], found[2]), family)
        return "unsure" if found[0] in _UNSURE else "unrelated"


def _member(cls: ClassId | None, family: set[ClassId]) -> str:
    if not cls:
        return "unsure"
    return "proven" if cls in family else "unrelated"


def _verdict(found: Resolved, target: Resolved) -> str:
    if found == target:
        return "proven"
    return "unsure" if found[0] in _UNSURE else "unrelated"


def _common(ref: Reference) -> str:
    if ref.kind == "text":
        return "mention"
    return "unrelated" if ref.kind == "keyword" else "unsure"


def _text_at(code: str, ref: Reference) -> str:
    return code.encode("utf-8")[ref.start_byte : ref.end_byte].decode("utf-8")


def _bad_new_name(old: str, new: str) -> RenameRefusal | None:
    if new == old:
        return RenameRefusal(f"the new name is '{old}' already; nothing to change")
    if not new.isidentifier() or keyword.iskeyword(new) or keyword.issoftkeyword(new):
        return RenameRefusal(f"'{new}' is not a free Python name")
    return None
