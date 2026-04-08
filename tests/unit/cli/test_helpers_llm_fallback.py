# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for CLI _helpers — _require_llm_adapter fallback chain.

Covers gap analysis items:
- #22: _require_llm_adapter — fallback model from DB system-default profile
- #23: _require_llm_adapter — DB profile also fails → hardcoded fallback
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# _require_llm_adapter fallback chain (gap #22, #23)
# ---------------------------------------------------------------------------


class TestRequireLlmAdapterFallback:
    """_require_llm_adapter falls back to system-default profile when active project fails."""

    def test_fallback_uses_system_default_model(self, _mock_db, tmp_path: Path, monkeypatch):
        """When load_settings_for_active raises, fallback reads system-default profile."""
        from specweaver.cli._helpers import _require_llm_adapter

        # Ensure GEMINI_API_KEY is set so adapter.available() returns True
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Patch at the source module (lazy imports inside the function)
        with patch("specweaver.llm.adapters.gemini.GeminiAdapter") as mock_adapter_cls:
            mock_adapter = MagicMock()
            mock_adapter.available.return_value = True
            mock_adapter_cls.return_value = mock_adapter

            _settings, adapter, gen_config = _require_llm_adapter(tmp_path)

        # Should have fallen back to system-default model
        assert gen_config.model == "gemini-3-flash-preview"
        assert adapter.available()

    def test_fallback_when_db_profile_also_fails(self, tmp_path: Path, monkeypatch):
        """When both load_settings_for_active AND DB profile lookup fail → hardcoded fallback."""
        from specweaver.cli._helpers import _require_llm_adapter

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Mock get_db to return a DB that raises on profile lookup
        mock_db = MagicMock()
        mock_db.get_llm_profile_by_name.side_effect = Exception("DB corrupt")
        monkeypatch.setattr("specweaver.cli._core.get_db", lambda: mock_db)

        # Patch load_settings_for_active at the source module
        with patch("specweaver.config.settings.load_settings_for_active") as mock_load:
            mock_load.side_effect = ValueError("No active project")

            with patch("specweaver.llm.adapters.gemini.GeminiAdapter") as mock_adapter_cls:
                mock_adapter = MagicMock()
                mock_adapter.available.return_value = True
                mock_adapter_cls.return_value = mock_adapter

                _settings, _adapter, gen_config = _require_llm_adapter(tmp_path)

        # Should use hardcoded fallback model
        assert gen_config.model == "gemini-3-flash-preview"
