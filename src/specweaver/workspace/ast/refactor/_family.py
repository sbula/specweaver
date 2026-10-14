# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A class's override family: every class linked to it by extends or implements, in any direction.

A method renamed in one class of the family is renamed in all of them, so an override never
loses its parent. A base outside the project may call the method by its old name, so a family
with such a base refuses.
"""

from __future__ import annotations

#: `(file, class name)`.
ClassId = tuple[str, str]

#: A class's bases: `(text as written, what it resolves to)`; `("def", file, name)` is a project class.
Parents = dict[ClassId, list[tuple[str, tuple[str, ...]]]]


def hierarchy(parents: Parents, target: ClassId) -> set[ClassId]:
    """`target` and every project class reachable from it through a base, up or down."""
    links: dict[ClassId, set[ClassId]] = {}
    for child, bases in parents.items():
        for _, found in bases:
            if found[0] == "def":
                parent = (found[1], found[2])
                links.setdefault(child, set()).add(parent)
                links.setdefault(parent, set()).add(child)
    seen, todo = {target}, [target]
    while todo:
        for nxt in links.get(todo.pop(), set()):
            if nxt not in seen:
                seen.add(nxt)
                todo.append(nxt)
    return seen


def outside_bases(parents: Parents, family: set[ClassId], harmless: frozenset[str]) -> list[str]:
    """The bases of the family that are not project classes, except those that add no methods."""
    return [
        text
        for cls in sorted(family)
        for text, found in parents.get(cls, [])
        if found[0] != "def" and text not in harmless
    ]
