# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for llm/factory.py — telemetry wrapping (stories 2-5)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from specweaver.core.config.llm_settings import ModelFacts
from specweaver.core.config.settings import LLMSettings, SpecWeaverSettings
from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter


@pytest.fixture()
def base_settings() -> SpecWeaverSettings:
    return SpecWeaverSettings(
        llm=LLMSettings(provider="gemini", model="gemini-3-flash-preview", temperature=0.7)
    )


class TestFactoryTelemetryWrapping:
    """Factory telemetry_project parameter behavior (stories 2-5)."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_no_telemetry_returns_raw_adapter(self, base_settings: SpecWeaverSettings) -> None:
        """telemetry_project=None → returns raw GeminiAdapter, not wrapped."""
        _settings, adapter, _config = create_llm_adapter(base_settings, telemetry_project=None)

        assert isinstance(adapter, AsyncRateLimiterAdapter)
        assert isinstance(adapter._wrapped, GeminiAdapter)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_telemetry_project_wraps_in_collector(self, base_settings: SpecWeaverSettings) -> None:
        """telemetry_project set → adapter is wrapped in TelemetryCollector."""
        _settings, adapter, _config = create_llm_adapter(
            base_settings,
            telemetry_project="test-proj",
        )
        assert isinstance(adapter, TelemetryCollector)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_empty_string_telemetry_project_no_wrap(
        self, base_settings: SpecWeaverSettings
    ) -> None:
        """telemetry_project="" (falsy) → no wrapping."""
        _settings, adapter, _config = create_llm_adapter(base_settings, telemetry_project="")

        assert isinstance(adapter, AsyncRateLimiterAdapter)
        assert isinstance(adapter._wrapped, GeminiAdapter)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_the_machine_file_corrects_the_catalogue_price(
        self, base_settings: SpecWeaverSettings
    ) -> None:
        corrected = ModelFacts(usd_per_million_input=9.0, usd_per_million_output=19.0)

        _settings, adapter, _config = create_llm_adapter(
            base_settings,
            telemetry_project="test-proj",
            machine_models={"gemini-2.5-pro": corrected},
        )

        assert isinstance(adapter, TelemetryCollector)
        facts = adapter._prices("gemini-2.5-pro")
        assert (facts.usd_per_million_input, facts.usd_per_million_output) == (9.0, 19.0)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_without_corrections_the_catalogue_prices(
        self, base_settings: SpecWeaverSettings
    ) -> None:
        _settings, adapter, _config = create_llm_adapter(
            base_settings, telemetry_project="test-proj"
        )

        facts = adapter._prices("gemini-2.5-pro")
        assert facts is not None and facts.usd_per_million_input > 0
        assert adapter._prices("no-such-model") is None


class TestFactoryProviderCapabilities:
    """Factory handles dynamic provider loading based on DB settings."""

    @pytest.mark.parametrize(
        "provider,adapter_cls_name,env_key",
        [
            ("openai", "OpenAIAdapter", "OPENAI_API_KEY"),
            ("anthropic", "AnthropicAdapter", "ANTHROPIC_API_KEY"),
            ("mistral", "MistralAdapter", "MISTRAL_API_KEY"),
        ],
    )
    def test_factory_loads_specific_provider(
        self, provider: str, adapter_cls_name: str, env_key: str
    ) -> None:
        """Factory creates correct adapter based on provider setting."""
        from specweaver.infrastructure.llm.adapters.registry import get_adapter_class

        settings = SpecWeaverSettings(
            llm=LLMSettings(provider=provider, model="some-model", temperature=0.7)
        )

        with patch.dict(os.environ, {env_key: "dummy-key"}):
            _settings, adapter, _config = create_llm_adapter(settings, telemetry_project=None)

        expected_cls = get_adapter_class(provider)

        assert isinstance(adapter, AsyncRateLimiterAdapter)
        assert isinstance(adapter._wrapped, expected_cls)
        assert type(adapter._wrapped).__name__ == adapter_cls_name

    @pytest.mark.parametrize("provider", ["qwen", "openai-compatible"])
    def test_a_provider_without_an_official_address_points_to_the_settings_file(
        self, provider: str
    ) -> None:
        settings = SpecWeaverSettings(llm=LLMSettings(provider=provider, model="m", api_key="k"))

        with pytest.raises(LLMAdapterError, match=r"settings\.toml"):
            create_llm_adapter(settings, telemetry_project=None)
