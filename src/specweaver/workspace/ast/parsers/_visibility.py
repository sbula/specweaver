# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reading a declaration's access level off the tree.

These are **free functions, not methods, and that is the point.** A visibility rule is a pure
function of one AST node: it reads no object state and needs none. Attaching it to each parser
class made `check_class_health` report a new LCOM4 component in Java, Kotlin, Rust and
TypeScript — the metric saying, correctly, that the rule was a separate concern wearing a method's
clothes.

Each language keeps its own rule, since the rules genuinely differ. What lives here is the part
they share: scanning a declaration for a keyword, and walking up for an enclosing construct.
"""

from __future__ import annotations

import typing
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from specweaver.workspace.ast.parsers.interfaces import Visibility


#: The access keywords each grammar spells out, in the order they must be tested. They live beside
#: `keyword_level` rather than in the language modules because three near-identical tuples in three
#: files is the shape that drifts -- and because the tuple is data about the vocabulary, not about
#: the parser.
JAVA_ACCESS: tuple[tuple[bytes, Visibility], ...] = (
    (b"public", "public"),
    (b"protected", "protected"),
    (b"private", "private"),
)

KOTLIN_ACCESS: tuple[tuple[bytes, Visibility], ...] = (
    (b"private", "private"),
    (b"protected", "protected"),
    (b"internal", "internal"),
)

TYPESCRIPT_ACCESS: tuple[tuple[bytes, Visibility], ...] = (
    (b"private", "private"),
    (b"protected", "protected"),
    (b"public", "public"),
)


def keyword_level(
    declaration: typing.Any,
    child_type: str,
    access: tuple[tuple[bytes, Visibility], ...],
) -> Visibility | None:
    """The first access keyword this declaration carries, or None if it carries none.

    Java, Kotlin and TypeScript differ only in which child node holds the keywords and which
    keywords those are, so the scan itself is written once. Three copies of it would be three
    places the answers can drift apart.
    """
    if declaration is None:
        return None
    for child in declaration.children:
        if child.type == child_type and child.text:
            for keyword, level in access:
                if keyword in child.text:
                    return level
    return None


def enclosed_by(node: typing.Any, want: tuple[str, ...], stop: tuple[str, ...]) -> bool:
    """Whether the nearest enclosing construct is one of `want` rather than one of `stop`.

    The container decides what "no modifier" means: package-private inside a Java class, implicitly
    public inside a Java interface. Walking to the first of EITHER set is what makes the answer the
    *nearest* container's rather than any ancestor's — a method inside a class inside an interface
    is package-private, not public.
    """
    parent = node.parent if node is not None else None
    while parent:
        if parent.type in want:
            return True
        if parent.type in stop:
            return False
        parent = parent.parent
    return False


def has_ancestor(node: typing.Any, node_type: str) -> bool:
    """Whether any ancestor is of `node_type`. Used for TypeScript's module-level `export`."""
    while node:
        if node.type == node_type:
            return True
        node = node.parent
    return False


def name_text(name_node: typing.Any) -> str:
    """The identifier this node spells, decoded."""
    return typing.cast("bytes", name_node.text).decode("utf-8")
