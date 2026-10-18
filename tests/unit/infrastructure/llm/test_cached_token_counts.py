# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each adapter reads its provider's cached-token counts; an unreported count is unknown, never 0.

Proves: TECH-074 FR-3

The usage objects are the SDKs' own types, so a wrong field name fails here.

| Bucket | Case |
|---|---|
| Happy | Anthropic, OpenAI, vLLM, llama.cpp, Mistral and Gemini each give their cached counts |
| Boundary | Anthropic's prompt total adds the cached part it leaves out; sums across rounds |
| Degradation | a reply without the field is unknown, and a sum with an unknown part is unknown |
| Hostile | a count that is not a whole number, or is negative, is unknown |
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from anthropic.types import Usage
from google.genai import types as genai_types
from mistralai.client.models import UsageInfo
from openai.types.chat import ChatCompletion

from specweaver.infrastructure.llm.adapters import anthropic as anthropic_adapter
from specweaver.infrastructure.llm.adapters import mistral as mistral_adapter
from specweaver.infrastructure.llm.adapters import openai as openai_adapter
from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
from specweaver.infrastructure.llm.models import TokenUsage


def _counts(usage: TokenUsage) -> tuple[int, int | None, int | None, int]:
    return (
        usage.prompt_tokens,
        usage.cached_read_tokens,
        usage.cache_write_tokens,
        usage.total_tokens,
    )


class TestTheSum:
    def test_known_counts_add_up(self) -> None:
        a = TokenUsage(
            prompt_tokens=10, total_tokens=10, cached_read_tokens=4, cache_write_tokens=1
        )
        b = TokenUsage(
            prompt_tokens=20, total_tokens=20, cached_read_tokens=6, cache_write_tokens=0
        )

        assert _counts(a + b) == (30, 10, 1, 30)

    def test_an_unknown_part_makes_the_sum_unknown(self) -> None:
        a = TokenUsage(
            prompt_tokens=10, total_tokens=10, cached_read_tokens=4, cache_write_tokens=0
        )
        b = TokenUsage(prompt_tokens=20, total_tokens=20)

        assert _counts(a + b) == (30, None, None, 30)

    def test_nothing_reported_adds_nothing(self) -> None:
        a = TokenUsage(
            prompt_tokens=10, total_tokens=10, cached_read_tokens=4, cache_write_tokens=0
        )

        assert _counts(TokenUsage() + a) == (10, 4, 0, 10)


class TestAnthropic:
    def test_cached_reads_and_writes_join_the_prompt_total(self) -> None:
        usage = Usage(
            input_tokens=100,
            output_tokens=10,
            cache_read_input_tokens=900,
            cache_creation_input_tokens=50,
        )

        assert _counts(anthropic_adapter._usage_of(usage)) == (1050, 900, 50, 1060)

    def test_an_unreported_cache_is_unknown(self) -> None:
        usage = Usage(input_tokens=100, output_tokens=10)

        assert _counts(anthropic_adapter._usage_of(usage)) == (100, None, None, 110)


def _completion(usage: dict | None, **extra: object) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "c1",
            "object": "chat.completion",
            "created": 1,
            "model": "m",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
            **({"usage": usage} if usage else {}),
            **extra,
        }
    )


_PLAIN = {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010}


class TestOpenAI:
    def test_cached_tokens_are_read_and_writes_are_none(self) -> None:
        usage = {**_PLAIN, "prompt_tokens_details": {"cached_tokens": 800}}

        assert _counts(openai_adapter._usage_of(_completion(usage))) == (1000, 800, 0, 1010)

    def test_a_reported_cache_write_is_read(self) -> None:
        usage = {**_PLAIN, "prompt_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 30}}

        assert _counts(openai_adapter._usage_of(_completion(usage))) == (1000, 0, 30, 1010)

    def test_without_details_the_cache_is_unknown(self) -> None:
        assert _counts(openai_adapter._usage_of(_completion(_PLAIN))) == (1000, None, None, 1010)

    def test_llama_cpp_reports_its_cache_outside_usage(self) -> None:
        reply = _completion(_PLAIN, timings={"cache_n": 120, "prompt_n": 880})

        assert _counts(openai_adapter._usage_of(reply)) == (1000, 120, 0, 1010)

    def test_no_usage_at_all_is_nothing(self) -> None:
        assert openai_adapter._usage_of(_completion(None)) == TokenUsage()

    @pytest.mark.parametrize("bad", ["many", -5, 1.5])
    def test_a_count_that_is_not_a_whole_number_is_unknown(self, bad: object) -> None:
        usage = {**_PLAIN, "prompt_tokens_details": {}}
        reply = _completion(usage, timings={"cache_n": bad})

        assert _counts(openai_adapter._usage_of(reply))[1] is None


class TestMistral:
    def test_cached_tokens_arrive_as_an_extra_field(self) -> None:
        usage = UsageInfo.model_validate({**_PLAIN, "prompt_tokens_details": {"cached_tokens": 64}})

        assert _counts(mistral_adapter._usage_of(usage)) == (1000, 64, 0, 1010)

    def test_without_details_the_cache_is_unknown(self) -> None:
        assert _counts(mistral_adapter._usage_of(UsageInfo.model_validate(_PLAIN))) == (
            1000,
            None,
            None,
            1010,
        )


class TestGemini:
    def _usage(self, **counts: int) -> TokenUsage:
        meta = genai_types.GenerateContentResponseUsageMetadata(
            prompt_token_count=5000, candidates_token_count=10, total_token_count=5010, **counts
        )
        return GeminiAdapter.__new__(GeminiAdapter)._extract_usage(
            SimpleNamespace(usage_metadata=meta)
        )

    def test_cached_content_is_read(self) -> None:
        assert _counts(self._usage(cached_content_token_count=4096)) == (5000, 4096, 0, 5010)

    def test_without_the_count_the_cache_is_unknown(self) -> None:
        assert _counts(self._usage()) == (5000, None, None, 5010)
