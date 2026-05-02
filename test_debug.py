import asyncio

from specweaver.core.config.database import get_global_write_queue


async def main():
    q = get_global_write_queue()
    await q.start()

    executed = False
    def cb():
        nonlocal executed
        executed = True

    await q.stop()

    q.enqueue_nowait(cb)

    await q.start()
    await q.flush()
    await q.stop()

    print(f"Executed: {executed}")

asyncio.run(main())
