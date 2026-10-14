# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which occurrences of a name are uses of one Java or Kotlin symbol, across a project.

Java and Kotlin are searched together: each calls the other. A type is found the way the
compilers find it: a single-type import, the file itself, the same package, then a `*` import.
A call with no receiver inside a class is a call on `this`. Types, methods and fields are kept
apart, so a field of the method's name is not a use of the method.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from specweaver.workspace.ast.refactor._base import Resolver, common, verdict
from specweaver.workspace.ast.refactor._model import Found, RenameRefusal

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import Reference
    from specweaver.workspace.ast.refactor._family import ClassId

#: Root types that add no method a rename could stop overriding.
_HARMLESS = frozenset({"Object", "java.lang.Object", "Any", "kotlin.Any"})
_UNSURE = ("unknown",)

_KEYWORDS = frozenset(
    [
        "abstract",
        "assert",
        "boolean",
        "break",
        "byte",
        "case",
        "catch",
        "char",
        "class",
        "const",
        "continue",
        "default",
        "do",
        "double",
        "else",
        "enum",
        "extends",
        "final",
        "finally",
        "float",
        "for",
        "goto",
        "if",
        "implements",
        "import",
        "instanceof",
        "int",
        "interface",
        "long",
        "native",
        "new",
        "package",
        "private",
        "protected",
        "public",
        "return",
        "short",
        "static",
        "strictfp",
        "super",
        "switch",
        "synchronized",
        "this",
        "throw",
        "throws",
        "transient",
        "try",
        "void",
        "volatile",
        "while",
        "true",
        "false",
        "null",
        "var",
        "record",
        "yield",
        "as",
        "fun",
        "in",
        "is",
        "object",
        "typealias",
        "typeof",
        "val",
        "when",
    ]
)

#: `("def", file, name)` · `("external",)` · `("unknown",)`
Resolved = tuple[str, ...]


