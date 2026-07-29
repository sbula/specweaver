# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Run async work from synchronous code without corrupting a running event loop.

Three call sites needed this and all three did it the same wrong way: `nest_asyncio.apply(loop)`
followed by `loop.run_until_complete(...)` on the loop that was ALREADY RUNNING.

Re-entering a running loop corrupts it. The nested run drains the loop's `_ready` deque while the
outer `_run_once` is partway through::

    ntodo = len(self._ready)
    for i in range(ntodo):
        handle = self._ready.popleft()      # IndexError: pop from an empty deque

Three properties made that expensive to diagnose:

* The damage lands on the OUTER loop, so the caller's own `try/except` never sees it.
* Whether it fires depends on what else is scheduled, so it reads as flakiness. The integration
  test `test_telemetry_roundtrip` passed when the whole tier ran and failed when its file ran
  alone — a green suite that was one scheduling change away from red.
* `nest_asyncio` patches the loop CLASS process-wide, so the first caller silently changes
  behaviour for every later one.

It was not test-only. `PipelineRunner._flush_telemetry()` runs in the `finally` of
`async def run()` and `async def resume()`, so every `sw run` took this path.

The fix is to stop re-entering. When a loop is already running, the coroutine goes to a private
loop on a worker thread; when none is, it runs directly. Both are ordinary asyncio.

**Prefer a native `await` where one exists** — `TelemetryCollector.flush_async` over `flush`, for
example. This bridge is for call sites that are genuinely synchronous, not a licence to call
async code from anywhere.

Safety requirement for callers: whatever the coroutine touches must not be bound to the calling
loop. That holds for the current callers because each builds its own SQLAlchemy engine with
`NullPool` and disposes it.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, TypeVar

import anyio

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

T = TypeVar("T")


def run_sync(make_coroutine: Callable[[], Coroutine[object, object, T]]) -> T:
    """Run an async callable to completion from synchronous code.

    Takes a zero-argument callable rather than a coroutine object so the coroutine is created on
    the loop that will actually run it.

    Args:
        make_coroutine: Zero-argument callable returning the coroutine to run.

    Returns:
        Whatever the coroutine returns.
    """
    try:
        loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop is not None and loop.is_running():
        # A private loop on its own thread. Never re-enter the caller's.
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="sync-bridge") as pool:
            return pool.submit(anyio.run, make_coroutine).result()

    return anyio.run(make_coroutine)
