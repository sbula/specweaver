# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A request that finds the file locked gets `503` with `Retry-After: 1`; other database errors
stay `500`.

A second connection really holds the write lock. The test lowers the lock wait from the API's
5 s to keep the suite fast; the 5 s value is proven in `test_api_door_prepares_files.py`.

Proves: TECH-090 FR-9 (path P-4)

| Bucket | Case |
|---|---|
| Happy | a write route on a locked config database answers `503`, `Retry-After: 1`, the agreed body |
| Boundary | once the lock is released, the same request succeeds |
| Degradation | a locked file reached through `sqlite3` (the pipeline state's path) is a `503` too |
| Hostile | another `OperationalError` stays a `500`, and no SQL text reaches the body; SQL naming a `busy` column is not a lock |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest
import sqlalchemy.exc
from fastapi.testclient import TestClient

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.infrastructure.database import Database, set_lock_wait
from specweaver.interfaces.api.app import create_app
from tests.api_token import AUTH, TEST_TOKEN
from tests.fixtures.db_utils import register_test_project

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from fastapi import FastAPI

pytestmark = pytest.mark.integration

_BUSY = {"detail": "The database is busy. Retry.", "error_code": "DATABASE_BUSY"}


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[FastAPI, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    path = data / "specweaver.db"
    bootstrap_database(str(path))
    db = Database(path)
    root = tmp_path / "proj"
    root.mkdir()
    register_test_project(db, "proj", str(root))
    app = create_app(token=TEST_TOKEN, db=db)
    set_lock_wait(0.2)  # after create_app, which sets 5 s
    return app, path


@pytest.fixture()
def held(world: tuple[FastAPI, Path]) -> Iterator[sqlite3.Connection]:
    _, path = world
    with closing(sqlite3.connect(path, isolation_level=None)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.execute("ROLLBACK")


def test_a_locked_file_answers_503_with_retry_after(
    world: tuple[FastAPI, Path], held: sqlite3.Connection
) -> None:
    app, _ = world

    with TestClient(app, headers=AUTH) as client:
        response = client.post("/api/v1/projects/proj/use")

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "1"
    assert response.json() == _BUSY


def test_the_request_succeeds_once_the_lock_is_released(world: tuple[FastAPI, Path]) -> None:
    app, path = world
    with closing(sqlite3.connect(path, isolation_level=None)) as conn:
        conn.execute("BEGIN IMMEDIATE")
        with TestClient(app, headers=AUTH) as client:
            assert client.post("/api/v1/projects/proj/use").status_code == 503
        conn.execute("ROLLBACK")

    with TestClient(app, headers=AUTH) as client:
        assert client.post("/api/v1/projects/proj/use").status_code == 200


def _raising(app: FastAPI, error: Exception) -> TestClient:
    @app.get("/boom")
    def boom() -> None:
        raise error

    return TestClient(app, headers=AUTH, raise_server_exceptions=False)


@pytest.mark.parametrize("message", ["database is locked", "database table is locked", "busy"])
def test_a_locked_file_reached_through_sqlite3_answers_503(
    world: tuple[FastAPI, Path], message: str
) -> None:
    app, _ = world

    with _raising(app, sqlite3.OperationalError(message)) as client:
        response = client.get("/boom")

    assert response.status_code == 503
    assert response.json() == _BUSY


def test_another_database_error_stays_500_without_its_sql(world: tuple[FastAPI, Path]) -> None:
    app, _ = world
    error = sqlalchemy.exc.OperationalError(
        "SELECT secret FROM t", {}, sqlite3.OperationalError("no such table: t")
    )

    with _raising(app, error) as client:
        response = client.get("/boom")

    assert response.status_code == 500
    assert "SELECT" not in response.text
    assert "Retry-After" not in response.headers


def test_sql_that_names_a_busy_column_is_not_a_lock(world: tuple[FastAPI, Path]) -> None:
    app, _ = world
    error = sqlalchemy.exc.OperationalError(
        "UPDATE t SET busy = 1", {}, sqlite3.OperationalError("no such table: t")
    )

    with _raising(app, error) as client:
        response = client.get("/boom")

    assert response.status_code == 500


def test_a_real_error_naming_a_busy_column_is_not_a_lock(world: tuple[FastAPI, Path]) -> None:
    app, _ = world
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.execute("CREATE TABLE t (a TEXT)")
        try:
            conn.execute("SELECT busy FROM t")
        except sqlite3.OperationalError as caught:
            error = caught

    with _raising(app, error) as client:
        response = client.get("/boom")

    assert "busy" in str(error)
    assert response.status_code == 500


@pytest.mark.parametrize(
    "code", [517, 262], ids=["SQLITE_BUSY_SNAPSHOT", "SQLITE_LOCKED_SHAREDCACHE"]
)
def test_an_extended_lock_code_answers_503(world: tuple[FastAPI, Path], code: int) -> None:
    app, _ = world
    error = sqlite3.OperationalError("database snapshot changed")
    error.sqlite_errorcode = code  # type: ignore[attr-defined]

    with _raising(app, error) as client:
        response = client.get("/boom")

    assert response.status_code == 503
