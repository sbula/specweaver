# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for llm/factory.py — telemetry wrapping (stories 2-5)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from specweaver.infrastructure.llm.telemetry import CostEntry

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db(tmp_path: Path) -> Any:
    """Fresh database with schema v9."""
    from specweaver.core.config.database import Database

    return Database(tmp_path / ".specweaver" / "specweaver.db")


class TestFactoryTelemetryWrapping:
    """Factory telemetry_project parameter behavior (stories 2-5)."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_no_telemetry_returns_raw_adapter(self, db: Any) -> None:
        """telemetry_project=None → returns raw GeminiAdapter, not wrapped."""
        from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
        from specweaver.infrastructure.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        _settings, adapter, _config = create_llm_adapter(db, telemetry_project=None)
        from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
        assert isinstance(adapter, AsyncRateLimiterAdapter)
        assert isinstance(adapter._wrapped, GeminiAdapter)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_telemetry_project_wraps_in_collector(self, db: Any) -> None:
        """telemetry_project set → adapter is wrapped in TelemetryCollector."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.infrastructure.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        _settings, adapter, _config = create_llm_adapter(
            db,
            telemetry_project="test-proj",
        )
        assert isinstance(adapter, TelemetryCollector)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_empty_string_telemetry_project_no_wrap(self, db: Any) -> None:
        """telemetry_project="" (falsy) → no wrapping."""
        from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
        from specweaver.infrastructure.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        _settings, adapter, _config = create_llm_adapter(db, telemetry_project="")
        from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
        assert isinstance(adapter, AsyncRateLimiterAdapter)
        assert isinstance(adapter._wrapped, GeminiAdapter)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_cost_overrides_passed_to_collector(self, db: Any) -> None:
        """DB cost overrides are loaded and passed to TelemetryCollector."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.infrastructure.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")
        db.set_cost_override("gemini-3-flash-preview", 99.0, 199.0)

        _settings, adapter, _config = create_llm_adapter(
            db,
            telemetry_project="test-proj",
        )
        assert isinstance(adapter, TelemetryCollector)
        assert adapter._cost_overrides is not None
        assert "gemini-3-flash-preview" in adapter._cost_overrides
        entry = adapter._cost_overrides["gemini-3-flash-preview"]
        assert entry == CostEntry(99.0, 199.0)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_cost_override_load_failure_fallback(self, db: Any) -> None:
        """DB error loading cost overrides → collector created with None."""
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.infrastructure.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        # Simulate DB failure on get_cost_overrides
        original = db.get_cost_overrides
        db.get_cost_overrides = MagicMock(side_effect=Exception("DB locked"))

        _settings, adapter, _config = create_llm_adapter(
            db,
            telemetry_project="test-proj",
        )
        assert isinstance(adapter, TelemetryCollector)
        assert adapter._cost_overrides is None

        db.get_cost_overrides = original


class TestFactoryProviderCapabilities:
    """Factory handles dynamic provider loading based on DB settings."""

    @pytest.mark.parametrize(
        "provider,adapter_cls_name,env_key",
        [
            ("openai", "OpenAIAdapter", "OPENAI_API_KEY"),
            ("anthropic", "AnthropicAdapter", "ANTHROPIC_API_KEY"),
            ("mistral", "MistralAdapter", "MISTRAL_API_KEY"),
            ("qwen", "QwenAdapter", "QWEN_API_KEY"),
        ],
    )
    def test_factory_loads_specific_provider(
        self, db: Any, provider: str, adapter_cls_name: str, env_key: str
    ) -> None:
        """Factory creates correct adapter based on DB provider setting."""
        from specweaver.infrastructure.llm.adapters.registry import get_adapter_class
        from specweaver.infrastructure.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        # Override the active setting for the provider
        profile_id = db.create_llm_profile("test-profile", provider=provider, model="some-model")
        db.link_project_profile("test-proj", "draft", profile_id)

        with patch.dict(os.environ, {env_key: "dummy-key"}):
            _settings, adapter, _config = create_llm_adapter(db, telemetry_project=None)

        expected_cls = get_adapter_class(provider)
        from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
        assert isinstance(adapter, AsyncRateLimiterAdapter)
        assert isinstance(adapter._wrapped, expected_cls)
        assert type(adapter._wrapped).__name__ == adapter_cls_name

    def test_factory_fallback_on_missing_project(self, db: Any) -> None:
        """Factory defaults cleanly to gemini if no active project exists."""
        from specweaver.infrastructure.llm.adapters.gemini import GeminiAdapter
        from specweaver.infrastructure.llm.factory import create_llm_adapter

        # Ensure no active project
        assert db.get_active_project() is None

        with patch.dict(os.environ, {"GEMINI_API_KEY": "fallback-key"}):
            settings, adapter, config = create_llm_adapter(db, telemetry_project=None)

        from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter
        assert isinstance(adapter, AsyncRateLimiterAdapter)
        assert isinstance(adapter._wrapped, GeminiAdapter)
        assert settings.llm.provider == "gemini"
        assert config.model == "gemini-3-flash-preview"
