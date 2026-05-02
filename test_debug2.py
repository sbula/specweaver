import asyncio

from specweaver.core.config.database import cqrs_context, get_global_write_queue


async def main():
    q = get_global_write_queue()
    await q.start()
    await q.stop()

    executed = False
    def cb():
        nonlocal executed
        executed = True

    q.enqueue_nowait(cb)

    async with cqrs_context():
        pass

    print(f"Executed: {executed}")

asyncio.run(main())
