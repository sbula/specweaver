# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Gemini's thinking tokens are billed as output, so they count as output.

Proves: B-FLOW-05 FR-1

| Bucket | Case |
|---|---|
| Happy | a reply with thinking counts candidates plus thoughts as output |
| Boundary | a reply without thinking counts the candidates alone |
| Degradation | a reply without usage counts nothing |
| Hostile | not applicable — usage comes from the provider, never from input |
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter


def _reply(**usage) -> SimpleNamespace:
    meta = SimpleNamespace(**usage) if usage else None
    return SimpleNamespace(text="ok", usage_metadata=meta, candidates=[], function_calls=None)


@pytest.mark.parametrize(
    ("usage", "output"),
    [
        ({"prompt_token_count": 5, "candidates_token_count": 10, "thoughts_token_count": 90}, 100),
        ({"prompt_token_count": 5, "candidates_token_count": 10, "thoughts_token_count": None}, 10),
        ({"prompt_token_count": 5, "candidates_token_count": 10}, 10),
        ({}, 0),
    ],
)
def test_thinking_counts_as_output(usage: dict, output: int) -> None:
    adapter = GeminiAdapter(api_key="k")

    assert adapter._extract_usage(_reply(**usage)).completion_tokens == output
    assert adapter._parse_response(_reply(**usage), "m").usage.completion_tokens == output
