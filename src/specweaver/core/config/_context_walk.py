# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Walking up the directory tree for the nearest `context.yaml` answer.

Three resolvers — `ArchetypeResolver.resolve`, `ArchetypeResolver.resolve_plugins` and
`DALResolver.resolve` — need the same forty-line walk, differing only in which cache they read and
which value they parse out. Hand-rolled, each one is over the complexity ceiling for it.

The two halt conditions are the subtle part and are stated once here rather than three times:
the walk stops at `project_root` **and** at the filesystem root, because a target outside the
project would otherwise climb to `/` before giving up.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

T = TypeVar("T")

CONTEXT_FILENAME = "context.yaml"


def resolve_up_tree(
    target_path: Path,
    project_root: Path,
    cache: Mapping[Path, T | None],
    parse: Callable[[Path], T | None],
) -> tuple[T | None, list[Path]]:
    """The nearest `context.yaml` answer at or above `target_path`.

    Returns the value (or None when nothing declares one) together with every directory walked, so
    the caller can backfill its cache — including the negative result, which is what stops a miss
    from re-walking the whole tree next time.

    A cached entry short-circuits immediately, and a cached `None` counts: it means "already looked
    here and found nothing".

    The cache is a read-only `Mapping` so callers may pass a stricter one — the plugin cache holds
    `list[str]` with no `None`, and a `dict` parameter would be invariant and reject it.
    """
    current = target_path.resolve()
    seen: list[Path] = []

    while True:
        if current in cache:
            return cache[current], seen

        seen.append(current)

        value = _declared_at(current, parse)
        if value is not None:
            return value, seen

        parent = _next_dir(current, project_root)
        if parent is None:
            break
        current = parent

    return None, seen


def _declared_at(directory: Path, parse: Callable[[Path], T | None]) -> T | None:
    """What this directory's `context.yaml` declares, or None if it has none to declare."""
    if not directory.is_dir():
        return None
    context_file = directory / CONTEXT_FILENAME
    return parse(context_file) if context_file.is_file() else None


def _next_dir(current: Path, project_root: Path) -> Path | None:
    """The directory to look at next, or None when the walk must stop.

    Two halts, and both are needed: `project_root` bounds a normal lookup, and the filesystem root
    catches a target that lies *outside* the project and would otherwise climb to `/`.
    """
    if current == project_root:
        return None
    parent = current.parent
    return None if parent == current else parent
