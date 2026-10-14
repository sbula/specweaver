# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The rewrites a file's move needs, for Java and Kotlin, Rust, and C and C++.

Java and Kotlin: the `package` line and every import of the file's types; a Java file renamed
in its folder renames its public class with it. A move to another package is refused while a
file of the old package uses the moved types without an import, or the moved file uses theirs.
Rust: a module renamed in its folder, with its `mod` line, `use` lines and paths. C and C++:
each quoted `#include` of the file, and the moved file's own.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING

from specweaver.workspace.ast.refactor._model import Edits, RenameRefusal, Spot

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import Reference
    from specweaver.workspace.ast.refactor.c_family import CResolver
    from specweaver.workspace.ast.refactor.jvm import JvmResolver
    from specweaver.workspace.ast.refactor.rust import RustResolver

_TYPE_USES = ("type", "bare", "call")


def _stem(path: str) -> str:
    return posixpath.basename(path).rsplit(".", 1)[0]


# --- Java and Kotlin -------------------------------------------------------------------------


def _new_package(resolver: JvmResolver, path: str, new_path: str) -> str | RenameRefusal:
    """The package `new_path` belongs to, read from the source root of `path`."""
    package = resolver.facts(path).package
    folder, below = posixpath.dirname(path), package.replace(".", "/")
    if below and not (folder == below or folder.endswith(f"/{below}")):
        return RenameRefusal(f"the package of {path} does not match its folder")
    root = folder[: len(folder) - len(below)].rstrip("/") if below else folder
    new_folder = posixpath.dirname(new_path)
    if root and new_folder != root and not new_folder.startswith(f"{root}/"):
        return RenameRefusal(f"{new_path} is outside the source root {root}")
    return new_folder[len(root) :].strip("/").replace("/", ".")


def jvm_edits(resolver: JvmResolver, path: str, new_path: str) -> Edits | RenameRefusal:
    new_package = _new_package(resolver, path, new_path)
    if isinstance(new_package, RenameRefusal):
        return new_package
    edits = Edits()
    renamed = _rename_file_class(resolver, edits, path, new_path)
    if new_package != resolver.facts(path).package:
        _change_package(resolver, edits, path, new_package, renamed)
    return edits


def _rename_file_class(
    resolver: JvmResolver, edits: Edits, path: str, new_path: str
) -> dict[str, str]:
    """A file renamed renames the top-level type named like it; returns `{old: new}`."""
    old, new = _stem(path), _stem(new_path)
    if old == new or old not in resolver.facts(path).defs:
        return {}
    found = resolver.type_uses(path, old)
    edits.unsure.extend(found.unsure)
    for p, spans in found.proven.items():
        for start, end in spans:
            edits.add(p, start, end, new)
    return {old: new}


def _change_package(
    resolver: JvmResolver, edits: Edits, path: str, new_package: str, renamed: dict[str, str]
) -> None:
    package = resolver.facts(path).package
    types = sorted(resolver.facts(path).defs)
    for ref in resolver.parser_for(path).find_module_references(resolver.code[path]):
        if ref.kind == "package":
            edits.add(path, ref.start_byte, ref.end_byte, new_package)
    for p in sorted(resolver.code):
        if p != path:
            _rewrite_imports(resolver, edits, p, package, new_package, types, renamed)
            _same_package_uses(resolver, edits, p, path, package, types)
    _uses_of_old_neighbours(resolver, edits, path, package)


def _rewrite_imports(
    resolver: JvmResolver,
    edits: Edits,
    p: str,
    package: str,
    new_package: str,
    types: list[str],
    renamed: dict[str, str],
) -> None:
    for ref in resolver.parser_for(p).find_module_references(resolver.code[p]):
        if ref.kind == "import":
            _rewrite_import(resolver, edits, p, ref, (package, new_package), types, renamed)


def _rewrite_import(
    resolver: JvmResolver,
    edits: Edits,
    p: str,
    ref: Reference,
    packages: tuple[str, str],
    types: list[str],
    renamed: dict[str, str],
) -> None:
    """`import old.T[.member]` becomes `import new.T[.member]`; `import old.*` using `T` is unsure."""
    package, new_package = packages
    module = ref.module or ""
    if ref.binding == "wildcard":
        if module == package and any(_uses(resolver, p, t) for t in types):
            edits.unsure.append(Spot(p, ref.line))
        return
    head = next(
        (t for t in types if module == f"{package}.{t}" or module.startswith(f"{package}.{t}.")),
        None,
    )
    if head is None:
        return
    rest = module[len(f"{package}.{head}") :]
    _drop_inside(edits, p, ref.start_byte, ref.end_byte)
    edits.add(p, ref.start_byte, ref.end_byte, f"{new_package}.{renamed.get(head, head)}{rest}")


