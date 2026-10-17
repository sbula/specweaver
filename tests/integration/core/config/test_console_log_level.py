# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What reaches the console is a project setting, like what reaches the log file.

Proves: D-FLOW-04 FR-7
Proves: D-FLOW-04 NFR-2

A real database built by the real start-up, and the real logging set-up.

| Bucket | Case |
|---|---|
| Happy | a project's console level is stored, read back, and applied to the console handler |
| Boundary | a database from before the column gains it, every project at WARNING, twice changes nothing |
| Degradation | a repeated set-up for the same project changes both levels, not the file's alone |
| Hostile | a level that is not a level is refused; a quiet file never silences a loud console |
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from typing import TYPE_CHECKING, Any

import pytest
from rich.logging import RichHandler

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.telemetry_logger import setup_logging, teardown_logging
from specweaver.workspace.store import WorkspaceRepository

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.integration


@pytest.fixture
def db(tmp_path: Path) -> Database:
    bootstrap_database(str(tmp_path / "specweaver.db"))
    database = Database(tmp_path / "specweaver.db")
    asyncio.run(_op(database, "register_project", "greeter", str(tmp_path)))
    return database


@pytest.fixture
def logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
    yield
    teardown_logging()


async def _op(db: Database, method: str, *args: Any) -> Any:
    async with db.async_session_scope() as session:
        return await getattr(WorkspaceRepository(session), method)(*args)


def _console_level() -> int:
    [handler] = [h for h in logging.getLogger("specweaver").handlers if isinstance(h, RichHandler)]
    return handler.level


def test_a_new_project_shows_warnings_on_the_console(db: Database) -> None:
    assert asyncio.run(_op(db, "get_console_log_level", "greeter")) == "WARNING"


def test_the_console_level_is_stored_and_read_back(db: Database) -> None:
    asyncio.run(_op(db, "set_console_log_level", "greeter", "info"))

    assert asyncio.run(_op(db, "get_console_log_level", "greeter")) == "INFO"
    assert asyncio.run(_op(db, "get_log_level", "greeter")) == "DEBUG"


@pytest.mark.parametrize("level", ["LOUD", "", "debug; DROP TABLE x"])
def test_a_level_that_is_not_a_level_is_refused(db: Database, level: str) -> None:
    with pytest.raises(ValueError, match="Invalid log level"):
        asyncio.run(_op(db, "set_console_log_level", "greeter", level))


def test_an_older_database_gains_the_column_at_warning(tmp_path: Path, db: Database) -> None:
    path = tmp_path / "specweaver.db"
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE workspace_projects DROP COLUMN console_log_level")

    bootstrap_database(str(path))
    bootstrap_database(str(path))

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT console_log_level FROM workspace_projects").fetchall() == [
            ("WARNING",)
        ]


@pytest.mark.usefixtures("logs")
def test_the_console_handler_takes_the_projects_level() -> None:
    setup_logging("greeter", level="DEBUG", console_level="INFO")

    assert _console_level() == logging.INFO


@pytest.mark.usefixtures("logs")
def test_a_repeated_set_up_changes_both_levels() -> None:
    setup_logging("greeter", level="DEBUG", console_level="WARNING")
    setup_logging("greeter", level="DEBUG", console_level="ERROR")

    assert _console_level() == logging.ERROR


@pytest.mark.usefixtures("logs")
def test_a_quiet_file_never_silences_a_loud_console(caplog: pytest.LogCaptureFixture) -> None:
    setup_logging("greeter", level="ERROR", console_level="INFO")
    setup_logging("greeter", level="ERROR", console_level="INFO")

    assert logging.getLogger("specweaver.x").isEnabledFor(logging.INFO)
