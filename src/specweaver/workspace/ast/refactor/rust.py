# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which occurrences of a name are uses of one Rust item, across a crate.

A crate is the folder of a `Cargo.toml`; its modules follow `src/` (`a.rs` or `a/mod.rs`). A
name resolves through `use`, `pub use` re-exports and `crate::`, `self::`, `super::` paths. A
method is either inherent (`impl Type`) or a trait's: renaming a trait method renames it in the
trait and every impl of it. A glob `use`, a macro and an unknown receiver are unsure.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING, ClassVar

from specweaver.workspace.ast.refactor._base import Resolver, common, verdict
from specweaver.workspace.ast.refactor._model import Found, RenameRefusal

if TYPE_CHECKING:
    from collections.abc import Mapping

    from specweaver.workspace.ast.parsers.interfaces import CodeStructureInterface, Reference
    from specweaver.workspace.ast.refactor._family import ClassId

#: `("def", file, name)` · `("module", crate, "a::b")` · `("external",)` · `("unknown",)`
#: · `("missing",)` · `("free",)`
Resolved = tuple[str, ...]

_UNSURE = ("unknown",)
_KEYWORDS = frozenset(
    [
        "as",
        "break",
        "const",
        "continue",
        "crate",
        "else",
        "enum",
        "extern",
        "false",
        "fn",
        "for",
        "if",
        "impl",
        "in",
        "let",
        "loop",
        "match",
        "mod",
        "move",
        "mut",
        "pub",
        "ref",
        "return",
        "self",
        "Self",
        "static",
        "struct",
        "super",
        "trait",
        "true",
        "type",
        "unsafe",
        "use",
        "where",
        "while",
        "async",
        "await",
        "dyn",
        "abstract",
        "become",
        "box",
        "do",
        "final",
        "macro",
        "override",
        "priv",
        "typeof",
        "unsized",
        "virtual",
        "yield",
        "try",
    ]
)


