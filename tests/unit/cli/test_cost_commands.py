# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Tests for ``sw costs`` sub-commands (Feature 3.12)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.cli import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.config.database import Database

    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.cli._core.get_db", lambda: db)
    return db


class TestCostsShow:
    """Tests for ``sw costs`` (show overrides)."""

    def test_costs_shows_defaults_when_no_overrides(self, _mock_db) -> None:
        """sw costs with no overrides → shows default pricing."""
        result = runner.invoke(app, ["costs"])

        assert result.exit_code == 0
        # Should show at least some default model
        assert "gemini" in result.output.lower() or "default" in result.output.lower()

    def test_costs_shows_overrides(self, _mock_db) -> None:
        """sw costs with an override → shows override."""
        _mock_db.set_cost_override("my-model", 0.01, 0.02)

        result = runner.invoke(app, ["costs"])

        assert result.exit_code == 0
        assert "my-model" in result.output


class TestCostsSet:
    """Tests for ``sw costs set``."""

    def test_set_cost_override(self, _mock_db) -> None:
        """sw costs set MODEL INPUT OUTPUT → persists override."""
        result = runner.invoke(
            app,
            ["costs", "set", "my-model", "0.005", "0.015"],
        )

        assert result.exit_code == 0
        overrides = _mock_db.get_cost_overrides()
        assert "my-model" in overrides
        assert overrides["my-model"] == (0.005, 0.015)


class TestCostsReset:
    """Tests for ``sw costs reset``."""

    def test_reset_cost_override(self, _mock_db) -> None:
        """sw costs reset MODEL → removes override."""
        _mock_db.set_cost_override("my-model", 0.01, 0.02)

        result = runner.invoke(
            app,
            ["costs", "reset", "my-model"],
        )

        assert result.exit_code == 0
        overrides = _mock_db.get_cost_overrides()
        assert "my-model" not in overrides
