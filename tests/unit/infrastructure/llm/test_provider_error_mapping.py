# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each provider's own errors become SpecWeaver's: auth, rate limit, model not found, the rest.

Proves: E-FLOW-03 FR-7

| Bucket | Case |
|---|---|
| Happy | OpenAI's and Anthropic's 401, 429 and 404 errors map to their SpecWeaver class |
| Boundary | an error with no class of its own is a generation error |
| Degradation | the original error stays attached as the cause |
| Hostile | not applicable — no user input reaches the mapping |
"""

from __future__ import annotations

import anthropic
import httpx2
import openai
import pytest

from specweaver.infrastructure.llm.adapters.anthropic import AnthropicAdapter
from specweaver.infrastructure.llm.adapters.openai import OpenAIAdapter
from specweaver.infrastructure.llm.errors import (
    AuthenticationError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)


def _response(code: int) -> httpx2.Response:
    return httpx2.Response(code, request=httpx2.Request("POST", "http://provider.example"))


@pytest.mark.parametrize(
    ("sdk", "adapter"),
    [(openai, OpenAIAdapter(api_key="k")), (anthropic, AnthropicAdapter(api_key="k"))],
)
@pytest.mark.parametrize(
    ("error", "code", "expected"),
    [
        ("AuthenticationError", 401, AuthenticationError),
        ("RateLimitError", 429, RateLimitError),
        ("NotFoundError", 404, ModelNotFoundError),
        ("InternalServerError", 500, GenerationError),
    ],
)
def test_a_provider_error_becomes_its_specweaver_class(sdk, adapter, error, code, expected) -> None:
    original = getattr(sdk, error)("failed", response=_response(code), body=None)

    with pytest.raises(expected) as caught:
        adapter._handle_error(original)

    assert type(caught.value) is expected
    assert caught.value.__cause__ is original
