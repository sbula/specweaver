# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a name occurs in one Kotlin file, and what it is there.

The same vocabulary as Java's finder, so one resolver judges both languages.
"""

from __future__ import annotations

import functools
import typing

from specweaver.workspace.ast.parsers import _jvm
from specweaver.workspace.ast.parsers._ref_tools import ref, text, walk
from specweaver.workspace.ast.parsers.interfaces import FileBindings, Reference

_TYPES = ("class_declaration", "object_declaration")


def _is_declared_name(ident: typing.Any) -> bool:
    """A parameter, a variable, a `catch` or `for` variable."""
    parent = ident.parent
    if parent.type in ("parameter", "class_parameter", "variable_declaration"):
        return bool(
            ident == next((c for c in parent.named_children if c.type == "identifier"), None)
        )
    return bool(parent.type == "catch_block")


def _declares(node: typing.Any) -> str | None:
    return text(node) if node.type == "identifier" and _is_declared_name(node) else None


_GRAMMAR = _jvm.Grammar(
    types=_TYPES,
    scopes=("function_declaration", "lambda_literal", "anonymous_function"),
    headers=("import", "package_header"),
    import_node="import",
    identifiers=("identifier",),
    string_node="string_literal",
    string_content="string_content",
    comments=("line_comment", "block_comment"),
    receivers={"this_expression": "this", "super_expression": "super"},
    declares=_declares,
    anonymous=lambda node: node.type == "object_literal",
)


def _declared(ident: typing.Any) -> Reference | None:
    parent = ident.parent
    if parent.type in (*_TYPES, "function_declaration") and ident == parent.child_by_field_name(
        "name"
    ):
        return _jvm.definition(ident, parent, _GRAMMAR, is_type=parent.type in _TYPES)
    if _is_declared_name(ident):
        return ref("field", ident)
    if parent.type == "value_argument" and any(c.type == "=" for c in parent.children):
        return ref("keyword", ident)
    return None


def _member(ident: typing.Any) -> Reference | None:
    """`a.name(...)`, `a::name` or `::name`; `a.name` alone is a property, a `field`."""
    parent = ident.parent
    if parent.type == "callable_reference":
        receiver = parent.named_children[0]
        return (
            _jvm.call(ident, _GRAMMAR)
            if receiver == ident
            else _jvm.attribute(ident, receiver, _GRAMMAR)
        )
    if parent.type != "navigation_expression" or ident != parent.named_children[-1]:
        return None
    called = parent.parent is not None and parent.parent.type == "call_expression"
    if called or any(c.type == "::" for c in parent.children):
        return _jvm.attribute(ident, parent.named_children[0], _GRAMMAR)
    return ref("field", ident)


def _identifier(ident: typing.Any) -> Reference:
    declared = _declared(ident) or _member(ident)
    if declared is not None:
        return declared
    parent = ident.parent
    if parent.type == "user_type":
        names = [c for c in parent.named_children if c.type == "identifier"]
        qualifier = ".".join(text(n) for n in names[: names.index(ident)]) or None
        outer = _jvm.enclosing(ident, _GRAMMAR)
        return ref("type", ident, qualifier=qualifier, owner=outer[0] if outer else None)
    if parent.type == "call_expression" and ident == parent.named_children[0]:
        return _jvm.call(ident, _GRAMMAR)
    return _jvm.bare(ident, _GRAMMAR)


def _import_parts(node: typing.Any) -> tuple[list[typing.Any], str | None, bool]:
    """`(segments, alias, wildcard)` of an import."""
    path = next(c for c in node.named_children if c.type == "qualified_identifier")
    segments = [c for c in path.named_children if c.type == "identifier"]
    alias = next((c for c in node.named_children if c.type == "identifier"), None)
    wildcard = any(c.type == "*" for c in node.children)
    return segments, text(alias) if alias is not None else None, wildcard


def _imports(node: typing.Any, name: str) -> list[Reference]:
    segments, alias, wildcard = _import_parts(node)
    return _jvm.segment_refs(segments, wildcard, name, alias=alias)


#: Every place a name occurs under a tree's root, in byte order.
find_references = functools.partial(
    _jvm.scan, grammar=_GRAMMAR, imports=_imports, identifier=_identifier
)


def _bases(declaration: typing.Any) -> list[str]:
    specifiers = next(
        (c for c in declaration.named_children if c.type == "delegation_specifiers"), None
    )
    users = [
        user
        for user in (walk(specifiers) if specifiers is not None else [])
        if user.type == "user_type"
        and user.parent.type in ("delegation_specifier", "constructor_invocation")
    ]
    return [
        ".".join(text(i) for i in user.named_children if i.type == "identifier") for user in users
    ]


def _named(node: typing.Any) -> str | None:
    name = node.child_by_field_name("name")
    return text(name) if name is not None else None


def file_bindings(root: typing.Any) -> FileBindings:
    """The package, imports, top-level declarations and class bases of one Kotlin file."""
    facts = FileBindings()
    for node in root.named_children:
        if node.type == "package_header":
            facts.package = _dotted(node)
        elif node.type == "import":
            _add_import(facts, node)
        elif node.type in (*_TYPES, "function_declaration") and _named(node):
            facts.defs.add(str(_named(node)))
    for node in walk(root):
        if node.type in _TYPES and _named(node) and _bases(node):
            facts.bases[str(_named(node))] = _bases(node)
    return facts


def _dotted(header: typing.Any) -> str:
    path = next(c for c in header.named_children if c.type == "qualified_identifier")
    return ".".join(text(c) for c in path.named_children if c.type == "identifier")


def _add_import(facts: FileBindings, node: typing.Any) -> None:
    segments, alias, wildcard = _import_parts(node)
    names = [text(s) for s in segments]
    if wildcard:
        facts.wildcards.append(".".join(names))
    else:
        facts.imports[alias or names[-1]] = (".".join(names[:-1]), names[-1])


def _header(node: typing.Any) -> Reference | None:
    if not node.is_named or node.type not in ("package_header", "import"):
        return None
    path = next((c for c in node.named_children if c.type == "qualified_identifier"), None)
    if path is None:
        return None
    kind = "package" if node.type == "package_header" else "import"
    return _jvm.header_ref(kind, path, any(c.type == "*" for c in node.children))


def module_references(root: typing.Any) -> list[Reference]:
    """The `package` line (kind `package`) and each import's dotted path (kind `import`)."""
    return [r for r in map(_header, root.named_children) if r is not None]
