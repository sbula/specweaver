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
from typing import TYPE_CHECKING, ClassVar

from specweaver.workspace.ast.refactor import moves
from specweaver.workspace.ast.refactor._base import Resolver, common, verdict
from specweaver.workspace.ast.refactor._model import Edits, Found, RenameRefusal

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import (
        Reference,
    )
    from specweaver.workspace.ast.refactor._family import ClassId

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


class PythonResolver(Resolver):
    """Resolves names across the Python files of one project."""

    SUFFIXES: ClassVar[tuple[str, ...]] = (".py",)

    # --- files and modules ------------------------------------------------------------------

    def move_edits(self, path: str, new_path: str) -> Edits | RenameRefusal:
        return moves.python_edits(self, path, new_path)

    def module_names(self, path: str) -> list[str]:
        return list(moves.python_dotted(path).values())

    def _module_file(self, base: str) -> str | None:
        return next((c for c in (f"{base}.py", f"{base}/__init__.py") if c in self.code), None)

    def _is_project_package(self, dotted: str) -> bool:
        top = dotted.split(".")[0]
        return any(
            p == f"{root}{top}.py" or p.startswith(f"{root}{top}/")
            for root in _ROOTS
            for p in self.code
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
        kind = self.module_kind(path, local)
        if (path, local) in seen or kind == "conflict":
            return ("unknown",)
        if kind == "def":
            return ("def", path, local)
        if kind == "import":
            module, imported = self.facts(path).imports[local]
            found = self.resolve_module(module, path)
            if found[0] != "module" or imported is None:
                return found
            sub = self._submodule(found[1], imported)
            if sub:
                return ("module", sub)
            return self.resolve_name(found[1], imported, seen | {(path, local)})
        if kind == "other":
            return ("other",)
        return ("unknown",) if self.facts(path).wildcards else ("free",)

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
        return self.collect(old, lambda p, r: self._top_level(path, old, p, r))

    def _target(self, path: str, symbol_name: str) -> str | RenameRefusal:
        name = self.pick(path, symbol_name)
        if isinstance(name, RenameRefusal):
            return name
        short = name.rsplit(".", 1)[-1]
        if short.startswith("__") and short.endswith("__"):
            return RenameRefusal(f"'{short}' is a special method; Python calls it by that name")
        return name

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
        return common(ref, ("keyword",))

    def _in_module(self, module: Resolved, old: str, target: Resolved) -> str:
        """The verdict on `old` read from `module`: an import from it, or `module.old`."""
        if module[0] != "module":
            return "unsure" if module[0] in _UNSURE else "unrelated"
        return verdict(self.resolve_name(module[1], old), target, _UNSURE)

    def _bare_top_level(self, home: str, p: str, ref: Reference, target: Resolved) -> str:
        if ref.binding == "module_def":
            return "proven" if p == home else "unrelated"
        if ref.binding == "import":
            return verdict(self.resolve_name(p, _text_at(self.code[p], ref)), target, _UNSURE)
        return "unrelated" if ref.binding in ("local", "class", "module_other") else "unsure"

    def _find_method(self, home: str, cls: str, old: str) -> Found | RenameRefusal:
        family = self.family(home, cls, old, self.resolve_dotted, _HARMLESS_BASES)
        if isinstance(family, RenameRefusal):
            return family
        return self.collect(old, lambda p, r: self._method(family, p, r))

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
        return common(ref, ("keyword",))

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


def _text_at(code: str, ref: Reference) -> str:
    return code.encode("utf-8")[ref.start_byte : ref.end_byte].decode("utf-8")


def _bad_new_name(old: str, new: str) -> RenameRefusal | None:
    if new == old:
        return RenameRefusal(f"the new name is '{old}' already; nothing to change")
    if not new.isidentifier() or keyword.iskeyword(new) or keyword.issoftkeyword(new):
        return RenameRefusal(f"'{new}' is not a free Python name")
    return None
