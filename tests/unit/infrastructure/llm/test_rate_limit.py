# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

import asyncio
from collections.abc import AsyncIterator

import pytest
from pydantic import BaseModel

from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, Message


class MockAdapterConfig(BaseModel):
    delay: float = 0.05


class StubAdapter(LLMAdapter):
    provider_name = "stub_provider"
    api_key_env_var = "STUB_API"

    def __init__(self, config: MockAdapterConfig | None = None) -> None:
        self._config = config or MockAdapterConfig()

    async def generate(self, messages: list[Message], config: GenerationConfig) -> LLMResponse:
        from specweaver.infrastructure.llm.models import TokenUsage

        await asyncio.sleep(self._config.delay)
        return LLMResponse(
            text="success",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
            finish_reason="stop",
            model="stub",
        )

    async def generate_stream(
        self, messages: list[Message], config: GenerationConfig
    ) -> AsyncIterator[str]:
        await asyncio.sleep(self._config.delay)
        yield "success"

    async def generate_with_tools(
        self, messages, config, tool_executor, on_tool_round=None, before_request=None
    ) -> LLMResponse:
        from specweaver.infrastructure.llm.models import TokenUsage

        await asyncio.sleep(self._config.delay)
        return LLMResponse(
            text="tools",
            usage=TokenUsage(prompt_tokens=1, completion_tokens=1),
            finish_reason="stop",
            model="stub",
        )

    def available(self) -> bool:
        return True

    async def count_tokens(self, text: str, model: str) -> int:
        return 42

    def estimate_tokens(self, text: str) -> int:
        return 21


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Clear global semaphores between tests."""
    from specweaver.infrastructure.llm.adapters._rate_limit import _SEMAPHORES

    _SEMAPHORES.clear()
    yield
    _SEMAPHORES.clear()


@pytest.mark.asyncio
async def test_rate_limiter_translates_metadata():
    stub = StubAdapter()
    adapter = AsyncRateLimiterAdapter(stub, limit=2)
    assert adapter.provider_name == "stub_provider"
    assert adapter.api_key_env_var == "STUB_API"
    assert adapter.available() is True
    assert adapter.estimate_tokens("hi") == 21
    assert await adapter.count_tokens("hi", "test") == 42


class CountingAdapter(StubAdapter):
    """Records the most calls it ever had in flight at once."""

    def __init__(self, delay: float = 0.05) -> None:
        super().__init__(MockAdapterConfig(delay=delay))
        self.active = 0
        self.peak = 0

    async def generate(self, messages, config):
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            return await super().generate(messages, config)
        finally:
            self.active -= 1

    async def generate_with_tools(
        self, messages, config, tool_executor, on_tool_round=None, before_request=None
    ):
        return await self.generate(messages, config)


@pytest.mark.asyncio
async def test_a_busy_server_makes_calls_wait_not_fail():
    stub = CountingAdapter()
    adapter = AsyncRateLimiterAdapter(stub, limit=2, key="gb10")

    results = await asyncio.gather(
        *(
            adapter.generate([], GenerationConfig(model="m", max_output_tokens=1000))
            for _ in range(4)
        )
    )

    assert [r.text for r in results] == ["success"] * 4
    assert stub.peak == 2


@pytest.mark.asyncio
async def test_two_servers_of_the_same_kind_do_not_share_slots():
    stub = CountingAdapter()
    first = AsyncRateLimiterAdapter(stub, limit=1, key="gb10")
    second = AsyncRateLimiterAdapter(stub, limit=1, key="gb10-backup")

    await asyncio.gather(
        first.generate([], GenerationConfig(model="m", max_output_tokens=1000)),
        second.generate([], GenerationConfig(model="m", max_output_tokens=1000)),
    )

    assert stub.peak == 2


@pytest.mark.asyncio
async def test_adapters_for_one_server_share_its_slots():
    stub = CountingAdapter()
    first = AsyncRateLimiterAdapter(stub, limit=1, key="gb10")
    second = AsyncRateLimiterAdapter(stub, limit=1, key="gb10")

    await asyncio.gather(
        first.generate([], GenerationConfig(model="m", max_output_tokens=1000)),
        second.generate([], GenerationConfig(model="m", max_output_tokens=1000)),
    )

    assert stub.peak == 1


def test_each_event_loop_gets_its_own_semaphore():
    adapter = AsyncRateLimiterAdapter(CountingAdapter(delay=0.01), limit=1, key="gb10")

    async def contended() -> None:
        await asyncio.gather(
            *(
                adapter.generate([], GenerationConfig(model="m", max_output_tokens=1000))
                for _ in range(2)
            )
        )

    asyncio.run(contended())
    asyncio.run(contended())  # a semaphore bound to the first loop would raise here


@pytest.mark.asyncio
async def test_a_cancelled_call_frees_its_slot():
    adapter = AsyncRateLimiterAdapter(CountingAdapter(delay=10), limit=1, key="gb10")
    stuck = asyncio.create_task(
        adapter.generate([], GenerationConfig(model="m", max_output_tokens=1000))
    )
    await asyncio.sleep(0.01)
    stuck.cancel()
    adapter._wrapped._config.delay = 0

    result = await asyncio.wait_for(
        adapter.generate([], GenerationConfig(model="m", max_output_tokens=1000)), timeout=1
    )

    assert result.text == "success"


@pytest.mark.asyncio
async def test_a_stream_closed_early_frees_its_slot():
    class TwoChunks(StubAdapter):
        async def generate_stream(self, messages, config):
            yield "one"
            yield "two"

    adapter = AsyncRateLimiterAdapter(TwoChunks(MockAdapterConfig(delay=0)), limit=1, key="gb10")
    stream = adapter.generate_stream([], GenerationConfig(model="m", max_output_tokens=1000))
    assert await anext(stream) == "one"
    await stream.aclose()

    result = await asyncio.wait_for(
        adapter.generate([], GenerationConfig(model="m", max_output_tokens=1000)), timeout=1
    )

    assert result.text == "success"


@pytest.mark.asyncio
async def test_rate_limiter_releases_lock_on_exception():
    class ExceptionAdapter(StubAdapter):
        async def generate(self, messages, config):
            raise ValueError("Upstream API 500 Error")

    stub = ExceptionAdapter()
    adapter = AsyncRateLimiterAdapter(stub, limit=1)

    # 1. Fire a failing request
    with pytest.raises(ValueError, match="Upstream API 500 Error"):
        await adapter.generate([], GenerationConfig(model="stub", max_output_tokens=1000))

    # 2. Lock should be released! Fire again and it should NOT timeout.
    # We prove the lock is available because we don't throw Timeout LLMAdapterError
    with pytest.raises(ValueError, match="Upstream API 500 Error"):
        await asyncio.wait_for(
            adapter.generate([], GenerationConfig(model="stub", max_output_tokens=1000)),
            timeout=0.1,
        )


@pytest.mark.asyncio
async def test_rate_limiter_wraps_generate_with_tools():
    stub = CountingAdapter()
    adapter = AsyncRateLimiterAdapter(stub, limit=1, key="gb10")

    results = await asyncio.gather(
        *(
            adapter.generate_with_tools(
                [], GenerationConfig(model="m", max_output_tokens=1000), tool_executor=None
            )
            for _ in range(2)
        )
    )

    assert [r.text for r in results] == ["success"] * 2
    assert stub.peak == 1


@pytest.mark.asyncio
async def test_rate_limiter_stream_delegation():
    stub = StubAdapter(MockAdapterConfig(delay=0.0))
    adapter = AsyncRateLimiterAdapter(stub, limit=2)

    chunks = []
    async for chunk in adapter.generate_stream(
        [], GenerationConfig(model="stub", max_output_tokens=1000)
    ):
        chunks.append(chunk)

    assert chunks == ["success"]


async def test_an_edited_parallel_limit_applies_without_a_restart() -> None:
    import asyncio

    from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter

    running = 0
    most = 0

    class _Slow:
        provider_name = "fake"
        api_key_env_var = ""

        async def generate(self, _messages, _config):
            nonlocal running, most
            running += 1
            most = max(most, running)
            await asyncio.sleep(0.02)
            running -= 1

    AsyncRateLimiterAdapter(_Slow(), limit=1, key="edited")._get_semaphore()
    widened = AsyncRateLimiterAdapter(_Slow(), limit=3, key="edited")

    await asyncio.gather(*(widened.generate([], None) for _ in range(3)))

    assert most == 3


async def test_two_server_names_on_one_address_share_one_limit() -> None:
    from specweaver.core.config.llm_settings import ServerEntry
    from specweaver.infrastructure.llm.servers import adapter_for_server

    def entry() -> ServerEntry:
        return ServerEntry(
            kind="openai-compatible", base_url="http://gb10:8000/v1", private=True, max_parallel=1
        )

    first = adapter_for_server("gb10", entry())
    second = adapter_for_server("gb10-again", entry())

    assert first._get_semaphore() is second._get_semaphore()
