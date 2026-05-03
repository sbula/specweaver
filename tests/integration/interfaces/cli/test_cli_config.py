# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Integration tests — sw config CLI subcommands.

Covers: set, get, list, reset, set-log-level, get-log-level,
set-constitution-max-size, get-constitution-max-size,
profiles, show-profile, set-profile, get-profile, reset-profile.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.cli_db_utils import bootstrap_database
    from specweaver.core.config.database import Database

    data_dir = tmp_path / ".specweaver-test"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data_dir))
    db_path = str(data_dir / "specweaver.db")
    bootstrap_database(db_path)
    db = Database(db_path)
    return db


@pytest.fixture
def mock_db(_mock_db):
    """Expose the mock DB for tests that need to inspect it."""
    return _mock_db


def _init_project(tmp_path: Path, name: str = "cfg-proj") -> None:
    """Helper: init a project so config commands have an active project."""
    project_dir = tmp_path / name
    project_dir.mkdir(exist_ok=True)
    result = runner.invoke(app, ["init", name, "--path", str(project_dir)])
    assert result.exit_code == 0, f"init failed: {result.output}"


# ---------------------------------------------------------------------------
# sw config set-log-level / get-log-level
# ---------------------------------------------------------------------------


class TestConfigLogLevel:
    """Test log level commands."""

    def test_set_log_level(self, tmp_path: Path) -> None:
        """sw config set-log-level INFO stores the level."""
        _init_project(tmp_path)
        result = runner.invoke(app, ["config", "set-log-level", "INFO"])
        assert result.exit_code == 0
        assert "INFO" in result.output

    def test_get_log_level(self, tmp_path: Path) -> None:
        """sw config get-log-level shows the current level."""
        _init_project(tmp_path)
        runner.invoke(app, ["config", "set-log-level", "WARNING"])
        result = runner.invoke(app, ["config", "get-log-level"])
        assert result.exit_code == 0
        assert "WARNING" in result.output.upper()

    def test_set_log_level_requires_active_project(self) -> None:
        """sw config set-log-level without active project fails."""
        result = runner.invoke(app, ["config", "set-log-level", "DEBUG"])
        assert result.exit_code == 1
        assert "no active project" in result.output.lower()


# ---------------------------------------------------------------------------
# sw config set-constitution-max-size / get-constitution-max-size
# ---------------------------------------------------------------------------


class TestConfigConstitutionMaxSize:
    """Test constitution max size commands."""

    def test_set_constitution_max_size(self, tmp_path: Path) -> None:
        """sw config set-constitution-max-size stores the value."""
        _init_project(tmp_path)
        result = runner.invoke(app, ["config", "set-constitution-max-size", "4096"])
        assert result.exit_code == 0
        assert "4096" in result.output

    def test_get_constitution_max_size(self, tmp_path: Path) -> None:
        """sw config get-constitution-max-size shows the value."""
        _init_project(tmp_path)
        runner.invoke(app, ["config", "set-constitution-max-size", "8192"])
        result = runner.invoke(app, ["config", "get-constitution-max-size"])
        assert result.exit_code == 0
        assert "8192" in result.output


# ---------------------------------------------------------------------------
# sw config profiles / show-profile / set-profile / get-profile / reset-profile
# ---------------------------------------------------------------------------


class TestConfigProfiles:
    """Test domain profile commands."""

    def test_profiles_lists_available(self) -> None:
        """sw config profiles shows available profiles."""
        result = runner.invoke(app, ["config", "profiles"])
        assert result.exit_code == 0
        # Should show at least the table header
        assert "profile" in result.output.lower() or "name" in result.output.lower()

    def test_show_profile_unknown(self) -> None:
        """sw config show-profile with unknown name fails."""
        result = runner.invoke(app, ["config", "show-profile", "nonexistent-profile"])
        assert result.exit_code == 1
        assert "unknown" in result.output.lower() or "not found" in result.output.lower()

    def test_get_profile_none_set(self, tmp_path: Path) -> None:
        """sw config get-profile with no profile shows defaults."""
        _init_project(tmp_path)
        result = runner.invoke(app, ["config", "get-profile"])
        assert result.exit_code == 0
        assert "no" in result.output.lower() or "defaults" in result.output.lower()

    def test_set_profile_requires_active_project(self) -> None:
        """sw config set-profile without active project fails."""
        result = runner.invoke(app, ["config", "set-profile", "some-profile"])
        assert result.exit_code == 1
        assert "no active project" in result.output.lower()

    def test_reset_profile(self, tmp_path: Path) -> None:
        """sw config reset-profile clears the profile."""
        _init_project(tmp_path)
        result = runner.invoke(app, ["config", "reset-profile"])
        assert result.exit_code == 0
        assert "cleared" in result.output.lower() or "deactivated" in result.output.lower()
