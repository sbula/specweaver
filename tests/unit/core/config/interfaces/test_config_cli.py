# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — CLI config subcommands.

Tests all 10 config commands via CliRunner with mocked DB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from tests.rendering import shows
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()


@pytest.fixture(autouse=True)
def _mock_db(tmp_path: Path, monkeypatch):
    """Patch get_db() to use a temp DB for all CLI tests."""
    from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
    from specweaver.core.config.database import Database

    bootstrap_database(str(tmp_path / ".specweaver-test" / "specweaver.db"))
    db = Database(tmp_path / ".specweaver-test" / "specweaver.db")
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
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
# config set-role — writes the LLM settings files (C-FLOW-13 FR-15)
# ---------------------------------------------------------------------------

_MACHINE = """\
# my machine
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4
"""


class TestConfigSetRole:
    """`sw config set-role` writes a role into the machine file, or the project's with --project."""

    def test_a_machine_role_is_written(self, _mock_db, tmp_path, monkeypatch) -> None:
        from specweaver.core.config.llm_settings import parse_machine_file

        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
        (tmp_path / "settings.toml").write_text(_MACHINE, encoding="utf-8")
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "set-role", "draft", "qwen3-coder-next@gb10"])

        assert result.exit_code == 0, result.output
        text = (tmp_path / "settings.toml").read_text(encoding="utf-8")
        assert text.startswith("# my machine")
        assert parse_machine_file(text, "x").roles["draft"].model == "qwen3-coder-next"

    def test_a_project_role_goes_to_the_projects_file(
        self, _mock_db, tmp_path, monkeypatch
    ) -> None:
        from specweaver.core.config.llm_settings import parse_project_llm

        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
        (tmp_path / "settings.toml").write_text(_MACHINE, encoding="utf-8")
        project = tmp_path / "proj"
        project.mkdir()
        _run_workspace_op(_mock_db, "register_project", "testproj", str(project))
        _run_workspace_op(_mock_db, "set_active_project", "testproj")

        result = runner.invoke(
            app, ["config", "set-role", "review", "qwen3-coder-next@gb10", "--project"]
        )

        assert result.exit_code == 0, result.output
        llm = parse_project_llm((project / "specweaver.toml").read_text(encoding="utf-8"), "x")
        assert llm.roles["review"].server == "gb10"

    def test_an_unknown_server_is_refused(self, _mock_db, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
        (tmp_path / "settings.toml").write_text(_MACHINE, encoding="utf-8")
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "set-role", "draft", "claude-opus-5-5@nowhere"])

        assert result.exit_code == 1
        assert shows(result.output, "nowhere")
        assert (tmp_path / "settings.toml").read_text(encoding="utf-8") == _MACHINE

    def test_an_unknown_role_is_refused(self, _mock_db, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
        (tmp_path / "settings.toml").write_text(_MACHINE, encoding="utf-8")
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "set-role", "drafting", "qwen3-coder-next@gb10"])

        assert result.exit_code == 1
        assert shows(result.output, "drafting")


class TestConfigShowBrokenFile:
    """A broken settings file stops the command cleanly with exit code 1, not with a crash."""

    def test_show_refuses_a_broken_file(self, _mock_db, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path))
        (tmp_path / "settings.toml").write_text("[servers.gb10\n", encoding="utf-8")
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "show"])

        assert result.exit_code == 1, result.output
        assert isinstance(result.exception, SystemExit), result.exception
        assert shows(result.output, "settings.toml")


def _run_workspace_op(db_instance, method_name: str, *args, **kwargs):
    import anyio

    from specweaver.workspace.store import WorkspaceRepository

    async def _action():
        async with db_instance.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args, **kwargs)

    return anyio.run(_action)