def _drop_inside(edits: Edits, p: str, start: int, end: int) -> None:
    """Remove edits inside a span that is about to be replaced whole."""
    edits.spans[p] = [s for s in edits.spans.get(p, []) if not (start <= s[0] and s[1] <= end)]


def _uses(resolver: JvmResolver, p: str, name: str) -> list[int]:
    return [
        r.line
        for r in resolver.refs(p, name)
        if r.kind in _TYPE_USES and r.binding != "local" and r.qualifier is None
    ]


def _same_package_uses(
    resolver: JvmResolver, edits: Edits, p: str, path: str, package: str, types: list[str]
) -> None:
    """A file of the old package that uses a moved type without an import breaks."""
    facts = resolver.facts(p)
    if facts.package != package:
        return
    for name in types:
        if name not in facts.imports:
            edits.unsure.extend(Spot(p, line) for line in _uses(resolver, p, name))


def _uses_of_old_neighbours(resolver: JvmResolver, edits: Edits, path: str, package: str) -> None:
    """The moved file using another type of its old package without an import breaks."""
    imports = resolver.facts(path).imports
    for p in sorted(resolver.code):
        if p == path or resolver.facts(p).package != package:
            continue
        for name in sorted(resolver.facts(p).defs):
            if name not in imports:
                edits.unsure.extend(Spot(path, line) for line in _uses(resolver, path, name))


# --- Rust ------------------------------------------------------------------------------------


def rust_edits(resolver: RustResolver, path: str, new_path: str) -> Edits | RenameRefusal:
    if posixpath.dirname(path) != posixpath.dirname(new_path):
        return RenameRefusal(
            "a Rust file can only be renamed in its folder: the folder is part of the module tree"
        )
    if posixpath.basename(path) in ("mod.rs", "lib.rs", "main.rs"):
        return RenameRefusal(
            f"{posixpath.basename(path)} names its folder or crate, not a module of its own"
        )
    old, new = _stem(path), _stem(new_path)
    if not re.fullmatch(r"[A-Za-z_]\w*", new):
        return RenameRefusal(f"'{new}' is not a Rust module name")
    module = resolver.module_of(path)
    edits = Edits()
    for p in sorted(resolver.code):
        if p == path:
            continue
        for ref in resolver.refs(p, old):
            verdict = _rust_verdict(resolver, p, ref, old, module)
            if verdict == "proven":
                edits.add(p, ref.start_byte, ref.end_byte, new)
            elif verdict == "unsure":
                edits.unsure.append(Spot(p, ref.line))
    return edits


def _rust_verdict(
    resolver: RustResolver, p: str, ref: object, old: str, module: tuple[str, ...]
) -> str:
    kind = getattr(ref, "kind", "")
    qualifier = getattr(ref, "qualifier", None) or ""
    if kind in ("import", "path"):
        segments = [*filter(None, qualifier.split("::")), old]
        return "proven" if resolver.resolve_path(p, segments) == module else "unrelated"
    if kind == "field":
        here = resolver.module_of(p)
        return (
            "proven" if here[0] == "module" and resolver.lookup(p, old) == module else "unrelated"
        )
    if kind == "bare":
        return "proven" if resolver.lookup(p, old) == module else "unrelated"
    return "unsure" if kind == "string" else "unrelated"


# --- C and C++ -------------------------------------------------------------------------------


def _resolve_include(resolver: CResolver, p: str, written: str) -> tuple[str | None, bool]:
    """The file an include names, and whether it was found beside its includer."""
    beside = posixpath.normpath(posixpath.join(posixpath.dirname(p), written))
    if beside in resolver.code:
        return beside, True
    matches = [f for f in resolver.code if f == written or f.endswith(f"/{written}")]
    return (matches[0], False) if len(matches) == 1 else (None, False)


def _relative(target: str, from_file: str) -> str:
    return posixpath.relpath(target, posixpath.dirname(from_file) or ".")


def c_edits(resolver: CResolver, path: str, new_path: str) -> Edits:
    edits = Edits()
    for p in sorted(resolver.code):
        for ref in resolver.parser_for(p).find_module_references(resolver.code[p]):
            new = _include_edit(resolver, p, ref.module or "", path, new_path)
            if new == "":
                edits.unsure.append(Spot(p, ref.line))
            elif new is not None and new != ref.module:
                edits.add(p, ref.start_byte, ref.end_byte, new)
    return edits


def _include_edit(
    resolver: CResolver, p: str, written: str, path: str, new_path: str
) -> str | None:
    """The include's new text; `""` when it cannot be rewritten for certain; None to keep it."""
    target, beside = _resolve_include(resolver, p, written)
    if p == path:
        return (
            _relative(target, new_path)
            if target is not None and beside and target != path
            else None
        )
    if target != path:
        return None
    return _relative(new_path, p) if beside else ""
