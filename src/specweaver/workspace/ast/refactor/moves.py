# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The import rewrites a file's move needs, for Python, TypeScript and Go.

Each function reads the project through its language's resolver and returns `Edits`: the new
text for every import that names the moved file, and the spots it cannot rewrite for certain.
"""

from __future__ import annotations

import posixpath
import re
from typing import TYPE_CHECKING

from specweaver.workspace.ast.refactor._model import Edits, RenameRefusal, Spot

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import Reference
    from specweaver.workspace.ast.refactor.go import GoResolver
    from specweaver.workspace.ast.refactor.python import PythonResolver
    from specweaver.workspace.ast.refactor.typescript import TypeScriptResolver

_ROOTS = ("", "src/")


# --- Python ----------------------------------------------------------------------------------


def python_dotted(path: str) -> dict[str, str]:
    """The dotted module name of `path` per source root it sits under."""
    module = path[: -len(".py")]
    if module.endswith("/__init__"):
        module = module[: -len("/__init__")]
    return {
        root: module[len(root) :].replace("/", ".") for root in _ROOTS if module.startswith(root)
    }


def _parts(folder: str) -> list[str]:
    return [p for p in folder.split("/") if p]


def relative_spec(from_file: str, target_file: str) -> str:
    """A relative import from the package of `from_file` to the module in `target_file`."""
    target = target_file[: -len(".py")]
    is_package = posixpath.basename(target) == "__init__"
    if is_package:
        target = posixpath.dirname(target)
    there, here = _parts(target), _parts(posixpath.dirname(from_file))
    folders = len(there) if is_package else len(there) - 1
    common = 0
    while common < min(len(here), folders) and here[common] == there[common]:
        common += 1
    return "." * (len(here) - common + 1) + ".".join(there[common:])


def python_edits(resolver: PythonResolver, path: str, new_path: str) -> Edits | RenameRefusal:
    if path.endswith("__init__.py"):
        return RenameRefusal("a package's __init__.py moves with its folder, not alone")
    edits = Edits()
    for p in sorted(resolver.code):
        _python_file(resolver, edits, p, path, new_path)
    return edits


def _python_file(resolver: PythonResolver, edits: Edits, p: str, path: str, new_path: str) -> None:
    code = resolver.code[p]
    parser = resolver.parser_for(p)
    old = python_dotted(path)
    current: Reference | None = None
    for ref in parser.find_module_references(code):
        if ref.kind == "string":
            if ref.module in old.values() and p != path:
                edits.unsure.append(Spot(p, ref.line))
        elif ref.kind == "import" and p != path:
            _python_import(resolver, edits, p, ref, old, python_dotted(new_path))
        elif ref.kind == "from":
            current = ref
            _python_from(resolver, edits, p, ref, path, new_path)
        elif ref.kind == "from_name" and current is not None and p != path:
            _python_submodule(resolver, edits, p, current, ref, path, new_path)


def _python_import(
    resolver: PythonResolver,
    edits: Edits,
    p: str,
    ref: Reference,
    old: dict[str, str],
    new: dict[str, str],
) -> None:
    root = next((r for r, dotted in old.items() if dotted == ref.module), None)
    if root is None:
        return
    if root not in new:
        edits.unsure.append(Spot(p, ref.line))
        return
    edits.add(p, ref.start_byte, ref.end_byte, new[root])
    if ref.alias is None:
        for chain in resolver.parser_for(p).find_dotted(resolver.code[p], ref.module or ""):
            edits.add(p, chain.start_byte, chain.end_byte, new[root])


def _python_from(
    resolver: PythonResolver, edits: Edits, p: str, ref: Reference, path: str, new_path: str
) -> None:
    spec = ref.module or ""
    found = resolver.resolve_module(spec, p)
    if found[0] != "module":
        return
    if p == path:
        if spec.startswith("."):
            new = relative_spec(new_path, found[1])
            if new != spec:
                edits.add(p, ref.start_byte, ref.end_byte, new)
        return
    if found[1] != path:
        return
    if spec.startswith("."):
        edits.add(p, ref.start_byte, ref.end_byte, relative_spec(p, new_path))
        return
    root = next((r for r, dotted in python_dotted(path).items() if dotted == spec), None)
    absolute = python_dotted(new_path).get(root) if root is not None else None
    if absolute is None:
        edits.unsure.append(Spot(p, ref.line))
    else:
        edits.add(p, ref.start_byte, ref.end_byte, absolute)


def _python_submodule(
    resolver: PythonResolver,
    edits: Edits,
    p: str,
    statement: Reference,
    ref: Reference,
    path: str,
    new_path: str,
) -> None:
    """`from app import greeter`: the parent and the name both change."""
    name = _text_of(resolver.code[p], ref)
    package = resolver.resolve_module(ref.module or "", p)
    if package[0] != "module" or resolver._submodule(package[1], name) != path:
        return
    spec = ref.module or ""
    new_spec = _parent_spec(p, spec, package[1], new_path)
    if new_spec != spec:
        if not new_spec or len((ref.receiver or "").split(",")) > 1:
            edits.unsure.append(Spot(p, ref.line))
            return
        edits.add(p, statement.start_byte, statement.end_byte, new_spec)
    stem = posixpath.basename(new_path)[: -len(".py")]
    edits.add(p, ref.start_byte, ref.end_byte, stem)
    if ref.alias is None and stem != name:
        _rebind(resolver, edits, p, name, stem)


def _text_of(code: str, ref: Reference) -> str:
    return code.encode("utf-8")[ref.start_byte : ref.end_byte].decode("utf-8")


def _parent_spec(p: str, spec: str, package_file: str, new_path: str) -> str:
    """The new `from` part for the package that holds the moved module."""
    parent = posixpath.join(posixpath.dirname(new_path), "__init__.py")
    if spec.startswith("."):
        return relative_spec(p, parent)
    root = next((r for r, d in python_dotted(package_file).items() if d == spec), None)
    return python_dotted(parent).get(root or "", "")


def _rebind(resolver: PythonResolver, edits: Edits, p: str, name: str, stem: str) -> None:
    """The local name the import bound follows the module's new name."""
    for use in resolver.parser_for(p).find_references(resolver.code[p], name):
        if use.kind == "bare" and use.binding == "import":
            edits.add(p, use.start_byte, use.end_byte, stem)


