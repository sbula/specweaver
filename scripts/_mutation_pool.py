#!/usr/bin/env python3
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Schedule work across a pool of sandboxes, returning results in the order the work was given.

Knows nothing about mutants, verdicts or worktrees — only how many workers to run and how to keep
the output ordered.

Every dependency is injected. `mutation.py` is the module tests monkeypatch, so importing
`build_sandbox` here would run the real one while a test patched the name it could see.
"""

from __future__ import annotations

import queue
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


def size_for(workers: int, work_count: int) -> int:
    """How many sandboxes to actually build.

    Never more than there is work: eight workers for two mutants is six worktrees built to sit idle,
    at 0.2s and a `git worktree` entry each.
    """
    return max(1, min(workers, work_count))


def run_ordered(
    work: list[Any],
    pool_size: int,
    *,
    run_one: Callable[[Path, Any], Any],
    build: Callable[[], Path],
    remove: Callable[[Path], None],
    prepare: Callable[[Path], Any],
) -> list[Any]:
    """Each item of `work` on some sandbox, returned in the order `work` was given.

    The ordering is the part worth stating. Appending as futures complete orders the report by
    finishing time, so two nights of the same corpus produce diffs that say nothing about the code —
    which is exactly what a nightly report exists to make readable. Indices are carried through and
    the results re-sorted at the end.

    `prepare` runs once per sandbox and its result is handed back to `run_one` for that sandbox — the
    cleanliness snapshot each leak check is measured against, which is per-worktree and must not be
    shared.
    """
    sandboxes = [build() for _ in range(pool_size)]
    free: queue.Queue[Path] = queue.Queue()
    prepared: dict[Path, Any] = {}
    for box in sandboxes:
        prepared[box] = prepare(box)
        free.put(box)

    def _one(item: tuple[int, Any]) -> tuple[int, Any]:
        index, payload = item
        box = free.get()
        try:
            return index, run_one(box, payload, prepared[box])
        finally:
            free.put(box)

    try:
        with ThreadPoolExecutor(max_workers=pool_size) as pool:
            done = list(pool.map(_one, enumerate(work)))
    finally:
        for box in sandboxes:
            remove(box)

    return [result for _, result in sorted(done, key=lambda pair: pair[0])]
