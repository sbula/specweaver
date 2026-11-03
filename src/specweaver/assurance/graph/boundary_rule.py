# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The boundary rule: going down the folder tree a module gets stricter.

A module's `forbids` are its own plus all its ancestors'. Each of its `consumes` lies inside its
parent's `consumes` or `widens`, inside its parent's own folder (a sibling), or in its own `widens`,
which names each allowance with a reason. A `consumes` entry that overlaps a forbidden path, inside
it or containing it, breaks the rule unless `widens` covers it. A folder without a manifest takes
its nearest ancestor's rule.

An entry names a folder relative to the root: another manifest's `name`, a `/` path, or a dotted
path; a trailing `/*` means the folder itself. Pure: it judges loaded nodes and reads no file.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

    from specweaver.assurance.graph.topology import TopologyNode

_Parts = tuple[str, ...]


@dataclass(frozen=True)
class Breach:
    """One entry of one manifest that breaks the rule."""

    folder: str
    entry: str
    #: `wider`, `uses-forbidden`, `empty-reason`, `stale-widens` or `bad-entry`.
    kind: str
    parent: str | None


def breaches(nodes: Mapping[str, TopologyNode], root: Path) -> list[Breach]:
    """Every breach of the rule in the tree, by folder, in manifest order."""
    tree = _Tree(nodes, root)
    found: list[Breach] = []
    for folder in sorted(tree.folders):
        found.extend(tree.judge(folder))
    return found


def allows(nodes: Mapping[str, TopologyNode], root: Path, folder: str, target: str) -> bool:
    """Whether code in `folder` may use `target` under the nearest manifest's effective rule."""
    tree = _Tree(nodes, root)
    owner = tree.owner_of(_split(folder))
    wanted = tree.parts(target)
    if owner is None:
        return True
    if wanted is None:
        return False
    own, node = tree.folders[owner]
    used = _inside(wanted, own) or any(_overlap(c, wanted) for c in tree.parsed(node.consumes))
    widened = any(_inside(wanted, w) for w in tree.parsed(node.widens))
    forbidden = any(_inside(wanted, f) for f in tree.forbids(owner))
    return used and (widened or not forbidden)


class _Tree:
    def __init__(self, nodes: Mapping[str, TopologyNode], root: Path) -> None:
        self.folders: dict[str, tuple[_Parts, TopologyNode]] = {}
        self._names: dict[str, _Parts] = {}
        for node in nodes.values():
            folder = _folder_of(node, root)
            if folder is not None:
                self.folders["/".join(folder)] = (folder, node)
                self._names[node.name] = folder

    def parts(self, entry: str) -> _Parts | None:
        """The folder an entry names, or None when it names none (`..`, absolute, empty)."""
        text = str(entry).strip()
        if text in self._names:
            return self._names[text]
        if text.startswith("/") or "\\" in text:
            return None
        if "/" not in text:
            text = text.replace(".", "/")
        parts = _split(text.removesuffix("/*"))
        return None if not parts or ".." in parts else parts

    def parsed(self, entries: Iterable[str]) -> list[_Parts]:
        return [p for p in (self.parts(e) for e in entries) if p is not None]

    def owner_of(self, folder: _Parts) -> str | None:
        """The nearest folder at or above `folder` that has a manifest."""
        for depth in range(len(folder), -1, -1):
            key = "/".join(folder[:depth])
            if key in self.folders:
                return key
        return None

    def parent_of(self, folder: str) -> str | None:
        own = self.folders[folder][0]
        return self.owner_of(own[:-1]) if own else None

    def forbids(self, folder: str) -> list[_Parts]:
        own = self.parsed(self.folders[folder][1].forbids)
        parent = self.parent_of(folder)
        return own + (self.forbids(parent) if parent is not None else [])

    def judge(self, folder: str) -> list[Breach]:
        node = self.folders[folder][1]
        parent = self.parent_of(folder)
        bad = [e for e in [*node.consumes, *node.forbids] if self.parts(e) is None]
        found = [Breach(folder, entry, "bad-entry", parent) for entry in bad]
        needed, consumed = self._judge_consumes(folder, parent)
        found += consumed
        for key, reason in node.widens.items():
            if self.parts(key) is None:
                kind = "bad-entry"
            elif not reason.strip():
                kind = "empty-reason"
            elif key not in needed:
                kind = "stale-widens"
            else:
                continue
            found.append(Breach(folder, key, kind, parent))
        return found

    def _judge_consumes(self, folder: str, parent: str | None) -> tuple[set[str], list[Breach]]:
        """The `widens` keys some entry needs, and the entries no `widens` covers."""
        node = self.folders[folder][1]
        widens = {key: w for key in node.widens if (w := self.parts(key)) is not None}
        forbidden = self.forbids(folder)
        needed: set[str] = set()
        found: list[Breach] = []
        for entry in node.consumes:
            used = self.parts(entry)
            if used is None:
                continue
            kinds = self._kinds(used, parent, forbidden)
            covering = {k for k, w in widens.items() if _inside(used, w)}
            if kinds and covering:
                needed |= covering
            else:
                found += [Breach(folder, entry, kind, parent) for kind in kinds]
        return needed, found

    def _kinds(self, used: _Parts, parent: str | None, forbidden: list[_Parts]) -> list[str]:
        """How an entry breaks the rule before any `widens` is applied."""
        kinds = []
        if parent is not None and not self._within_parent(used, parent):
            kinds.append("wider")
        if any(_overlap(used, f) for f in forbidden):
            kinds.append("uses-forbidden")
        return kinds

    def _within_parent(self, used: _Parts, parent: str) -> bool:
        own, node = self.folders[parent]
        allowed = self.parsed([*node.consumes, *node.widens])
        return _inside(used, own) or any(_inside(used, a) for a in allowed)


def _folder_of(node: TopologyNode, root: Path) -> _Parts | None:
    if node.yaml_path is None:
        return None
    folder = node.yaml_path.parent
    try:
        relative = folder.relative_to(root)
    except ValueError:  # expected: the root may be given unresolved; compare resolved paths
        try:
            relative = folder.resolve().relative_to(root.resolve())
        except ValueError:  # expected: a manifest outside the root has no place in its tree
            return None
    return _split(relative.as_posix())


def _split(text: str) -> _Parts:
    return tuple(part for part in text.split("/") if part not in ("", "."))


def _inside(path: _Parts, pattern: _Parts) -> bool:
    """`path` is `pattern` or below it; a pattern part may be a glob."""
    return len(path) >= len(pattern) and all(
        fnmatchcase(p, q) for p, q in zip(path, pattern, strict=False)
    )


def _overlap(a: _Parts, b: _Parts) -> bool:
    """One of the two paths is the other or below it."""
    return all(fnmatchcase(x, y) or fnmatchcase(y, x) for x, y in zip(a, b, strict=False))