# --- TypeScript ------------------------------------------------------------------------------


def typescript_spec(from_file: str, target: str, original: str) -> str:
    """A relative specifier from `from_file` to `target`, in the style of `original`."""
    rel = posixpath.relpath(target, posixpath.dirname(from_file) or ".")
    rel = re.sub(r"(\.d)?\.tsx?$", "", rel)
    if posixpath.basename(rel) == "index" and not original.rstrip("/").endswith("index"):
        rel = posixpath.dirname(rel) or "."
    match = re.search(r"\.[mc]?jsx?$", original)
    if match:
        rel += match.group(0)
    return rel if rel.startswith(".") else f"./{rel}"


def typescript_edits(resolver: TypeScriptResolver, path: str, new_path: str) -> Edits:
    edits = Edits()
    for p in sorted(resolver.code):
        for ref in resolver.parser_for(p).find_module_references(resolver.code[p]):
            _typescript_ref(resolver, edits, p, ref, path, new_path)
    return edits


def _typescript_ref(
    resolver: TypeScriptResolver, edits: Edits, p: str, ref: Reference, path: str, new_path: str
) -> None:
    spec = ref.module or ""
    if not spec.startswith("."):
        stem = posixpath.basename(path).split(".")[0]
        if resolver._aliased and posixpath.basename(spec).split(".")[0] == stem:
            edits.unsure.append(Spot(p, ref.line))
        return
    found = resolver.resolve_module(spec, p)
    if found[0] != "module" or (found[1] == path) == (p == path):
        return
    new = (
        typescript_spec(new_path, found[1], spec)
        if p == path
        else typescript_spec(p, new_path, spec)
    )
    if new != spec:
        edits.add(p, ref.start_byte, ref.end_byte, new)


# --- Go --------------------------------------------------------------------------------------


def go_edits(_resolver: GoResolver, path: str, new_path: str) -> Edits | RenameRefusal:
    if posixpath.dirname(path) != posixpath.dirname(new_path):
        return RenameRefusal(
            "a Go file can only be renamed in its folder: the folder is the package"
        )
    return Edits()
