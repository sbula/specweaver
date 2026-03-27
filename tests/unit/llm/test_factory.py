# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for llm/factory.py — telemetry wrapping (stories 2-5)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from specweaver.llm.telemetry import CostEntry

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def db(tmp_path: Path):
    """Fresh database with schema v9."""
    from specweaver.config.database import Database

    return Database(tmp_path / ".specweaver" / "specweaver.db")


class TestFactoryTelemetryWrapping:
    """Factory telemetry_project parameter behavior (stories 2-5)."""

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_no_telemetry_returns_raw_adapter(self, db):
        """telemetry_project=None → returns raw GeminiAdapter, not wrapped."""
        from specweaver.llm.adapters.gemini import GeminiAdapter
        from specweaver.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        _settings, adapter, _config = create_llm_adapter(db, telemetry_project=None)
        assert isinstance(adapter, GeminiAdapter)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_telemetry_project_wraps_in_collector(self, db):
        """telemetry_project set → adapter is wrapped in TelemetryCollector."""
        from specweaver.llm.collector import TelemetryCollector
        from specweaver.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        _settings, adapter, _config = create_llm_adapter(
            db, telemetry_project="test-proj",
        )
        assert isinstance(adapter, TelemetryCollector)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_empty_string_telemetry_project_no_wrap(self, db):
        """telemetry_project="" (falsy) → no wrapping."""
        from specweaver.llm.adapters.gemini import GeminiAdapter
        from specweaver.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        _settings, adapter, _config = create_llm_adapter(db, telemetry_project="")
        assert isinstance(adapter, GeminiAdapter)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_cost_overrides_passed_to_collector(self, db):
        """DB cost overrides are loaded and passed to TelemetryCollector."""
        from specweaver.llm.collector import TelemetryCollector
        from specweaver.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")
        db.set_cost_override("gemini-3-flash-preview", 99.0, 199.0)

        _settings, adapter, _config = create_llm_adapter(
            db, telemetry_project="test-proj",
        )
        assert isinstance(adapter, TelemetryCollector)
        assert adapter._cost_overrides is not None
        assert "gemini-3-flash-preview" in adapter._cost_overrides
        entry = adapter._cost_overrides["gemini-3-flash-preview"]
        assert entry == CostEntry(99.0, 199.0)

    @patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-1234"})
    def test_cost_override_load_failure_fallback(self, db):
        """DB error loading cost overrides → collector created with None."""
        from specweaver.llm.collector import TelemetryCollector
        from specweaver.llm.factory import create_llm_adapter

        db.register_project("test-proj", "/tmp/test")
        db.set_active_project("test-proj")

        # Simulate DB failure on get_cost_overrides
        original = db.get_cost_overrides
        db.get_cost_overrides = MagicMock(side_effect=Exception("DB locked"))

        _settings, adapter, _config = create_llm_adapter(
            db, telemetry_project="test-proj",
        )
        assert isinstance(adapter, TelemetryCollector)
        assert adapter._cost_overrides is None

        # Restore
        db.get_cost_overrides = original
