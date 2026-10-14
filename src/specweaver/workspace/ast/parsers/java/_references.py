# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Where a name occurs in one Java file, and what it is there.

Java keeps types, methods and variables apart: a field `greet` and a method `greet()` never
stand for each other, so each occurrence says which of the three it is.
"""

from __future__ import annotations

import functools
import typing

from specweaver.workspace.ast.parsers import _jvm
from specweaver.workspace.ast.parsers._ref_tools import ref, text, walk
from specweaver.workspace.ast.parsers.interfaces import FileBindings, Reference

_TYPES = ("class_declaration", "interface_declaration", "enum_declaration", "record_declaration")
_DECLARES = (
    "variable_declarator",
    "formal_parameter",
    "catch_formal_parameter",
    "enhanced_for_statement",
    "spread_parameter",
)


def _declares(node: typing.Any) -> str | None:
    if node.type in _DECLARES:
        name = node.child_by_field_name("name")
        return text(name) if name is not None else None
    parent = node.parent
    if node.type == "identifier" and parent is not None:
        lambda_param = parent.type == "lambda_expression" and node == parent.child_by_field_name(
            "parameters"
        )
        if lambda_param or parent.type == "inferred_parameters":
            return text(node)
    return None


def _anonymous(node: typing.Any) -> bool:
    return bool(
        node.type == "class_body"
        and node.parent is not None
        and node.parent.type == "object_creation_expression"
    )


_GRAMMAR = _jvm.Grammar(
    types=_TYPES,
    scopes=("method_declaration", "constructor_declaration", "lambda_expression"),
    headers=("import_declaration", "package_declaration"),
    import_node="import_declaration",
    identifiers=("identifier", "type_identifier"),
    string_node="string_literal",
    string_content="string_fragment",
    comments=("line_comment", "block_comment"),
    receivers={"this": "this", "super": "super"},
    declares=_declares,
    anonymous=_anonymous,
)


def _declared(ident: typing.Any) -> Reference | None:
    parent = ident.parent
    if ident != parent.child_by_field_name("name"):
        return None
    if parent.type in _TYPES:
        return _jvm.definition(ident, parent, _GRAMMAR, is_type=True)
    if parent.type == "method_declaration":
        return _jvm.definition(ident, parent, _GRAMMAR, is_type=False)
    if parent.type == "constructor_declaration":
        return ref("constructor", ident, owner=_jvm.enclosing(ident, _GRAMMAR)[0])
    return ref("field", ident) if parent.type in _DECLARES else None


def _used(ident: typing.Any) -> Reference:
    parent = ident.parent
    if parent.type == "method_invocation" and ident == parent.child_by_field_name("name"):
        receiver = parent.child_by_field_name("object")
        return (
            _jvm.call(ident, _GRAMMAR)
            if receiver is None
            else _jvm.attribute(ident, receiver, _GRAMMAR)
        )
    if parent.type == "method_reference" and ident == parent.children[-1]:
        return _jvm.attribute(ident, parent.children[0], _GRAMMAR)
    if parent.type == "field_access" and ident == parent.child_by_field_name("field"):
        return ref("field", ident)
    return _jvm.bare(ident, _GRAMMAR)


def _type_ref(node: typing.Any) -> Reference:
    parent = node.parent
    qualifier = None
    if parent.type == "scoped_type_identifier" and node == parent.named_children[-1]:
        qualifier = text(parent.named_children[0])
    outer = _jvm.enclosing(node, _GRAMMAR)
    return ref("type", node, qualifier=qualifier, owner=outer[0] if outer else None)


def _identifier(node: typing.Any) -> Reference:
    if node.type == "type_identifier":
        return _type_ref(node)
    return _declared(node) or _used(node)


def _import_parts(node: typing.Any) -> tuple[list[typing.Any], bool, bool]:
    """`(segments, static, wildcard)` of an import declaration."""
    path = next(c for c in node.named_children if c.type in ("scoped_identifier", "identifier"))
    segments = (
        [path] if path.type == "identifier" else [n for n in walk(path) if n.type == "identifier"]
    )
    static = any(c.type == "static" for c in node.children)
    wildcard = any(c.type == "asterisk" for c in node.children)
    return segments, static, wildcard


def _imports(node: typing.Any, name: str) -> list[Reference]:
    segments, static, wildcard = _import_parts(node)
    return _jvm.segment_refs(segments, wildcard, name, module="static" if static else None)


#: Every place a name occurs under a tree's root, in byte order.
find_references = functools.partial(
    _jvm.scan, grammar=_GRAMMAR, imports=_imports, identifier=_identifier
)


def _bases(declaration: typing.Any) -> list[str]:
    bases = []
    for child in declaration.children:
        if child.type not in ("superclass", "super_interfaces", "extends_interfaces"):
            continue
        for node in walk(child):
            outermost = node.parent.type not in ("scoped_type_identifier", "generic_type")
            if (
                node.type in ("type_identifier", "scoped_type_identifier", "generic_type")
                and outermost
            ):
                bases.append(text(node.named_children[0] if node.type == "generic_type" else node))
    return bases


def file_bindings(root: typing.Any) -> FileBindings:
    """The package, imports, top-level types and class bases of one Java file."""
    facts = FileBindings()
    for node in root.named_children:
        if node.type == "package_declaration":
            facts.package = text(node.named_children[0])
        elif node.type == "import_declaration":
            _add_import(facts, node)
        elif node.type in _TYPES:
            facts.defs.add(text(node.child_by_field_name("name")))
    for node in walk(root):
        if node.type in _TYPES and _bases(node):
            facts.bases[text(node.child_by_field_name("name"))] = _bases(node)
    return facts


def _add_import(facts: FileBindings, node: typing.Any) -> None:
    segments, static, wildcard = _import_parts(node)
    names = [text(s) for s in segments]
    if wildcard:
        facts.wildcards.append(("static " if static else "") + ".".join(names))
    elif static:
        facts.statics[names[-1]] = (".".join(names[:-1]), names[-1])
    else:
        facts.imports[names[-1]] = (".".join(names[:-1]), names[-1])
