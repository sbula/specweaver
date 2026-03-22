import os

import pytest

from specweaver.llm.models import GenerationConfig, Message, Role


@pytest.mark.live
@pytest.mark.asyncio
async def test_llm_live_gemini_connection():
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
