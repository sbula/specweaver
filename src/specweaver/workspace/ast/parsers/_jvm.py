# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The reference finder Java and Kotlin share; each language gives its grammar's node names.

Both speak one vocabulary, so one resolver judges both: a call with no receiver is `call`, a
call on something `attribute`, a name in a type `type`, a declared variable `field`.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass

from specweaver.workspace.ast.parsers._ref_tools import (
    comment_ref,
    literal_ref,
    ref,
    text,
    walk,
    word,
)

if typing.TYPE_CHECKING:
    from collections.abc import Callable

    from specweaver.workspace.ast.parsers.interfaces import Reference


@dataclass(frozen=True)
class Grammar:
    """What one JVM grammar calls the nodes the finder needs."""

    types: tuple[str, ...]
    scopes: tuple[str, ...]
    headers: tuple[str, ...]
    import_node: str
    identifiers: tuple[str, ...]
    string_node: str
    string_content: str
    comments: tuple[str, ...]
    receivers: dict[str, str]
    declares: Callable[[typing.Any], str | None]
    anonymous: Callable[[typing.Any], bool]


def enclosing(node: typing.Any, grammar: Grammar) -> tuple[str, ...]:
    """The names of the type declarations around `node`, innermost first."""
    names = []
    parent = node.parent
    while parent is not None:
        if parent.type in grammar.types and parent.child_by_field_name("name") is not None:
            names.append(text(parent.child_by_field_name("name")))
        parent = parent.parent
    return tuple(names)


def in_anonymous(node: typing.Any, grammar: Grammar) -> bool:
    """Whether `node` sits in an anonymous class nearer than any named type."""
    parent = node.parent
    while parent is not None and parent.type not in grammar.types:
        if grammar.anonymous(parent):
            return True
        parent = parent.parent
    return False


def binding(node: typing.Any, grammar: Grammar) -> str:
    """`local` when the method or lambda around `node` declares its name, else `free`."""
    scope = node.parent
    while scope is not None and scope.type not in grammar.scopes:
        scope = scope.parent
    if scope is None:
        return "free"
    declared = {grammar.declares(inner) for inner in walk(scope)}
    return "local" if text(node) in declared else "free"


def receiver_binding(receiver: typing.Any, grammar: Grammar) -> str | None:
    if receiver.type in grammar.receivers:
        return grammar.receivers[receiver.type]
    return binding(receiver, grammar) if receiver.type == "identifier" else None


def attribute(ident: typing.Any, receiver: typing.Any, grammar: Grammar) -> Reference:
    outer = enclosing(ident, grammar)
    return ref(
        "attribute",
        ident,
        owner=outer[0] if outer else None,
        enclosing=outer,
        receiver=text(receiver),
        receiver_binding=receiver_binding(receiver, grammar),
    )


def call(ident: typing.Any, grammar: Grammar) -> Reference:
    outer = enclosing(ident, grammar)
    kind = "anonymous" if in_anonymous(ident, grammar) else "plain"
    return ref("call", ident, owner=outer[0] if outer else None, enclosing=outer, binding=kind)


def bare(ident: typing.Any, grammar: Grammar) -> Reference:
    outer = enclosing(ident, grammar)
    owner = outer[0] if outer else None
    return ref("bare", ident, owner=owner, enclosing=outer, binding=binding(ident, grammar))


def definition(
    ident: typing.Any, declaration: typing.Any, grammar: Grammar, is_type: bool
) -> Reference:
    outer = enclosing(declaration, grammar)
    return ref(
        "definition",
        ident,
        scope="class" if outer else "module",
        owner=outer[0] if outer else None,
        binding="type" if is_type else None,
    )


def segment_refs(
    segments: list[typing.Any], wildcard: bool, name: str, **extra: typing.Any
) -> list[Reference]:
    """An import's segments that are `name`, each with the dotted text before it."""
    found = []
    for i, segment in enumerate(segments):
        if text(segment) == name:
            last = i == len(segments) - 1 and not wildcard
            qualifier = ".".join(text(s) for s in segments[:i])
            found.append(
                ref(
                    "import",
                    segment,
                    qualifier=qualifier,
                    scope="last" if last else "inner",
                    **extra,
                )
            )
    return found


def _inside(node: typing.Any, types: tuple[str, ...]) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in types:
            return True
        parent = parent.parent
    return False


def _text_like(node: typing.Any, name: str, grammar: Grammar) -> Reference | None:
    pattern = word(name)
    if node.type == grammar.string_node:
        return literal_ref(node, name, pattern, (grammar.string_content,))
    return comment_ref(node, pattern)


def scan(
    root: typing.Any,
    name: str,
    grammar: Grammar,
    imports: Callable[[typing.Any, str], list[Reference]],
    identifier: Callable[[typing.Any], Reference],
) -> list[Reference]:
    """Every place `name` occurs under `root`, in byte order."""
    if not name:
        return []
    found: list[Reference] = []
    for node in walk(root):
        if node.type == grammar.import_node and node.is_named:
            found.extend(imports(node, name))
        elif node.type in grammar.identifiers and text(node) == name:
            if not _inside(node, grammar.headers):
                found.append(identifier(node))
        elif node.type == grammar.string_node or node.type in grammar.comments:
            mention = _text_like(node, name, grammar)
            if mention:
                found.append(mention)
    return sorted(found, key=lambda r: r.start_byte)
