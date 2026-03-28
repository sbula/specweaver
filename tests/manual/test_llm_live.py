import os

import pytest

from specweaver.llm.models import GenerationConfig, Message, Role


@pytest.mark.live
@pytest.mark.asyncio
async def test_llm_live_gemini_connection() -> None:
    """Manual test to connect to the real Gemini API."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set. Cannot run live test.")

    from specweaver.llm.adapters.gemini import GeminiAdapter

    adapter = GeminiAdapter(api_key=api_key)

    messages = [
        Message(role=Role.USER, content="Reply specifically with ONLY the word 'Pleb' and nothing else.")
    ]
    config = GenerationConfig(model="gemini-3-flash-preview")

    print(f"\n[LIVE] Sending payload to {adapter.provider_name}...")
    response = await adapter.generate(messages, config)

    assert response
    assert response.text.strip().upper() == "PLEB"


@pytest.mark.live
@pytest.mark.asyncio
async def test_llm_live_openai_connection() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set. Cannot run live test.")
    from specweaver.llm.adapters.openai import OpenAIAdapter
    adapter = OpenAIAdapter(api_key=api_key)
    messages = [Message(role=Role.USER, content="Reply specifically with ONLY the word 'Pleb' and nothing else.")]
    config = GenerationConfig(model="gpt-5.4-mini")
    print(f"\n[LIVE] Sending payload to {adapter.provider_name}...")
    response = await adapter.generate(messages, config)
    assert response
    assert "PLEB" in response.text.strip().upper()


@pytest.mark.live
@pytest.mark.asyncio
async def test_llm_live_anthropic_connection() -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set.")
    from specweaver.llm.adapters.anthropic import AnthropicAdapter
    adapter = AnthropicAdapter(api_key=api_key)
    messages = [Message(role=Role.USER, content="Reply specifically with ONLY the word 'Pleb' and nothing else.")]
    config = GenerationConfig(model="claude-4-6-sonnet")
    response = await adapter.generate(messages, config)
    assert response
    assert "PLEB" in response.text.upper()


@pytest.mark.live
@pytest.mark.asyncio
async def test_llm_live_mistral_connection() -> None:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        pytest.skip("MISTRAL_API_KEY not set.")
    from specweaver.llm.adapters.mistral import MistralAdapter
    adapter = MistralAdapter(api_key=api_key)
    messages = [Message(role=Role.USER, content="Reply specifically with ONLY the word 'Pleb' and nothing else.")]
    config = GenerationConfig(model="mistral-small-4")
    response = await adapter.generate(messages, config)
    assert response
    assert "PLEB" in response.text.upper()


@pytest.mark.live
@pytest.mark.asyncio
async def test_llm_live_qwen_connection() -> None:
    api_key = os.environ.get("QWEN_API_KEY")
    if not api_key:
        pytest.skip("QWEN_API_KEY not set.")
    from specweaver.llm.adapters.qwen import QwenAdapter
    adapter = QwenAdapter(api_key=api_key)
    messages = [Message(role=Role.USER, content="Reply specifically with ONLY the word 'Pleb' and nothing else.")]
    config = GenerationConfig(model="qwen3.5-plus")
    response = await adapter.generate(messages, config)
    assert response
    assert "PLEB" in response.text.upper()
