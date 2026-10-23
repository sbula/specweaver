# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The folders above a file that a rule may search, never above the run's project root."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


def walk_up(start: Path, stop: Path | None) -> Iterator[Path]:
    """`start`, then each parent, ending at `stop` (the filesystem root when `stop` is None).

    A `start` outside `stop` yields only its own folders up to where it would pass `stop`'s level,
    so nothing above the project is ever searched.
    """
    boundary = stop.resolve() if stop is not None else None
    current = start
    while True:
        yield current
        parent = current.parent
        if parent == current:
            return
        if boundary is not None and not parent.resolve().is_relative_to(boundary):
            return
        current = parent
