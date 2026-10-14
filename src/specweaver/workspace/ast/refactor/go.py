# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which occurrences of a name are uses of one Go symbol, across a module.

A package is a folder (and its `package` clause): a bare name is proven anywhere in its own
package, and `pkg.Name` through an import that `go.mod` resolves to that folder. A method is
proven through its own receiver variable or a method expression on its type. Go matches
interfaces by name alone, so a method any interface of the project declares, or one with a
standard library interface's name, refuses.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.workspace.ast.refactor._base import Resolver, common
from specweaver.workspace.ast.refactor._model import Found, RenameRefusal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface, Reference

#: Method names standard library interfaces call; renaming one silently drops the interface.
STANDARD_METHODS = frozenset(
    {
        "String",
        "Error",
        "Read",
        "Write",
        "Close",
        "ServeHTTP",
        "Len",
        "Less",
        "Swap",
        "MarshalJSON",
        "UnmarshalJSON",
    }
)
_KEYWORDS = frozenset(
    [
        "break",
        "case",
        "chan",
        "const",
        "continue",
        "default",
        "defer",
        "else",
        "fallthrough",
        "for",
        "func",
        "go",
        "goto",
        "if",
        "import",
        "interface",
        "map",
        "package",
        "range",
        "return",
        "select",
        "struct",
        "switch",
        "type",
        "var",
    ]
)


class GoResolver(Resolver):
    """Resolves function, type and method names across the Go packages of one project."""

    SUFFIXES: ClassVar[tuple[str, ...]] = (".go",)

    def __init__(self, files: Mapping[str, str], parser: CodeStructureInterface) -> None:
        super().__init__(files, parser)
        self._modules = {}
        for p, content in files.items():
            if posixpath.basename(p) == "go.mod":
                match = re.search(r"^module\s+(\S+)", content, re.M)
                if match:
                    self._modules[posixpath.dirname(p)] = match.group(1)

    # --- packages ----------------------------------------------------------------------------

    def package_of(self, path: str) -> tuple[str, str]:
        return posixpath.dirname(path), self.facts(path).package

    def import_dir(self, import_path: str) -> str | None:
        """The folder an import path names, when a `go.mod` of the project covers it."""
        for folder, module in self._modules.items():
            if import_path == module:
                return folder
            if import_path.startswith(f"{module}/"):
                return (
                    posixpath.join(folder, import_path[len(module) + 1 :])
                    if folder
                    else import_path[len(module) + 1 :]
                )
        return None

    def _package_name(self, folder: str) -> str | None:
        return next(
            (
                self.facts(p).package
                for p in sorted(self.code)
                if posixpath.dirname(p) == folder and not p.endswith("_test.go")
            ),
            None,
        )

    def aliases(self, path: str) -> dict[str, str | None]:
        """Each name `path` reaches a package by, and the package's folder (None outside)."""
        names: dict[str, str | None] = {}
        for local, (import_path, flag) in self.facts(path).imports.items():
            folder = self.import_dir(import_path)
            name = local
            if flag is None and folder is not None:
                name = self._package_name(folder) or local
            names[name] = folder
        return names

    # --- the rename --------------------------------------------------------------------------

    def find(self, path: str, symbol_name: str, new_name: str) -> Found | RenameRefusal:
        started = self.start(
            path,
            symbol_name,
            new_name,
            lambda n: bool(re.fullmatch(r"[A-Za-z_]\w*", n)) and n not in _KEYWORDS,
            "Go",
        )
        if isinstance(started, RenameRefusal):
            return started
        name, old = started
        if old[:1].isupper() != new_name[:1].isupper():
            return RenameRefusal(f"renaming '{old}' to '{new_name}' changes whether it is exported")
        home = self.package_of(path)
        if "." in name:
            return self._find_method(home, name.split(".")[0], old)
        return self.collect(old, lambda p, r: self._top_level(path, home, p, r))

    def _top_level(self, file: str, home: tuple[str, str], p: str, ref: Reference) -> str:
        if ref.kind == "definition":
            return "proven" if p == file and ref.scope == "module" else "unrelated"
        if ref.kind in ("bare", "type") and ref.qualifier is None:
            return self._unqualified(home, p, ref)
        if ref.kind in ("type", "attribute"):
            through = ref.qualifier if ref.kind == "type" else ref.receiver
            if ref.kind == "attribute" and ref.receiver_binding not in ("import", "free"):
                return "unrelated"
            folder = self.aliases(p).get(through or "", "")
            return "proven" if folder == home[0] else "unrelated"
        return common(ref, ("field",))

    def _unqualified(self, home: tuple[str, str], p: str, ref: Reference) -> str:
        """A bare name: its own package sees it; a dot import might."""
        if ref.binding == "local":
            return "unrelated"
        if self.package_of(p) == home:
            return "proven"
        dots = [self.import_dir(d) for d in self.facts(p).wildcards]
        return "unsure" if home[0] in dots or None in dots else "unrelated"

    def _find_method(self, home: tuple[str, str], owner: str, old: str) -> Found | RenameRefusal:
        if old in STANDARD_METHODS:
            return RenameRefusal(
                f"'{old}' is the method of a standard library interface; renaming it drops the interface"
            )
        for p in sorted(self.code):
            if any(r.kind == "definition" and r.binding == "interface" for r in self.refs(p, old)):
                return RenameRefusal(
                    f"an interface in {p} declares '{old}'; a type may satisfy it by that name"
                )
        return self.collect(old, lambda p, r: self._method_use(home, owner, p, r))

    def _method_use(self, home: tuple[str, str], owner: str, p: str, ref: Reference) -> str:
        same = self.package_of(p) == home
        if ref.kind == "definition":
            return "proven" if ref.scope == "class" and ref.owner == owner and same else "unrelated"
        if ref.kind != "attribute":
            return common(ref, ("field", "bare", "type", "import"))
        if ref.receiver_binding == "receiver":
            return "proven" if ref.owner == owner and same else "unrelated"
        if (ref.receiver or "").strip("()*") == owner and same:
            return "proven"
        return "unrelated" if ref.receiver_binding == "import" else "unsure"
