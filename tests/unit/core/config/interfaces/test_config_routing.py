# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Unit tests — CLI config routing subcommands (set/show/clear)."""

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
    monkeypatch.setattr("specweaver.interfaces.cli._core.get_db", lambda: db)
    return db


def _create_project(db, name: str = "testproj") -> str:
    """Register and activate a project in the DB."""
    _run_workspace_op(db, "register_project", name, ".")
    _run_workspace_op(db, "set_active_project", name)
    return name


def _create_profile(db, name: str = "gemini-pro", **kwargs) -> int:
    """Create a named LLM profile and return its ID."""
    defaults = {"provider": "gemini", "model": "gemini-2.5-pro"}
    defaults.update(kwargs)
    return _run_llm_op(db, "create_llm_profile", name, **defaults)


# ---------------------------------------------------------------------------
# routing set
# ---------------------------------------------------------------------------


class TestRoutingSet:
    """Test sw config routing set."""

    def test_set_happy_path(self, _mock_db) -> None:
        """routing set → links task type to profile, prints confirmation."""
        _create_project(_mock_db)
        _create_profile(_mock_db, "my-profile", provider="openai", model="gpt-5")

        result = runner.invoke(app, ["config", "routing", "set", "implement", "my-profile"])

        assert result.exit_code == 0
        assert "implement" in result.output
        assert "my-profile" in result.output
        assert "openai" in result.output
        # Verify DB entry was created
        entries = _run_llm_op(_mock_db, "get_project_routing_entries", "testproj")
        assert len(entries) == 1
        assert entries[0]["task_type"] == "implement"

    def test_set_invalid_task_type(self, _mock_db) -> None:
        """routing set with bad task type → exit 1."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "routing", "set", "badtype", "some-profile"])

        assert result.exit_code == 1
        assert "Invalid task type" in result.output

    def test_set_unknown_profile(self, _mock_db) -> None:
        """routing set with nonexistent profile → exit 1."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "routing", "set", "implement", "no-such-profile"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_set_no_active_project(self, _mock_db) -> None:
        """routing set without active project → exit 1."""
        # Do NOT create a project
        result = runner.invoke(app, ["config", "routing", "set", "implement", "prof"])

        assert result.exit_code == 1
        assert "No active project" in result.output

    def test_set_overwrites_existing(self, _mock_db) -> None:
        """routing set twice for same task type → second profile wins."""
        _create_project(_mock_db)
        _create_profile(_mock_db, "profile-a", provider="gemini", model="model-a")
        _create_profile(_mock_db, "profile-b", provider="openai", model="model-b")

        runner.invoke(app, ["config", "routing", "set", "implement", "profile-a"])
        runner.invoke(app, ["config", "routing", "set", "implement", "profile-b"])

        entries = _run_llm_op(_mock_db, "get_project_routing_entries", "testproj")
        assert len(entries) == 1
        assert entries[0]["profile_name"] == "profile-b"


# ---------------------------------------------------------------------------
# routing show
# ---------------------------------------------------------------------------


class TestRoutingShow:
    """Test sw config routing show."""

    def test_show_empty(self, _mock_db) -> None:
        """routing show with no entries → default message."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "routing", "show"])

        assert result.exit_code == 0
        assert "No routing configured" in result.output

    def test_show_with_entries(self, _mock_db) -> None:
        """routing show after set → displays table."""
        _create_project(_mock_db)
        _create_profile(_mock_db, "claude-profile", provider="anthropic", model="claude-4")

        runner.invoke(app, ["config", "routing", "set", "review", "claude-profile"])
        result = runner.invoke(app, ["config", "routing", "show"])

        assert result.exit_code == 0
        assert "review" in result.output
        assert "claude-profile" in result.output
        assert "anthropic" in result.output
        assert "claude-4" in result.output

    def test_show_deleted_profile(self, _mock_db) -> None:
        """routing show with orphaned link → shows [deleted] markers."""
        _create_project(_mock_db)
        pid = _create_profile(_mock_db, "temp-profile")

        runner.invoke(app, ["config", "routing", "set", "draft", "temp-profile"])

        # Delete the profile directly, simulating orphan
        with _mock_db.connect() as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM llm_profiles WHERE id = ?", (pid,))
            conn.execute("PRAGMA foreign_keys = ON")

        result = runner.invoke(app, ["config", "routing", "show"])

        assert result.exit_code == 0
        assert "[deleted]" in result.output


# ---------------------------------------------------------------------------
# routing clear
# ---------------------------------------------------------------------------


class TestRoutingClear:
    """Test sw config routing clear."""

    def test_clear_specific_entry(self, _mock_db) -> None:
        """routing clear <task_type> → clears only that entry."""
        _create_project(_mock_db)
        _create_profile(_mock_db, "prof1", provider="gemini", model="m1")

        runner.invoke(app, ["config", "routing", "set", "implement", "prof1"])
        runner.invoke(app, ["config", "routing", "set", "review", "prof1"])

        result = runner.invoke(app, ["config", "routing", "clear", "implement"])

        assert result.exit_code == 0
        assert "Cleared routing for" in result.output
        assert "implement" in result.output
        # review should still exist
        entries = _run_llm_op(_mock_db, "get_project_routing_entries", "testproj")
        assert len(entries) == 1
        assert entries[0]["task_type"] == "review"

    def test_clear_specific_nonexistent(self, _mock_db) -> None:
        """routing clear <task_type> with no entry → info message."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "routing", "clear", "implement"])

        assert result.exit_code == 0
        assert "No routing entry" in result.output

    def test_clear_all(self, _mock_db) -> None:
        """routing clear (no arg) → clears all entries."""
        _create_project(_mock_db)
        _create_profile(_mock_db, "prof1", provider="gemini", model="m1")

        runner.invoke(app, ["config", "routing", "set", "implement", "prof1"])
        runner.invoke(app, ["config", "routing", "set", "review", "prof1"])

        result = runner.invoke(app, ["config", "routing", "clear"])

        assert result.exit_code == 0
        assert "Cleared all" in result.output
        assert _run_llm_op(_mock_db, "get_project_routing_entries", "testproj") == []

    def test_clear_all_empty(self, _mock_db) -> None:
        """routing clear (no arg) with no entries → info message."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "routing", "clear"])

        assert result.exit_code == 0
        assert "No routing entries to clear" in result.output

    def test_clear_invalid_task_type(self, _mock_db) -> None:
        """routing clear with bad task type → exit 1."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["config", "routing", "clear", "badtype"])

        assert result.exit_code == 1
        assert "Invalid task type" in result.output


def _run_workspace_op(db_instance, method_name: str, *args, **kwargs):
    import anyio

    from specweaver.workspace.store import WorkspaceRepository

    async def _action():
        async with db_instance.async_session_scope() as session:
            repo = WorkspaceRepository(session)
            method = getattr(repo, method_name)
            return await method(*args, **kwargs)

    return anyio.run(_action)


def _run_llm_op(db_instance, method_name: str, *args, **kwargs):
    import anyio

    from specweaver.infrastructure.llm.store import LlmRepository

    async def _action():
        async with db_instance.async_session_scope() as session:
            repo = LlmRepository(session)
            method = getattr(repo, method_name)
            return await method(*args, **kwargs)

    return anyio.run(_action)
