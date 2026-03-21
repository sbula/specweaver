# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Unit tests — CLI config subcommands.

Tests all 10 config commands via CliRunner with mocked DB.
"""

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


def _create_project(db, name: str = "testproj") -> str:
    """Register and activate a project in the DB."""
    db.register_project(name, ".")
    db.set_active_project(name)
    return name


# ---------------------------------------------------------------------------
# config set / get / list / reset
# ---------------------------------------------------------------------------


class TestConfigSetGetListReset:
    """Test config set/get/list/reset subcommands."""

    def test_set_requires_at_least_one_option(self, _mock_db) -> None:
        """config set without any option → exit 1."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set", "S08"])
        assert result.exit_code == 1
        assert "Provide at least one" in result.output

    def test_set_enabled(self, _mock_db) -> None:
        """config set --enabled → success."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set", "S08", "--enabled"])
        assert result.exit_code == 0
        assert "S08" in result.output

    def test_set_warn_threshold(self, _mock_db) -> None:
        """config set --warn → success."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set", "S08", "--warn", "5.0"])
        assert result.exit_code == 0

    def test_set_fail_threshold(self, _mock_db) -> None:
        """config set --fail → success."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set", "S08", "--fail", "10.0"])
        assert result.exit_code == 0

    def test_get_no_override(self, _mock_db) -> None:
        """config get with no override → shows default message."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "get", "S99"])
        assert result.exit_code == 0
        assert "No override" in result.output or "defaults" in result.output

    def test_get_existing_override(self, _mock_db) -> None:
        """config get after set → shows the override."""
        _create_project(_mock_db)
        runner.invoke(app, ["config", "set", "S08", "--warn", "5.0"])
        result = runner.invoke(app, ["config", "get", "S08"])
        assert result.exit_code == 0
        assert "S08" in result.output

    def test_list_empty(self, _mock_db) -> None:
        """config list with no overrides → shows default message."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "No overrides" in result.output or "defaults" in result.output

    def test_list_with_overrides(self, _mock_db) -> None:
        """config list after setting overrides → shows them."""
        _create_project(_mock_db)
        runner.invoke(app, ["config", "set", "S08", "--warn", "5.0"])
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "S08" in result.output

    def test_reset_removes_override(self, _mock_db) -> None:
        """config reset → removes the override."""
        _create_project(_mock_db)
        runner.invoke(app, ["config", "set", "S08", "--warn", "5.0"])
        result = runner.invoke(app, ["config", "reset", "S08"])
        assert result.exit_code == 0
        assert "removed" in result.output.lower() or "S08" in result.output


# ---------------------------------------------------------------------------
# config log-level
# ---------------------------------------------------------------------------


class TestConfigLogLevel:
    """Test config set-log-level / get-log-level."""

    def test_set_log_level(self, _mock_db) -> None:
        """set-log-level → success."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set-log-level", "DEBUG"])
        assert result.exit_code == 0
        assert "DEBUG" in result.output

    def test_get_log_level(self, _mock_db) -> None:
        """get-log-level → shows current level."""
        _create_project(_mock_db)
        runner.invoke(app, ["config", "set-log-level", "WARNING"])
        result = runner.invoke(app, ["config", "get-log-level"])
        assert result.exit_code == 0
        assert "WARNING" in result.output

    def test_set_invalid_log_level(self, _mock_db) -> None:
        """set-log-level with invalid value → exit 1."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set-log-level", "INVALID"])
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# config constitution-max-size
# ---------------------------------------------------------------------------


class TestConfigConstitutionMaxSize:
    """Test config constitution max size commands."""

    def test_set_constitution_max_size(self, _mock_db) -> None:
        """set-constitution-max-size → success."""
        _create_project(_mock_db)
        result = runner.invoke(
            app, ["config", "set-constitution-max-size", "5000"],
        )
        assert result.exit_code == 0
        assert "5000" in result.output

    def test_get_constitution_max_size(self, _mock_db) -> None:
        """get-constitution-max-size → shows value."""
        _create_project(_mock_db)
        runner.invoke(app, ["config", "set-constitution-max-size", "3000"])
        result = runner.invoke(app, ["config", "get-constitution-max-size"])
        assert result.exit_code == 0
        assert "3000" in result.output


# ---------------------------------------------------------------------------
# config profiles
# ---------------------------------------------------------------------------


class TestConfigProfiles:
    """Test config profile commands."""

    def test_profiles_lists_available(self, _mock_db) -> None:
        """config profiles → lists available profiles."""
        result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0
        # Should show the profiles table
        assert "Available" in result.output or "Name" in result.output

    def test_show_profile_unknown(self, _mock_db) -> None:
        """config show-profile unknown → exit 1."""
        result = runner.invoke(app, ["config", "show-profile", "nonexistent"])
        assert result.exit_code == 1
        assert "Unknown profile" in result.output

    def test_set_profile_unknown(self, _mock_db) -> None:
        """config set-profile unknown → exit 1."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set-profile", "nonexistent"])
        assert result.exit_code == 1

    def test_get_profile_none_set(self, _mock_db) -> None:
        """config get-profile with no profile → shows default."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "get-profile"])
        assert result.exit_code == 0
        assert "No domain profile" in result.output or "defaults" in result.output

    def test_reset_profile(self, _mock_db) -> None:
        """config reset-profile → clears profile."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "reset-profile"])
        assert result.exit_code == 0
        assert "cleared" in result.output.lower() or "reset" in result.output.lower()


# ---------------------------------------------------------------------------
# config auto-bootstrap
# ---------------------------------------------------------------------------


class TestConfigAutoBootstrap:
    """Test config set-auto-bootstrap / get-auto-bootstrap commands."""

    def test_set_auto_bootstrap_happy_path(self, _mock_db) -> None:
        """set-auto-bootstrap → success."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set-auto-bootstrap", "auto"])
        assert result.exit_code == 0
        assert "auto" in result.output

    def test_set_auto_bootstrap_invalid_mode(self, _mock_db) -> None:
        """set-auto-bootstrap with invalid mode → exit 1."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "set-auto-bootstrap", "always"])
        assert result.exit_code == 1
        assert "Error" in result.output or "Invalid" in result.output

    def test_get_auto_bootstrap_happy_path(self, _mock_db) -> None:
        """get-auto-bootstrap → shows current mode."""
        _create_project(_mock_db)
        runner.invoke(app, ["config", "set-auto-bootstrap", "off"])
        result = runner.invoke(app, ["config", "get-auto-bootstrap"])
        assert result.exit_code == 0
        assert "off" in result.output

    def test_get_auto_bootstrap_default_is_prompt(self, _mock_db) -> None:
        """get-auto-bootstrap on fresh project → 'prompt' (default)."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "get-auto-bootstrap"])
        assert result.exit_code == 0
        assert "prompt" in result.output
