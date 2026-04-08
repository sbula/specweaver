# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for _require_llm_adapter telemetry wiring (Feature 3.12).

Verifies that _require_llm_adapter passes the active project name
as telemetry_project to create_llm_adapter, enabling automatic
TelemetryCollector wrapping.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


class TestRequireLlmAdapterTelemetry:
    """_require_llm_adapter passes telemetry_project to factory."""

    def test_passes_active_project_as_telemetry_project(self, tmp_path, monkeypatch):
        """When an active project exists, telemetry_project is set."""
        from specweaver.cli._helpers import _require_llm_adapter

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "my-project"
        monkeypatch.setattr("specweaver.cli._core.get_db", lambda: mock_db)

        fake_result = (MagicMock(), MagicMock(), MagicMock())
        with patch(
            "specweaver.llm.factory.create_llm_adapter",
            return_value=fake_result,
        ) as mock_create:
            _require_llm_adapter(tmp_path)

        mock_create.assert_called_once_with(
            mock_db,
            llm_role="draft",
            telemetry_project="my-project",
        )

    def test_passes_none_when_no_active_project(self, tmp_path, monkeypatch):
        """When no active project, telemetry_project is None."""
        from specweaver.cli._helpers import _require_llm_adapter

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = None
        monkeypatch.setattr("specweaver.cli._core.get_db", lambda: mock_db)

        fake_result = (MagicMock(), MagicMock(), MagicMock())
        with patch(
            "specweaver.llm.factory.create_llm_adapter",
            return_value=fake_result,
        ) as mock_create:
            _require_llm_adapter(tmp_path)

        mock_create.assert_called_once_with(
            mock_db,
            llm_role="draft",
            telemetry_project=None,
        )

    def test_passes_llm_role_through(self, tmp_path, monkeypatch):
        """llm_role parameter is still forwarded correctly."""
        from specweaver.cli._helpers import _require_llm_adapter

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "proj"
        monkeypatch.setattr("specweaver.cli._core.get_db", lambda: mock_db)

        fake_result = (MagicMock(), MagicMock(), MagicMock())
        with patch(
            "specweaver.llm.factory.create_llm_adapter",
            return_value=fake_result,
        ) as mock_create:
            _require_llm_adapter(tmp_path, llm_role="review")

        mock_create.assert_called_once_with(
            mock_db,
            llm_role="review",
            telemetry_project="proj",
        )
