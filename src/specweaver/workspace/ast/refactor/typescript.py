# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which occurrences of a name are uses of one TypeScript symbol, across a project.

Each file is a module. A name is proven when it resolves through imports, re-exports and
namespace imports to the definition, or is a member reached through `this`, `super` or a class
of its override family. `export *`, a path alias from `tsconfig.json`, an object-literal key and
a plain JavaScript file holding the name are unsure: none can be followed for certain.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.workspace.ast.refactor._base import Resolver, common, verdict
from specweaver.workspace.ast.refactor._model import Found, RenameRefusal, Spot

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface, Reference
    from specweaver.workspace.ast.refactor._family import ClassId

#: `("def", file, name)` · `("module", file)` · `("default",)` · `("missing",)` · `("other",)`
#: · `("external",)` · `("unknown",)` · `("free",)`
Resolved = tuple[str, ...]

_UNSURE = ("unknown",)
_JS = (".js", ".jsx", ".mjs", ".cjs")
_RESERVED = frozenset(
    [
        "break",
        "case",
        "catch",
        "class",
        "const",
        "continue",
        "debugger",
        "default",
        "delete",
        "do",
        "else",
        "enum",
        "export",
        "extends",
        "false",
        "finally",
        "for",
        "function",
        "if",
        "import",
        "in",
        "instanceof",
        "new",
        "null",
        "return",
        "super",
        "switch",
        "this",
        "throw",
        "true",
        "try",
        "typeof",
        "var",
        "void",
        "while",
        "with",
        "as",
        "implements",
        "interface",
        "let",
        "package",
        "private",
        "protected",
        "public",
        "static",
        "yield",
        "await",
    ]
)


