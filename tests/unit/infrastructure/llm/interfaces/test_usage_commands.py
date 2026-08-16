# mypy: ignore-errors
# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Tests for ``sw usage`` command (Feature 3.12).

Proves: TECH-052 FR-1
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

    def test_usage_rejects_an_unparseable_since_with_a_message(self, _mock_db) -> None:
        """[Hostile] `--since not-a-date` → an error naming the option, never a traceback.

        `TECH-052`. `datetime.fromisoformat(since)` had no guard, so any typo — `2026-8-1`,
        `yesterday`, a pasted log line — reached the user as a raw `ValueError`. It sits on the
        READ half of the US-16 cost journey, where a traceback reads as "telemetry is broken"
        rather than "the date was wrong".
        """
        _create_project(_mock_db)

        result = runner.invoke(app, ["usage", "--since", "not-a-date"])

        assert result.exit_code == 1
        assert result.exception is None or isinstance(result.exception, SystemExit)
        assert shows(result.output, "--since")
        assert shows(result.output, "not-a-date")

    def test_usage_names_the_format_it_wanted(self, _mock_db) -> None:
        """[Hostile] the message has to say what a good value looks like.

        A rejection that only says "invalid" leaves the user guessing between `2026-08-16`,
        `16/08/2026` and an epoch. The example is the fix, not decoration.
        """
        _create_project(_mock_db)

        result = runner.invoke(app, ["usage", "--since", "16/08/2026"])

        assert result.exit_code == 1
        assert shows(result.output, "2026-08-16")

    def test_an_offset_timestamp_is_accepted(self, _mock_db) -> None:
        """[Boundary] the guard must not narrow what already worked.

        Typer's native `datetime` type — the obvious framework answer — accepts only its three
        default formats and would have rejected this offset, so the fix keeps `fromisoformat` and
        guards it instead.
        """
        _create_project(_mock_db)
        _seed_usage(_mock_db, "testproj")

        assert runner.invoke(app, ["usage", "--since", "2026-03-27T11:00:00+02:00"]).exit_code == 0

    def test_a_naive_timestamp_is_refused_before_it_reaches_the_database(self, _mock_db) -> None:
        """[Hostile] A SECOND defect, found while writing the first test's boundary case.

        `--since 2026-03-27` parses perfectly — `fromisoformat` accepts a bare date — and then dies
        deeper down with `StatementError: StrictISODateTime must be timezone-aware`, a SQLAlchemy
        type error shown to a user who asked a reporting question. Guarding only the parse would
        have left this crash untouched and the ticket half-fixed.

        Refused rather than assumed-UTC on purpose: silently choosing a timezone mis-filters by up
        to a day at the boundary, and the user cannot see that it happened.
        """
        _create_project(_mock_db)

        result = runner.invoke(app, ["usage", "--since", "2026-03-27"])

        assert result.exit_code == 1
        assert result.exception is None or isinstance(result.exception, SystemExit)
        assert shows(result.output, "timezone")
        assert not shows(result.output, "StatementError")

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
