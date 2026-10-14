# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which occurrences of a name are uses of one C or C++ symbol, across a project.

C and C++ files are searched together (`extern "C"`). A non-`static` name is one symbol
program-wide: a use is proven in its own file, or in a file that declares it or includes,
through quoted `#include`s, a header that declares it. A use with no declaration in reach,
a name in a macro body and `using namespace` are unsure. A `static` name stays in its file.
C++ methods rename with their override family; a family with a base outside the project
refuses.
"""

from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING, ClassVar

from specweaver.workspace.ast.refactor._base import Resolver, common, plain_name
from specweaver.workspace.ast.refactor._model import Found, RenameRefusal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface, Reference

_C_KEYWORDS = frozenset(
    [
        "auto",
        "break",
        "case",
        "char",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extern",
        "float",
        "for",
        "goto",
        "if",
        "inline",
        "int",
        "long",
        "register",
        "restrict",
        "return",
        "short",
        "signed",
        "sizeof",
        "static",
        "struct",
        "switch",
        "typedef",
        "union",
        "unsigned",
        "void",
        "volatile",
        "while",
        "bool",
        "true",
        "false",
    ]
)
_CPP_KEYWORDS = _C_KEYWORDS | frozenset(
    [
        "alignas",
        "alignof",
        "and",
        "asm",
        "catch",
        "class",
        "constexpr",
        "const_cast",
        "decltype",
        "delete",
        "dynamic_cast",
        "explicit",
        "export",
        "friend",
        "mutable",
        "namespace",
        "new",
        "noexcept",
        "not",
        "nullptr",
        "operator",
        "or",
        "private",
        "protected",
        "public",
        "reinterpret_cast",
        "static_assert",
        "static_cast",
        "template",
        "this",
        "thread_local",
        "throw",
        "try",
        "typeid",
        "typename",
        "using",
        "virtual",
        "wchar_t",
        "override",
        "final",
    ]
)


class CResolver(Resolver):
    """Resolves function, type and method names across the C and C++ files of one project."""

    SUFFIXES: ClassVar[tuple[str, ...]] = (".c", ".h", ".cpp", ".hpp", ".cc", ".cxx")
    #: C++ files may include a C header, so a new name must be free in both languages.
    KEYWORDS: ClassVar[frozenset[str]] = _CPP_KEYWORDS
    LANGUAGE: ClassVar[str] = "C"

    def __init__(self, files: Mapping[str, str], parser: CodeStructureInterface) -> None:
        super().__init__(files, parser)
        self._closure: dict[str, set[str]] = {}

    # --- includes ----------------------------------------------------------------------------

    def _include(self, path: str, written: str) -> str | None:
        beside = posixpath.normpath(posixpath.join(posixpath.dirname(path), written))
        if beside in self.code:
            return beside
        matches = [f for f in self.code if f == written or f.endswith(f"/{written}")]
        return matches[0] if len(matches) == 1 else None

    def included(self, path: str) -> set[str]:
        """Every project file `path` includes, directly or through other includes."""
        if path not in self._closure:
            seen: set[str] = set()
            todo = [path]
            while todo:
                for written in self.facts(todo.pop()).imports:
                    found = self._include(path, written)
                    if found and found not in seen:
                        seen.add(found)
                        todo.append(found)
            self._closure[path] = seen
        return self._closure[path]

    # --- targets -----------------------------------------------------------------------------

    def pick(self, path: str, symbol_name: str) -> str | RenameRefusal:
        """C and C++ symbols are read from their definitions and prototypes in `path`."""
        written, _, short = symbol_name.rpartition(".")
        decls = [r for r in self.refs(path, short) if r.kind in ("definition", "declaration")]
        owner = _owner(written.split(".")[-1], short, decls)
        if isinstance(owner, RenameRefusal):
            return owner
        mine = [r for r in decls if (r.owner or "") == owner]
        if not mine:
            return RenameRefusal(
                f"only functions, methods and types can be renamed; '{symbol_name}' is none of them in {path}"
            )
        if max(sum(r.kind == kind for r in mine) for kind in ("definition", "declaration")) > 1:
            return RenameRefusal(f"'{symbol_name}' is defined more than once in {path}")
        return f"{owner}.{short}" if owner else short

    def find(self, path: str, symbol_name: str, new_name: str) -> Found | RenameRefusal:
        started = self.start(
            path,
            symbol_name,
            new_name,
            plain_name(self.KEYWORDS),
            self.LANGUAGE,
        )
        if isinstance(started, RenameRefusal):
            return started
        name, old = started
        if "." in name:
            return self._find_method(name.split(".")[0], old)
        return self._find_top_level(path, old)

    # --- functions and types -----------------------------------------------------------------

    def _find_top_level(self, home: str, old: str) -> Found | RenameRefusal:
        own = next(
            r
            for r in self.refs(home, old)
            if r.kind in ("definition", "declaration") and not r.owner
        )
        namespace = own.module or ""
        static = own.binding == "static"
        if not static and own.binding != "type":
            elsewhere = self._defined_elsewhere(home, old, namespace)
            if elsewhere:
                return RenameRefusal(
                    f"'{old}' is defined in several files: {', '.join([home, *elsewhere])}"
                )
        declares = {
            p
            for p in self.code
            if p == home
            or (not static and any(self._declares(r, namespace) for r in self.refs(p, old)))
        }
        return self.collect(
            old, lambda p, r: self._top_level(home, namespace, static, declares, p, r)
        )

    def _defined_elsewhere(self, home: str, old: str, namespace: str) -> list[str]:
        """Other files with a non-`static` definition of `old` in the same namespace."""
        return sorted(
            p
            for p in self.code
            if p != home
            and any(
                r.kind == "definition"
                and not r.owner
                and r.binding is None
                and (r.module or "") == namespace
                for r in self.refs(p, old)
            )
        )

    def _declares(self, ref: Reference, namespace: str) -> bool:
        return (
            ref.kind in ("definition", "declaration")
            and not ref.owner
            and (ref.module or "") == namespace
            and ref.binding != "static"
        )

    def _sees(self, declares: set[str], p: str) -> bool:
        return p in declares or bool(self.included(p) & declares)

    def _top_level(
        self, home: str, namespace: str, static: bool, declares: set[str], p: str, ref: Reference
    ) -> str:
        if ref.kind in ("definition", "declaration"):
            if ref.owner or (ref.module or "") != namespace:
                return "unrelated"
            if p == home:
                return "proven"
            return "unrelated" if static or ref.binding == "static" else "proven"
        if ref.kind in ("path", "import"):
            return (
                "proven"
                if (ref.qualifier or "").lstrip(":") == namespace and not static
                else "unrelated"
            )
        if ref.kind in ("bare", "type"):
            return self._unqualified(home, namespace, static, declares, p, ref)
        return common(ref, ("field", "attribute"))

    def _unqualified(
        self, home: str, namespace: str, static: bool, declares: set[str], p: str, ref: Reference
    ) -> str:
        if ref.binding == "local" or (ref.kind == "bare" and ref.owner and p != home):
            return "unrelated"
        if p != home and (static or self._has_own_static(p, ref)):
            return "unrelated"
        inside = (ref.module or "") == namespace or (ref.module or "").startswith(f"{namespace}::")
        if namespace and not inside:
            return self._outside_namespace(namespace, p, ref)
        return "proven" if self._sees(declares, p) else "unsure"

    def _outside_namespace(self, namespace: str, p: str, ref: Reference) -> str:
        """An unqualified use outside the namespace: through `using`, or not ours."""
        if any(
            r.kind == "import" and (r.qualifier or "") == namespace
            for r in self.refs(p, self._name(p, ref))
        ):
            return "proven"
        return "unsure" if namespace in self.facts(p).wildcards else "unrelated"

    def _name(self, p: str, ref: Reference) -> str:
        return self.code[p].encode("utf-8")[ref.start_byte : ref.end_byte].decode("utf-8")

    def _has_own_static(self, p: str, ref: Reference) -> bool:
        return any(
            r.kind == "definition" and r.binding == "static"
            for r in self.refs(p, self._name(p, ref))
        )

    # --- methods (C++) -----------------------------------------------------------------------

    def _class_file(self, name: str) -> str | None:
        return next((p for p in sorted(self.code) if name in self.facts(p).defs), None)

    def resolve_class(self, _path: str, written: str) -> tuple[str, ...]:
        name = written.split("::")[-1].split("<")[0]
        found = self._class_file(name)
        return ("def", found, name) if found else ("external",)

    def _find_method(self, cls: str, old: str) -> Found | RenameRefusal:
        home = self._class_file(cls)
        if home is None:
            return RenameRefusal(f"the class {cls} is not defined in the project")
        family = self.family(home, cls, old, self.resolve_class, frozenset())
        if isinstance(family, RenameRefusal):
            return family
        names = {name for _, name in family}
        return self.collect(old, lambda p, r: self._method_use(names, r))

    def _method_use(self, names: set[str], ref: Reference) -> str:
        if ref.kind in ("definition", "declaration", "bare"):
            return "proven" if ref.owner in names else "unrelated"
        if ref.kind == "attribute":
            if ref.receiver_binding != "this":
                return "unsure"
            return "proven" if ref.owner in names else "unrelated"
        if ref.kind == "path":
            return (
                "proven"
                if (ref.qualifier or "").split("::")[-1].split("<")[0] in names
                else "unrelated"
            )
        return common(ref, ("field", "type", "import"))


def _owner(written: str, short: str, decls: list[Reference]) -> str | RenameRefusal:
    """The class of the symbol: as written, or the one class that has a member of that name."""
    if written or any(not r.owner for r in decls):
        return written
    owners = sorted({r.owner for r in decls if r.owner})
    if len(owners) > 1:
        return RenameRefusal(f"'{short}' is ambiguous: {', '.join(f'{o}.{short}' for o in owners)}")
    return owners[0] if owners else ""


class CppResolver(CResolver):
    """The same search, reading `.h` files as C++."""

    LANGUAGE: ClassVar[str] = "C++"

    def __init__(self, files: Mapping[str, str], parser: CodeStructureInterface) -> None:
        super().__init__(files, parser)
        self._parsers[".h"] = self._parsers[".cpp"]
        self.code = {p: c for p, c in files.items() if p.endswith(self.SUFFIXES)}