class RustResolver(Resolver):
    """Resolves item, method and trait names across the Rust crates of one project."""

    SUFFIXES: ClassVar[tuple[str, ...]] = (".rs",)

    def __init__(self, files: Mapping[str, str], parser: CodeStructureInterface) -> None:
        super().__init__(files, parser)
        self._crates = sorted(
            (posixpath.dirname(p) for p in files if posixpath.basename(p) == "Cargo.toml"),
            key=len,
            reverse=True,
        )

    # --- modules -----------------------------------------------------------------------------

    def _crate_of(self, path: str) -> str | None:
        return next(
            (c for c in self._crates if path.startswith(f"{c}/src/" if c else "src/")), None
        )

    def module_of(self, path: str) -> Resolved:
        crate = self._crate_of(path)
        if crate is None:
            return ("unknown",)
        src = f"{crate}/src/" if crate else "src/"
        parts = path[len(src) : -len(".rs")].split("/")
        if parts[-1] == "mod" or parts in (["lib"], ["main"]):
            parts = parts[:-1]
        return ("module", crate, "::".join(parts))

    def _module_file(self, crate: str, segments: str) -> str | None:
        src = f"{crate}/src" if crate else "src"
        if not segments:
            return next((f for f in (f"{src}/lib.rs", f"{src}/main.rs") if f in self.code), None)
        base = f"{src}/{segments.replace('::', '/')}"
        return next((f for f in (f"{base}.rs", f"{base}/mod.rs") if f in self.code), None)

    def _member(self, module: Resolved, name: str, seen: frozenset[str]) -> Resolved:
        """What `name` is inside `module`."""
        crate, segments = module[1], module[2]
        file = self._module_file(crate, segments)
        if file is None:
            return ("unknown",)
        facts = self.facts(file)
        if name in facts.defs:
            return ("def", file, name)
        if name in facts.others:
            return ("module", crate, f"{segments}::{name}" if segments else name)
        if name in facts.imports and f"{file}:{name}" not in seen:
            return self.resolve_path(
                file, facts.imports[name][0].split("::"), seen | {f"{file}:{name}"}
            )
        return ("unknown",) if facts.wildcards else ("missing",)

    def lookup(self, path: str, name: str) -> Resolved:
        """What a bare `name` stands for at the top of `path`."""
        module = self.module_of(path)
        if module[0] != "module":
            return module
        found = self._member(module, name, frozenset())
        if found[0] == "missing":
            return ("free",)
        return found

    def resolve_path(
        self, path: str, segments: list[str], seen: frozenset[str] = frozenset()
    ) -> Resolved:
        """What a path like `crate::util::total`, read in `path`, stands for."""
        current = self._start(path, segments[0], seen)
        for segment in segments[1:]:
            if current[0] != "module":
                return current if current[0] in ("external", "unknown") else ("unknown",)
            if segment == "super":
                current = _parent(current)
                continue
            current = self._member(current, segment, seen)
        return current

    def _start(self, path: str, first: str, seen: frozenset[str]) -> Resolved:
        module = self.module_of(path)
        if module[0] != "module":
            return module
        if first == "crate":
            return ("module", module[1], "")
        if first == "self":
            return module
        if first == "super":
            return _parent(module)
        found = self._member(module, first, seen)
        if found[0] == "missing":
            crates = {posixpath.basename(c) for c in self._crates}
            return ("unknown",) if first in crates else ("external",)
        return found

    def class_id(self, path: str, name: str | None) -> ClassId | None:
        if not name:
            return None
        found = self.lookup(path, name)
        return (found[1], found[2]) if found[0] == "def" else (path, name)

    # --- the rename --------------------------------------------------------------------------

    def find(self, path: str, symbol_name: str, new_name: str) -> Found | RenameRefusal:
        started = self.start(
            path,
            symbol_name,
            new_name,
            lambda n: bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n)) and n not in _KEYWORDS,
            "Rust",
        )
        if isinstance(started, RenameRefusal):
            return started
        name, old = started
        own = self._definition(path, name)
        if own is not None and own.scope == "nested":
            return RenameRefusal(
                f"'{name}' is inside an inline mod; only items of a file's own module rename"
            )
        if "." in name:
            return self._find_method(path, name.split(".")[0], old, own)
        target = ("def", path, old)
        return self.collect(old, lambda p, r: self._item_use(target, p, r))

    def _definition(self, path: str, name: str) -> Reference | None:
        owner, _, short = name.rpartition(".")
        return next(
            (
                r
                for r in self.refs(path, short)
                if r.kind == "definition" and (r.owner or "") == owner
            ),
            None,
        )

    def _item_use(self, target: Resolved, p: str, ref: Reference) -> str:
        if ref.kind == "definition":
            return "proven" if p == target[1] and ref.scope == "module" else "unrelated"
        if ref.kind in ("import", "path"):
            if ref.qualifier == "Self":
                return "unrelated"
            segments = [*filter(None, (ref.qualifier or "").split("::")), target[2]]
            return verdict(self.resolve_path(p, segments), target, _UNSURE)
        if ref.kind in ("bare", "type"):
            if ref.binding == "local":
                return "unrelated"
            return verdict(self.lookup(p, target[2]), target, _UNSURE)
        return common(ref, ("field", "attribute"))

    # --- methods -----------------------------------------------------------------------------

    def _find_method(
        self, home: str, owner: str, old: str, own: Reference | None
    ) -> Found | RenameRefusal:
        trait = (
            own.owner
            if own is not None and own.binding == "trait"
            else (own.qualifier if own else None)
        )
        if trait is None:
            family: set[ClassId] | RenameRefusal = self._inherent(home, owner, old)
        else:
            family = self._trait_family(home, trait, old)
        if isinstance(family, RenameRefusal):
            return family
        return self.collect(old, lambda p, r: self._method_use(family, p, r))

    def _inherent(self, home: str, owner: str, old: str) -> set[ClassId] | RenameRefusal:
        me = self.class_id(home, owner)
        for p in sorted(self.code):
            for r in self.refs(p, old):
                if r.kind == "definition" and r.qualifier and self.class_id(p, r.owner) == me:
                    return RenameRefusal(
                        f"{owner} also has '{old}' from the trait {r.qualifier}; which one a call means is unsure"
                    )
        return {me} if me else set()

    def _trait_family(self, home: str, trait: str, old: str) -> set[ClassId] | RenameRefusal:
        found = self.resolve_path(home, trait.split("::"))
        if found[0] != "def":
            return RenameRefusal(
                f"the trait {trait} is outside the project; renaming '{old}' would stop its impls matching it"
            )
        family: set[ClassId] = {(found[1], found[2])}
        for p in sorted(self.code):
            for type_name, traits in self.facts(p).bases.items():
                if any(self.resolve_path(p, t.split("::")) == found for t in traits):
                    owner = self.class_id(p, type_name)
                    if owner:
                        family.add(owner)
        return family

    def _method_use(self, family: set[ClassId], p: str, ref: Reference) -> str:
        """The verdict on one occurrence of the method's name; `family` is the trait and its impls."""
        mine = self.class_id(p, ref.owner) in family
        if ref.kind == "definition":
            return "proven" if ref.scope == "class" and mine else "unrelated"
        if ref.kind == "attribute":
            if ref.receiver_binding != "self":
                return "unsure"
            return "proven" if mine else "unrelated"
        if ref.kind == "path":
            return self._method_path(family, p, ref, mine)
        return common(ref, ("field", "bare", "type", "import"))

    def _method_path(self, family: set[ClassId], p: str, ref: Reference, mine: bool) -> str:
        """`Self::m`, `Type::m` or `Trait::m`."""
        if ref.qualifier == "Self":
            return "proven" if mine else "unrelated"
        found = self.resolve_path(p, (ref.qualifier or "").split("::"))
        if found[0] == "def":
            return "proven" if (found[1], found[2]) in family else "unrelated"
        return "unsure" if found[0] in _UNSURE else "unrelated"


def _parent(module: Resolved) -> Resolved:
    if module[0] != "module" or not module[2]:
        return ("unknown",)
    return ("module", module[1], module[2].rpartition("::")[0])
