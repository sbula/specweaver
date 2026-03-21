# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests — CLI validation module.

Tests: _apply_override, _load_check_settings.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import typer

from specweaver.config.settings import RuleOverride, ValidationSettings

# ---------------------------------------------------------------------------
# _apply_override
# ---------------------------------------------------------------------------


class TestApplyOverride:
    """Test _apply_override parsing and application."""

    def test_valid_enabled_true(self) -> None:
        """RULE.enabled=true → sets enabled=True."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        _apply_override(settings, "S08.enabled=true")
        assert settings.overrides["S08"].enabled is True

    def test_valid_enabled_false(self) -> None:
        """RULE.enabled=false → sets enabled=False."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        _apply_override(settings, "S08.enabled=false")
        assert settings.overrides["S08"].enabled is False

    def test_valid_warn_threshold(self) -> None:
        """RULE.warn_threshold=5 → sets warn_threshold=5.0."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        _apply_override(settings, "S08.warn_threshold=5")
        assert settings.overrides["S08"].warn_threshold == 5.0

    def test_valid_fail_threshold(self) -> None:
        """RULE.fail_threshold=10 → sets fail_threshold=10.0."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        _apply_override(settings, "S08.fail_threshold=10")
        assert settings.overrides["S08"].fail_threshold == 10.0

    def test_invalid_format_no_equals(self) -> None:
        """Missing '=' → typer.Exit(code=1)."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        with pytest.raises(typer.Exit) as exc_info:
            _apply_override(settings, "S08-warn_threshold-5")
        assert exc_info.value.exit_code == 1

    def test_invalid_format_no_dot(self) -> None:
        """Missing '.' → typer.Exit(code=1)."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        with pytest.raises(typer.Exit) as exc_info:
            _apply_override(settings, "S08warn=5")
        assert exc_info.value.exit_code == 1

    def test_invalid_threshold_value(self) -> None:
        """Non-numeric threshold → typer.Exit(code=1)."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        with pytest.raises(typer.Exit) as exc_info:
            _apply_override(settings, "S08.warn_threshold=abc")
        assert exc_info.value.exit_code == 1

    def test_rule_id_uppercased(self) -> None:
        """Rule IDs are uppercased."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        _apply_override(settings, "s08.enabled=true")
        assert "S08" in settings.overrides

    def test_extra_param(self) -> None:
        """Custom field → stored in extra_params."""
        from specweaver.cli.validation import _apply_override

        settings = ValidationSettings()
        _apply_override(settings, "S08.max_lines=100")
        assert settings.overrides["S08"].extra_params["max_lines"] == 100.0


# ---------------------------------------------------------------------------
# _load_check_settings
# ---------------------------------------------------------------------------


class TestLoadCheckSettings:
    """Test _load_check_settings cascade logic."""

    @patch("specweaver.cli.validation._core.get_db")
    def test_no_project_no_overrides_returns_none(self, mock_get_db) -> None:
        """No active project and no --set → None."""
        from specweaver.cli.validation import _load_check_settings

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = None
        mock_get_db.return_value = mock_db

        result = _load_check_settings(None)
        assert result is None

    @patch("specweaver.cli.validation._core.get_db")
    def test_set_overrides_without_project(self, mock_get_db) -> None:
        """No active project but --set flags → creates settings."""
        from specweaver.cli.validation import _load_check_settings

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = None
        mock_get_db.return_value = mock_db

        result = _load_check_settings(["S08.enabled=false"])
        assert result is not None
        assert "S08" in result.overrides
        assert result.overrides["S08"].enabled is False

    @patch("specweaver.cli.validation._core.get_db")
    def test_project_settings_loaded(self, mock_get_db) -> None:
        """Active project → loads settings from DB."""
        from specweaver.cli.validation import _load_check_settings

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "myproject"
        mock_db.load_validation_settings.return_value = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01", enabled=False)},
        )
        mock_get_db.return_value = mock_db

        result = _load_check_settings(None)
        assert result is not None
        assert result.overrides["S01"].enabled is False

    @patch("specweaver.cli.validation._core.get_db")
    def test_set_overrides_on_top_of_db(self, mock_get_db) -> None:
        """--set flags override DB settings."""
        from specweaver.cli.validation import _load_check_settings

        mock_db = MagicMock()
        mock_db.get_active_project.return_value = "myproject"
        mock_db.load_validation_settings.return_value = ValidationSettings(
            overrides={"S01": RuleOverride(rule_id="S01", enabled=True)},
        )
        mock_get_db.return_value = mock_db

        result = _load_check_settings(["S01.enabled=false"])
        assert result is not None
        assert result.overrides["S01"].enabled is False
