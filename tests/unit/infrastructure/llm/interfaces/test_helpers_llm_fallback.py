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
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".specweaver-test" / "specweaver.db"))
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.get_db", lambda: db)
    return db


# ---------------------------------------------------------------------------
# _require_llm_adapter fallback chain (gap #22, #23)
# ---------------------------------------------------------------------------


class TestRequireLlmAdapterFallback:
    """_require_llm_adapter falls back to system-default profile when active project fails."""

    def test_fallback_uses_system_default_model(self, _mock_db, tmp_path: Path, monkeypatch):
        """When load_settings_for_active raises, fallback reads system-default profile."""
        from specweaver.infrastructure.llm.interfaces.cli import _require_llm_adapter

        # Ensure GEMINI_API_KEY is set so adapter.available() returns True
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Mock _run_workspace_op to return a project that triggers a missing settings error
        with patch(
            "specweaver.workspace.project.interfaces.cli._run_workspace_op", return_value="fake-project"
        ):
            # Mock load_settings to simulate project settings failing
            with patch("specweaver.core.config.settings_loader.load_settings") as mock_load:
                from specweaver.core.config.settings import SpecWeaverSettings

                # First call fails (project profile), second call succeeds (system-default)
                def side_effect(db, project, llm_role=None, fallback_to_default=True):
                    if project == "fake-project" and llm_role == "draft":
                        raise ValueError("No active project")
                    # Return system default on fallback
                    return SpecWeaverSettings(
                        llm={
                            "provider": "gemini",
                            "model": "gemini-3-flash-preview",
                            "api_key": "test",
                        }
                    )

                mock_load.side_effect = side_effect

                with patch(
                    "specweaver.infrastructure.llm.adapters.gemini.GeminiAdapter"
                ) as mock_adapter_cls:
                    mock_adapter = MagicMock()
                    mock_adapter.available.return_value = True
                    mock_adapter_cls.return_value = mock_adapter

                    _settings, adapter, gen_config = _require_llm_adapter(tmp_path)

        # Should have fallen back to system-default model
        assert gen_config.model == "gemini-3-flash-preview"
        assert adapter.available()

    def test_fallback_when_db_profile_also_fails(self, tmp_path: Path, monkeypatch):
        """When both load_settings_for_active AND DB profile lookup fail → hardcoded fallback."""
        from specweaver.infrastructure.llm.interfaces.cli import _require_llm_adapter

        monkeypatch.setenv("GEMINI_API_KEY", "test-key")

        # Mock get_db to return a DB
        mock_db = MagicMock()
        monkeypatch.setattr("specweaver.core.config.cli_db_utils.get_db", lambda: mock_db)

        # Mock _run_workspace_op
        with patch(
            "specweaver.workspace.project.interfaces.cli._run_workspace_op", return_value="fake-project"
        ):
            # Simulate both project profile AND system-default failing to load
            with patch("specweaver.core.config.settings_loader.load_settings") as mock_load:
                mock_load.side_effect = ValueError("No active project")

                with patch(
                    "specweaver.infrastructure.llm.adapters.gemini.GeminiAdapter"
                ) as mock_adapter_cls:
                    mock_adapter = MagicMock()
                    mock_adapter.available.return_value = True
                    mock_adapter_cls.return_value = mock_adapter

                    _settings, _adapter, gen_config = _require_llm_adapter(tmp_path)

        # Should use hardcoded fallback model
        assert gen_config.model == "gemini-3-flash-preview"
