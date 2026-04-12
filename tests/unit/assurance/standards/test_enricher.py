# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for StandardsEnricher."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from specweaver.assurance.standards.analyzer import CategoryResult
from specweaver.assurance.standards.enricher import StandardsEnricher
from specweaver.infrastructure.llm.adapters.base import LLMAdapter
from specweaver.infrastructure.llm.models import LLMResponse


class DummyAdapter(LLMAdapter):
    def __init__(self, responses: list[str]):
        self.responses = responses
        self._provider_name = "dummy"

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def generate(self, messages, config) -> LLMResponse:
        text = self.responses.pop(0) if self.responses else "{}"
        return LLMResponse(text=text, model="dummy", finish_reason="stop")

    async def generate_stream(self, messages, config):
        yield ""

    def available(self) -> bool:
        return True

    async def count_tokens(self, text, model):
        return 0


@pytest.mark.asyncio
class TestStandardsEnricher:
    async def test_skips_enrichment_if_confidence_high(self) -> None:
        adapter = DummyAdapter([])
        adapter.generate = AsyncMock()  # type: ignore
        enricher = StandardsEnricher(adapter)

        res = CategoryResult(
            category="naming", dominant={"style": "snake"}, confidence=0.95, sample_size=10
        )

        await enricher.enrich([res], "python", confidence_threshold=0.9)

        adapter.generate.assert_not_called()

    async def test_enriches_if_confidence_low(self) -> None:
        json_resp = '{"industry_standard": "PascalCase", "is_conflict": true, "conflict_reason": "snake is wrong"}'
        adapter = DummyAdapter([json_resp])
        enricher = StandardsEnricher(adapter)

        res = CategoryResult(
            category="naming", dominant={"style": "snake"}, confidence=0.5, sample_size=10
        )

        await enricher.enrich([res], "python", confidence_threshold=0.9)

        assert len(res.conflicts) == 1
        assert res.conflicts[0] == "snake is wrong"

    async def test_enriches_if_force_compare_true(self) -> None:
        json_resp = '{"industry_standard": "snake", "is_conflict": false}'
        adapter = DummyAdapter([json_resp])
        enricher = StandardsEnricher(adapter)

        # High confidence, but forced
        res = CategoryResult(
            category="naming", dominant={"style": "snake"}, confidence=0.99, sample_size=10
        )

        await enricher.enrich([res], "python", confidence_threshold=0.9, force_compare=True)

        assert len(res.conflicts) == 0  # no conflicts added because is_conflict=False

    async def test_handles_invalid_json_gracefully(self) -> None:
        # Invalid JSON missing quotes
        json_resp = '{industry_standard: "PascalCase", is_conflict: true}'
        adapter = DummyAdapter([json_resp])
        enricher = StandardsEnricher(adapter)

        res = CategoryResult(
            category="naming", dominant={"style": "snake"}, confidence=0.5, sample_size=10
        )

        # Should not raise exception
        await enricher.enrich([res], "python", confidence_threshold=0.9)

        assert len(res.conflicts) == 0
