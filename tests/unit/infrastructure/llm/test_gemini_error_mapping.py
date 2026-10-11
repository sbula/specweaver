# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A Gemini error is named by its status code, not by words in its message.

Found on a real call, 2026-10-10: Google's 503 "This model is currently experiencing high demand"
was reported as "model not found", because the mapping matched the word "model".

Proves: E-FLOW-03 FR-7

| Bucket | Case |
|---|---|
| Happy | 401/403 → authentication, 429 → rate limit, 404 → model not found |
| Boundary | a 503 whose message says "model" is an ordinary generation error, keeping its text |
| Degradation | an error with no status code falls back to its text |
| Hostile | a message mentioning "model" never decides the class |
"""

from __future__ import annotations

import pytest
from google.genai import errors

from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
from specweaver.infrastructure.llm.errors import (
    AuthenticationError,
    GenerationError,
    ModelNotFoundError,
    RateLimitError,
)


def _api(code: int, message: str) -> errors.APIError:
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "message": message, "status": "X"}})


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (401, AuthenticationError),
        (403, AuthenticationError),
        (429, RateLimitError),
        (404, ModelNotFoundError),
        (503, GenerationError),
        (500, GenerationError),
    ],
)
def test_the_status_code_decides(code: int, expected: type) -> None:
    with pytest.raises(expected) as caught:
        GeminiAdapter(api_key="k")._handle_error(_api(code, "This model is busy"))

    assert type(caught.value) is expected
    assert str(code) in str(caught.value)


def test_a_plain_message_about_a_model_is_not_model_not_found() -> None:
    with pytest.raises(GenerationError) as caught:
        GeminiAdapter(api_key="k")._handle_error(Exception("the model returned nothing"))

    assert type(caught.value) is GenerationError