class TypeScriptResolver(Resolver):
    """Resolves names across the TypeScript modules of one project."""

    SUFFIXES: ClassVar[tuple[str, ...]] = (".ts", ".tsx")

    def __init__(self, files: Mapping[str, str], parser: CodeStructureInterface) -> None:
        super().__init__(files, parser)
        self._files = files
        self._aliased = any(
            p.endswith("tsconfig.json") and re.search(r'"(paths|baseUrl)"', text)
            for p, text in files.items()
        )

    # --- modules -----------------------------------------------------------------------------

    def resolve_module(self, spec: str, from_file: str) -> Resolved:
        """The file an import path means, seen from `from_file`."""
        if not spec.startswith("."):
            return ("unknown",) if self._aliased else ("external",)
        base = posixpath.normpath(posixpath.join(posixpath.dirname(from_file), spec))
        stem = re.sub(r"\.[mc]?jsx?$", "", base)
        for candidate in (
            f"{stem}.ts",
            f"{stem}.tsx",
            f"{stem}.d.ts",
            f"{stem}/index.ts",
            f"{stem}/index.tsx",
        ):
            if candidate in self.code:
                return ("module", candidate)
        return ("unknown",)

    def resolve_export(
        self, module: str, name: str, seen: frozenset[tuple[str, str]] = frozenset()
    ) -> Resolved:
        """What `module` exports as `name`."""
        if (module, name) in seen:
            return ("unknown",)
        seen = seen | {(module, name)}
        facts = self.facts(module)
        if name in facts.statics:
            source, original = facts.statics[name]
            if not source:
                return self.resolve_local(module, original, seen)
            found = self.resolve_module(source, module)
            return self.resolve_export(found[1], original, seen) if found[0] == "module" else found
        if name in facts.defs:
            return ("def", module, name)
        return ("unknown",) if facts.wildcards else ("missing",)

    def resolve_local(
        self, path: str, local: str, seen: frozenset[tuple[str, str]] = frozenset()
    ) -> Resolved:
        """What the module-level name `local` of `path` stands for."""
        kind = self.module_kind(path, local)
        if kind in ("conflict", "def"):
            return ("unknown",) if kind == "conflict" else ("def", path, local)
        if kind == "import":
            source, imported = self.facts(path).imports[local]
            found = self.resolve_module(source, path)
            if found[0] != "module" or imported is None:
                return found
            return (
                ("default",)
                if imported == "default"
                else self.resolve_export(found[1], imported, seen)
            )
        return ("other",) if kind == "other" else ("free",)

    def resolve_dotted(self, path: str, written: str) -> Resolved:
        """A dotted name like `ns.Greeter`, read from the module level of `path`."""
        parts = written.split(".")
        if not all(p.isidentifier() for p in parts):
            return ("unknown",)
        found = self.resolve_local(path, parts[0])
        for part in parts[1:]:
            if found[0] != "module":
                return found if found[0] in ("external", "unknown") else ("unknown",)
            found = self.resolve_export(found[1], part)
        return found

    # --- the rename --------------------------------------------------------------------------

    def find(self, path: str, symbol_name: str, new_name: str) -> Found | RenameRefusal:
        started = self.start(
            path,
            symbol_name,
            new_name,
            lambda n: bool(re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", n)) and n not in _RESERVED,
            "TypeScript",
        )
        if isinstance(started, RenameRefusal):
            return started
        name, old = started
        if "." in name:
            found = self._find_method(path, name.split(".")[0], old)
        else:
            target = ("def", path, old)
            found = self.collect(old, lambda p, r: self._top_level(target, p, r))
        if isinstance(found, Found):
            found.unsure.extend(self._in_javascript(old))
        return found

    def _in_javascript(self, old: str) -> list[Spot]:
        """No parser reads JavaScript, so a `.js` file holding the name is unsure."""
        pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(old)}(?![A-Za-z0-9_$])")
        spots = []
        for p, content in sorted(self._files.items()):
            if p.endswith(_JS):
                line = next(
                    (n for n, t in enumerate(content.splitlines(), 1) if pattern.search(t)), None
                )
                if line is not None:
                    spots.append(Spot(p, line))
        return spots

    def _top_level(self, target: Resolved, p: str, ref: Reference) -> str:
        home = target[1]
        if ref.kind == "definition":
            return "proven" if p == home and ref.scope == "module" else "unrelated"
        if ref.kind == "import":
            return self._exported(self.resolve_module(ref.module or "", p), target)
        if ref.kind in ("bare", "type"):
            if ref.qualifier:
                return self._exported(self.resolve_dotted(p, ref.qualifier), target)
            return self._bare(target, p, ref)
        if ref.kind == "attribute":
            if ref.receiver_binding not in ("import", "module_def"):
                return "unsure"
            return self._exported(self.resolve_dotted(p, ref.receiver or ""), target)
        return common(ref, ("field",))

    def _exported(self, module: Resolved, target: Resolved) -> str:
        """The verdict on the target's name read from `module`."""
        if module[0] != "module":
            return "unsure" if module[0] in _UNSURE else "unrelated"
        return verdict(self.resolve_export(module[1], target[2]), target, _UNSURE)

    def _bare(self, target: Resolved, p: str, ref: Reference) -> str:
        if ref.binding == "module_def":
            return "proven" if p == target[1] else "unrelated"
        if ref.binding == "import":
            return verdict(self.resolve_local(p, target[2]), target, _UNSURE)
        return "unrelated" if ref.binding in ("local", "module_other") else "unsure"

    # --- methods -----------------------------------------------------------------------------

    def _find_method(self, home: str, cls: str, old: str) -> Found | RenameRefusal:
        family = self.family(home, cls, old, self.resolve_dotted, frozenset())
        if isinstance(family, RenameRefusal):
            return family
        return self.collect(old, lambda p, r: self._member(family, p, r))

    def _member(self, family: set[ClassId], p: str, ref: Reference) -> str:
        """The verdict on one occurrence of the method's name; `family` is its override family."""
        in_family = ref.owner is not None and (p, ref.owner) in family
        if ref.kind == "definition":
            return "proven" if ref.scope == "class" and in_family else "unrelated"
        if ref.kind == "field":
            return "unsure" if in_family else "unrelated"
        if ref.kind == "attribute":
            return self._member_call(family, p, ref, in_family)
        if ref.kind in ("bare", "type", "import"):
            return "unrelated"
        return common(ref, ())

    def _member_call(self, family: set[ClassId], p: str, ref: Reference, in_family: bool) -> str:
        if ref.receiver_binding in ("this", "super"):
            return "proven" if in_family else "unrelated"
        if ref.receiver_binding not in ("import", "module_def"):
            return "unsure"
        found = self.resolve_dotted(p, ref.receiver or "")
        if found[0] == "def":
            return "proven" if (found[1], found[2]) in family else "unrelated"
        return "unsure" if found[0] in _UNSURE else "unrelated"
