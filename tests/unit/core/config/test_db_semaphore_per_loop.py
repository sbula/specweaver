# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each event loop gets its own database semaphore.

The CLI runs every command in a fresh loop (`anyio.run`, `run_sync`). A semaphore shared across
loops binds to the first loop that ever waited on it, and the next loop that has to wait crashes
with "bound to a different event loop".
"""

from __future__ import annotations

import asyncio

from specweaver.core.config import database


async def _contend() -> None:
    # Two holders on a limit of one: the second has to wait, which binds the semaphore to this loop.
    semaphore = database.get_db_semaphore(max_connections=1)

    async def hold() -> None:
        async with semaphore:
            await asyncio.sleep(0.01)

    await asyncio.gather(hold(), hold())


def test_a_second_event_loop_can_wait_on_its_own_semaphore() -> None:
    asyncio.run(_contend())
    asyncio.run(_contend())  # a new loop: must not reuse the first loop's semaphore


def test_one_loop_reuses_its_semaphore() -> None:
    async def twice() -> bool:
        return database.get_db_semaphore() is database.get_db_semaphore()

    assert asyncio.run(twice())
