# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — CLI config subcommands.

Tests all 10 config commands via CliRunner with mocked DB.
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

    bootstrap_database(str(tmp_path / ".specweaver-test" / "specweaver.db"))
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.core.config.cli_db_utils.get_db", lambda: db)
    return db


def _create_project(db, name: str = "testproj") -> str:
    """Register and activate a project in the DB."""
    _run_workspace_op(db, "register_project", name, ".")
    _run_workspace_op(db, "set_active_project", name)
    return name


# ---------------------------------------------------------------------------
# config set / get / list / reset
# ---------------------------------------------------------------------------


class TestConfigList:
    """Test config list subcommand."""

    def test_list_with_no_profile(self, _mock_db) -> None:
        """config list shows default pipeline message."""
        _create_project(_mock_db)
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "default pipeline" in result.output

    def test_list_with_profile(self, _mock_db) -> None:
        """config list shows profile message."""
        _create_project(_mock_db)
        runner.invoke(app, ["config", "set-profile", "web-app"])
        result = runner.invoke(app, ["config", "list"])
        assert result.exit_code == 0
        assert "web-app" in result.output


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
            app,
            ["config", "set-constitution-max-size", "5000"],
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
        assert (
            "cleared" in result.output.lower()
            or "reset" in result.output.lower()
            or "deactivated" in result.output.lower()
        )


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


# ---------------------------------------------------------------------------
# config set-provider
# ---------------------------------------------------------------------------


class TestConfigSetProvider:
    """Test config set-provider command."""

    def _get_profile(self, _mock_db, name: str, role: str):
        import anyio

        from specweaver.infrastructure.llm.store import LlmRepository

        async def _get():
            async with _mock_db.async_session_scope() as session:
                return await LlmRepository(session).get_project_profile(name, role)

        return anyio.run(_get)

    def test_set_provider_happy_path_new_profile(self, _mock_db) -> None:
        """set-provider creates a new local profile if project doesn't have one."""
        _create_project(_mock_db)
        # Initially, no local profile
        profile = self._get_profile(_mock_db, "testproj", "draft")
        assert profile is None or profile.is_global == 1

        result = runner.invoke(app, ["config", "set-provider", "openai"])

        assert result.exit_code == 0
        assert "Created new local profile" in result.output
        assert "openai" in result.output

        profile = self._get_profile(_mock_db, "testproj", "draft")
        assert profile is not None
        assert profile.is_global == 0
        assert profile.provider == "openai"
        assert profile.model == "default"

    def test_set_provider_updates_existing_local_profile(self, _mock_db) -> None:
        """set-provider updates the provider and model on an existing local profile."""
        _create_project(_mock_db)

        # Create initial local profile
        runner.invoke(app, ["config", "set-provider", "mistral"])

        # Update it
        result = runner.invoke(
            app, ["config", "set-provider", "anthropic", "--model", "claude-3-haiku"]
        )

        assert result.exit_code == 0
        assert "Updated existing custom profile" in result.output

        profile = self._get_profile(_mock_db, "testproj", "draft")
        assert profile is not None
        assert profile.provider == "anthropic"
        assert profile.model == "claude-3-haiku"

    def test_set_provider_unknown_provider(self, _mock_db) -> None:
        """set-provider rejects unknown providers based on the registry."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "set-provider", "fake-provider-123"])

        assert result.exit_code == 1
        assert "Unknown provider" in result.output
        assert "Available:" in result.output


def _run_workspace_op(db_instance, method_name: str, *args, **kwargs):
    import anyio

    from specweaver.workspace.store import WorkspaceRepository

    async def _action():
        async with db_instance.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args, **kwargs)

    return anyio.run(_action)
