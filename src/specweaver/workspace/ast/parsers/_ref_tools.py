# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Small pieces every language's reference finder uses: walk, text, a reference at a node."""

from __future__ import annotations

import re
import typing

from specweaver.workspace.ast.parsers.interfaces import (
    CodeStructureInterface,
    FileBindings,
    Reference,
)


def text(node: typing.Any) -> str:
    return str(node.text.decode("utf-8", errors="replace"))


def walk(root: typing.Any) -> typing.Iterator[typing.Any]:
    """Every node under `root`, in source order."""
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(reversed(node.children))


def word(name: str) -> re.Pattern[str]:
    """`name` as a whole word."""
    return re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")


def ref(kind: str, node: typing.Any, **extra: typing.Any) -> Reference:
    return Reference(kind, node.start_point[0] + 1, node.start_byte, node.end_byte, **extra)


def literal_ref(
    node: typing.Any, name: str, pattern: re.Pattern[str], content_types: tuple[str, ...]
) -> Reference | None:
    """A string whose content is `name` is `string`; one that holds it as a word is `text`."""
    content = "".join(text(c) for c in node.children if c.type in content_types)
    if content == name and all(c.type in content_types for c in node.named_children):
        return ref("string", node)
    return ref("text", node) if pattern.search(content) else None


def comment_ref(node: typing.Any, pattern: re.Pattern[str]) -> Reference | None:
    return ref("text", node) if pattern.search(text(node)) else None


def inside(node: typing.Any, kinds: tuple[str, ...]) -> bool:
    """Whether any ancestor of `node` is one of `kinds`."""
    parent = node.parent
    while parent is not None:
        if parent.type in kinds:
            return True
        parent = parent.parent
    return False


def mention(
    node: typing.Any,
    name: str,
    pattern: re.Pattern[str],
    strings: dict[str, str],
    comments: tuple[str, ...],
    skip_parents: tuple[str, ...] = (),
) -> Reference | None:
    """A string or comment holding `name`: `strings` maps a string node to its content node."""
    if node.type in strings and node.parent is not None and node.parent.type not in skip_parents:
        return literal_ref(node, name, pattern, (strings[node.type],))
    if node.type in comments:
        return comment_ref(node, pattern)
    return None


class Renames(CodeStructureInterface):
    """Mixin for a parser whose language renames: `_finder` gives its reference finder."""

    parser: typing.Any

    def _finder(self) -> typing.Any:
        raise NotImplementedError

    def _root(self, code: str) -> typing.Any:
        return self.parser.parse(code.encode("utf-8")).root_node

    def find_references(self, code: str, name: str) -> list[Reference]:
        return list(self._finder().find_references(self._root(code), name))

    def file_bindings(self, code: str) -> FileBindings:
        return typing.cast("FileBindings", self._finder().file_bindings(self._root(code)))

    def supported_intents(self) -> list[str]:
        return [*super().supported_intents(), "rename"]
