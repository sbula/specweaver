# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for ``sw usage`` command (Feature 3.12)."""

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
    _run_workspace_op(db, "register_project", name, ".")
    _run_workspace_op(db, "set_active_project", name)
    return name


def _seed_usage(db, project, *, n=3):
    """Insert n dummy usage records."""
    for i in range(n):
        _run_llm_op(
            db,
            "log_usage",
            {
                "timestamp": f"2026-03-27T{10 + i:02d}:00:00Z",
                "project_name": project,
                "task_type": "review",
                "model": "gemini-2.0-flash",
                "provider": "google",
                "prompt_tokens": 100 * (i + 1),
                "completion_tokens": 50 * (i + 1),
                "total_tokens": 150 * (i + 1),
                "estimated_cost_usd": 0.001 * (i + 1),
                "duration_ms": 500 * (i + 1),
            },
        )


class TestUsageCommand:
    """Tests for ``sw usage``."""

    def test_usage_shows_summary_table(self, _mock_db) -> None:
        """sw usage → shows usage summary table."""
        _create_project(_mock_db)
        _seed_usage(_mock_db, "testproj")

        result = runner.invoke(app, ["usage"])

        assert result.exit_code == 0
        assert "review" in result.output
        # Rich may truncate column values; check for partial match
        assert "gemini" in result.output

    def test_usage_no_data_shows_message(self, _mock_db) -> None:
        """sw usage with no records → helpful message."""
        _create_project(_mock_db)

        result = runner.invoke(app, ["usage"])

        assert result.exit_code == 0
        assert "no usage" in result.output.lower() or "No usage" in result.output

    def test_usage_all_flag(self, _mock_db) -> None:
        """sw usage --all → shows all projects."""
        _create_project(_mock_db)
        _seed_usage(_mock_db, "testproj")

        result = runner.invoke(app, ["usage", "--all"])

        assert result.exit_code == 0

    def test_usage_since_flag(self, _mock_db) -> None:
        """sw usage --since 2026-03-27T11:00:00Z → filters by date."""
        _create_project(_mock_db)
        _seed_usage(_mock_db, "testproj")

        result = runner.invoke(
            app,
            ["usage", "--since", "2026-03-27T11:00:00Z"],
        )

        assert result.exit_code == 0

    def test_usage_no_active_project_shows_hint(self, _mock_db) -> None:
        """sw usage with no active project → exit 0 with hint."""
        # Don't create project — no active project
        result = runner.invoke(app, ["usage"])

        assert result.exit_code == 0
        assert "no active project" in result.output.lower()


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