class JvmResolver(Resolver):
    """Resolves type, method and function names across the Java and Kotlin files of a project."""

    SUFFIXES: ClassVar[tuple[str, ...]] = (".java", ".kt", ".kts")

    # --- types -------------------------------------------------------------------------------

    def _index(self) -> dict[tuple[str, str], str]:
        if not hasattr(self, "_types"):
            self._types = {
                (self.facts(p).package, name): p
                for p in sorted(self.code)
                for name in self.facts(p).defs
            }
        return self._types

    def _packages(self) -> set[str]:
        return {self.facts(p).package for p in self.code}

    def resolve_qualified(self, qualifier: str, name: str) -> Resolved:
        found = self._index().get((qualifier, name))
        if found:
            return ("def", found, name)
        if qualifier in self._packages() or qualifier.split(".")[-1][:1].isupper():
            return ("unknown",)
        return ("external",)

    def resolve_type(self, path: str, name: str) -> Resolved:
        """The class `name` stands for in `path`, as the compiler looks it up."""
        facts = self.facts(path)
        if name in facts.imports:
            qualifier, imported = facts.imports[name]
            return self.resolve_qualified(qualifier, imported or name)
        if name in facts.defs:
            return ("def", path, name)
        for package in (
            facts.package,
            *[w for w in facts.wildcards if not w.startswith("static ")],
        ):
            found = self._index().get((package, name))
            if found:
                return ("def", found, name)
        if any(w not in self._packages() for w in facts.wildcards):
            return ("unknown",)
        return ("external",)

    def resolve_text(self, path: str, written: str) -> Resolved:
        """A type as written, plain or dotted."""
        if "." not in written:
            return self.resolve_type(path, written)
        qualifier, _, name = written.rpartition(".")
        return self.resolve_qualified(qualifier, name)

    # --- the rename --------------------------------------------------------------------------

    def find(self, path: str, symbol_name: str, new_name: str) -> Found | RenameRefusal:
        started = self.start(
            path,
            symbol_name,
            new_name,
            lambda n: n.isidentifier() and n not in _KEYWORDS,
            "Java or Kotlin",
        )
        if isinstance(started, RenameRefusal):
            return started
        name, old = started
        if self._is_type(path, name):
            return self._find_type(path, name)
        if "." in name:
            return self._find_method(path, name.split(".")[0], old)
        return self._find_function(path, old)

    def _is_type(self, path: str, name: str) -> bool:
        owner, _, short = name.rpartition(".")
        return any(
            r.kind == "definition" and r.binding == "type" and (r.owner or "") == owner
            for r in self.refs(path, short)
        )

    def _find_type(self, home: str, name: str) -> Found | RenameRefusal:
        if "." in name:
            return RenameRefusal(f"'{name}' is a nested type; only top-level types rename")
        stem = home.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        public = name in self.parser_for(home).list_symbols(self.code[home], visibility=["public"])
        if home.endswith(".java") and stem == name and public:
            return RenameRefusal(
                f"'{name}' is the public class of {home}, which Java names after it; "
                "rename the file with move_module"
            )
        target = ("def", home, name)
        package = self.facts(home).package
        return self.collect(name, lambda p, r: self._type_use(target, package, p, r))

    def _type_use(self, target: Resolved, package: str, p: str, ref: Reference) -> str:
        home, name = target[1], target[2]
        if ref.kind == "definition":
            is_it = p == home and ref.scope == "module" and ref.binding == "type"
            return "proven" if is_it else "unrelated"
        if ref.kind == "constructor":
            return "proven" if (p, ref.owner) == (home, name) else "unrelated"
        if ref.kind == "import":
            return "proven" if ref.qualifier == package else "unrelated"
        if ref.kind in ("type", "bare", "call"):
            return self._type_name(target, p, ref)
        if ref.kind == "attribute":
            return "proven" if ref.receiver == package else "unsure"
        return common(ref, ("keyword", "field"))

    def _type_name(self, target: Resolved, p: str, ref: Reference) -> str:
        """A use of the class's name as a type, a value or a constructor call."""
        if ref.kind == "bare" and ref.binding == "local":
            return "unrelated"
        if ref.qualifier is not None:
            return verdict(self.resolve_qualified(ref.qualifier, target[2]), target, _UNSURE)
        return verdict(self.resolve_type(p, target[2]), target, _UNSURE)

    def _find_function(self, home: str, old: str) -> Found:
        package = self.facts(home).package
        facade = home.rsplit("/", 1)[-1].rsplit(".", 1)[0].capitalize() + "Kt"
        return self.collect(old, lambda p, r: self._function_use(home, package, facade, p, r))

    def _function_use(self, home: str, package: str, facade: str, p: str, ref: Reference) -> str:
        """The verdict on one occurrence of a Kotlin top-level function's name."""
        if ref.kind == "definition":
            return "proven" if p == home and ref.scope == "module" else "unrelated"
        if ref.kind == "import":
            return "proven" if ref.qualifier == package and ref.scope == "last" else "unrelated"
        if ref.kind in ("call", "bare"):
            return self._function_call(package, p, ref)
        if ref.kind == "attribute":
            return (
                "proven" if ref.receiver in (package, facade, f"{package}.{facade}") else "unsure"
            )
        return common(ref, ("keyword", "field"))

    def _function_call(self, package: str, p: str, ref: Reference) -> str:
        if ref.binding == "anonymous":
            return "unsure"
        if ref.binding == "local":
            return "unrelated"
        name = self.code[p].encode("utf-8")[ref.start_byte : ref.end_byte].decode("utf-8")
        if ref.owner and f"{ref.owner}.{name}" in self.symbols(p):
            return "unrelated"
        facts = self.facts(p)
        if name in facts.imports:
            return "proven" if facts.imports[name][0] == package else "unrelated"
        same = facts.package == package or package in facts.wildcards
        return "proven" if same else "unrelated"

    # --- methods -----------------------------------------------------------------------------

    def _find_method(self, home: str, cls: str, old: str) -> Found | RenameRefusal:
        family = self.family(home, cls, old, self.resolve_text, _HARMLESS)
        if isinstance(family, RenameRefusal):
            return family
        return self.collect(old, lambda p, r: self._method_use(family, p, r))

    def _method_use(self, family: set[ClassId], p: str, ref: Reference) -> str:
        """The verdict on one occurrence of the method's name; `family` is its override family."""
        if ref.kind == "definition":
            in_family = ref.scope == "class" and ref.binding != "type" and (p, ref.owner) in family
            return "proven" if in_family else "unrelated"
        if ref.kind == "call":
            return self._method_call(family, p, ref)
        if ref.kind == "attribute":
            return self._method_attribute(family, p, ref)
        if ref.kind == "import":
            if ref.module != "static" or ref.scope != "last":
                return "unrelated"
            return _member(self.resolve_text(p, ref.qualifier or ""), family)
        if ref.kind in ("type", "bare", "field", "constructor"):
            return "unrelated"
        return common(ref, ("keyword", "field"))

    def _method_call(self, family: set[ClassId], p: str, ref: Reference) -> str:
        """A call with no receiver: on `this`, through a static import, or something else."""
        if ref.binding == "anonymous":
            return "unsure"
        facts = self.facts(p)
        name = self.code[p].encode("utf-8")[ref.start_byte : ref.end_byte].decode("utf-8")
        if name in facts.statics:
            return _member(self.resolve_text(p, facts.statics[name][0]), family)
        if ref.owner and (p, ref.owner) in family:
            return "proven"
        if any((p, outer) in family for outer in ref.enclosing):
            return "unsure"
        static_stars = [w[len("static ") :] for w in facts.wildcards if w.startswith("static ")]
        if any(_member(self.resolve_text(p, w), family) != "unrelated" for w in static_stars):
            return "unsure"
        return "unrelated"

    def _method_attribute(self, family: set[ClassId], p: str, ref: Reference) -> str:
        """`this.m()`, `super.m()`, `Type.m()`, `Type::m`; anything else is unsure."""
        if ref.receiver_binding in ("this", "super"):
            return "proven" if ref.owner and (p, ref.owner) in family else "unrelated"
        receiver = ref.receiver or ""
        if ref.receiver_binding == "local" or not all(
            s.isidentifier() for s in receiver.split(".")
        ):
            return "unsure"
        return _member(self.resolve_text(p, receiver), family)


def _member(found: Resolved, family: set[ClassId]) -> str:
    if found[0] == "def":
        return "proven" if (found[1], found[2]) in family else "unrelated"
    return "unsure" if found[0] in _UNSURE else "unrelated"
