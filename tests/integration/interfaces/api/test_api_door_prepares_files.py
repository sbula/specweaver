# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The API door brings its files up to date before the app is built, and sets a 5 s lock wait.

Real files in a temporary data dir; `sw serve` never starts a server here.

Proves: TECH-090 FR-2, FR-7

| Bucket | Case |
|---|---|
| Happy | `create_app()` on a fresh data dir leaves `specweaver.db` and `pipeline_state.db` current |
| Boundary | `create_app(db=…)` brings that database's own file up to date; the lock wait is 5 s after it |
| Degradation | a `specweaver.db` newer than the code makes `create_app` raise; `sw serve` exits 1 and starts no server |
| Hostile | a `pipeline_state.db` that is not a database makes `create_app` raise `SchemaOpenError` |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.database import (
    Database,
    SchemaOpenError,
    SchemaTooNewError,
    lock_wait_seconds,
    set_lock_wait,
)
from specweaver.interfaces.api.app import create_app
from specweaver.interfaces.cli.main import app as cli
from tests.api_token import TEST_TOKEN
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

runner = CliRunner()


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(path))
    return path


def _version(path: Path) -> int:
    with closing(sqlite3.connect(path)) as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _at_version(path: Path, version: int) -> None:
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(f"PRAGMA user_version = {version}")


def test_a_fresh_data_dir_gets_current_files(data_dir: Path) -> None:
    create_app(token=TEST_TOKEN)

    assert _version(data_dir / "specweaver.db") == 1
    assert _version(data_dir / "pipeline_state.db") == 1


def test_a_given_database_is_brought_up_to_date(data_dir: Path) -> None:
    path = data_dir / "other.db"

    create_app(token=TEST_TOKEN, db=Database(path))

    assert _version(path) == 1


def test_the_api_sets_a_5_second_lock_wait(data_dir: Path) -> None:
    set_lock_wait(30)

    create_app(token=TEST_TOKEN)

    assert lock_wait_seconds() == 5


def test_a_newer_config_database_stops_the_app(data_dir: Path) -> None:
    path = data_dir / "specweaver.db"
    _at_version(path, 99)

    with pytest.raises(SchemaTooNewError, match="schema version 99") as caught:
        create_app(token=TEST_TOKEN)

    assert str(path) in str(caught.value)


def test_a_pipeline_state_that_is_not_a_database_stops_the_app(data_dir: Path) -> None:
    path = data_dir / "pipeline_state.db"
    path.write_bytes(b"this is not a database " * 100)

    with pytest.raises(SchemaOpenError, match="cannot be opened"):
        create_app(token=TEST_TOKEN)


def test_sw_serve_on_a_newer_config_database_starts_no_server(data_dir: Path) -> None:
    path = data_dir / "specweaver.db"
    _at_version(path, 99)

    with patch("uvicorn.run") as serve:
        result = runner.invoke(cli, ["serve"])

    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit), result.exception
    assert shows(result.output, str(path)), result.output
    assert shows(result.output, "schema version 99"), result.output
    serve.assert_not_called()
    assert not (data_dir / "serve.token").exists()
