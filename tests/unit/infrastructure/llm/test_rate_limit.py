import asyncio
from typing import AsyncIterator

import pytest
from pydantic import BaseModel

from specweaver.core.config.settings import SpecWeaverSettings
from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.factory import LLMAdapterError
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
        return LLMResponse(text="success", usage=TokenUsage(prompt_tokens=1, completion_tokens=1), finish_reason="stop", model="stub")

    async def generate_stream(self, messages: list[Message], config: GenerationConfig) -> AsyncIterator[str]:
        await asyncio.sleep(self._config.delay)
        yield "success"

    async def generate_with_tools(self, messages, config, tool_executor, on_tool_round=None) -> LLMResponse:
        from specweaver.infrastructure.llm.models import TokenUsage
        await asyncio.sleep(self._config.delay)
        return LLMResponse(text="tools", usage=TokenUsage(prompt_tokens=1, completion_tokens=1), finish_reason="stop", model="stub")

    def available(self) -> bool:
        return True

    async def count_tokens(self, text: str, model: str) -> int:
        return 42

    def estimate_tokens(self, text: str) -> int:
        return 21


@pytest.fixture(autouse=True)
def reset_rate_limit_state():
    """Clear global semaphores between tests."""
    from specweaver.infrastructure.llm.adapters._rate_limit import _PROVIDER_SEMAPHORES
    _PROVIDER_SEMAPHORES.clear()
    yield
    _PROVIDER_SEMAPHORES.clear()


@pytest.mark.asyncio
async def test_rate_limiter_translates_metadata():
    stub = StubAdapter()
    adapter = AsyncRateLimiterAdapter(stub, limit=2)
    assert adapter.provider_name == "stub_provider"
    assert adapter.api_key_env_var == "STUB_API"
    assert adapter.available() is True
    assert adapter.estimate_tokens("hi") == 21
    assert await adapter.count_tokens("hi", "test") == 42


@pytest.mark.asyncio
async def test_rate_limiter_concurrency_bounds():
    stub = StubAdapter(MockAdapterConfig(delay=0.1))
    adapter = AsyncRateLimiterAdapter(stub, limit=2, timeout=0.05)
    
    # We fire 3 requests. Limit is 2. The 3rd should timeout because the delay is 0.1s, 
    # but the timeout wait is only 0.05s.
    
    config = GenerationConfig(model="stub")
    
    tasks = [
        asyncio.create_task(adapter.generate([], config)),
        asyncio.create_task(adapter.generate([], config)),
        asyncio.create_task(adapter.generate([], config)),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successes = [r for r in results if isinstance(r, LLMResponse)]
    errors = [r for r in results if isinstance(r, Exception)]
    
    assert len(successes) == 2
    assert len(errors) == 1
    
    assert isinstance(errors[0], LLMAdapterError)
    assert "concurrency" in str(errors[0]).lower()


@pytest.mark.asyncio
async def test_rate_limiter_releases_lock_on_exception():
    class ExceptionAdapter(StubAdapter):
        async def generate(self, messages, config):
            raise ValueError("Upstream API 500 Error")

    stub = ExceptionAdapter()
    adapter = AsyncRateLimiterAdapter(stub, limit=1)

    # 1. Fire a failing request
    with pytest.raises(ValueError, match="Upstream API 500 Error"):
        await adapter.generate([], GenerationConfig(model="stub"))

    # 2. Lock should be released! Fire again and it should NOT timeout.
    # We prove the lock is available because we don't throw Timeout LLMAdapterError
    with pytest.raises(ValueError, match="Upstream API 500 Error"):
        await asyncio.wait_for(adapter.generate([], GenerationConfig(model="stub")), timeout=0.1)


@pytest.mark.asyncio
async def test_rate_limiter_wraps_generate_with_tools():
    stub = StubAdapter(MockAdapterConfig(delay=0.1))
    adapter = AsyncRateLimiterAdapter(stub, limit=1, timeout=0.05)
    
    config = GenerationConfig(model="stub")
    
    # Prove successful delegation
    res = await adapter.generate_with_tools([], config, tool_executor=None)
    assert res.text == "tools"
    
    # Prove it obeys the concurrency limits
    tasks = [
        asyncio.create_task(adapter.generate_with_tools([], config, tool_executor=None)),
        asyncio.create_task(adapter.generate_with_tools([], config, tool_executor=None)),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    successes = [r for r in results if isinstance(r, LLMResponse)]
    errors = [r for r in results if isinstance(r, Exception)]
    
    assert len(successes) == 1
    assert len(errors) == 1
    assert isinstance(errors[0], LLMAdapterError)
    assert "concurrency" in str(errors[0]).lower()


@pytest.mark.asyncio
async def test_rate_limiter_stream_delegation():
    stub = StubAdapter(MockAdapterConfig(delay=0.0))
    adapter = AsyncRateLimiterAdapter(stub, limit=2)
    
    chunks = []
    async for chunk in adapter.generate_stream([], GenerationConfig(model="stub")):
        chunks.append(chunk)
        
    assert chunks == ["success"]
