# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A file's schema version lives in `PRAGMA user_version`, and only its missing steps run.

Proves: TECH-090 FR-3, FR-7

| Bucket | Case |
|---|---|
| Happy | a new file runs every step and ends at the last version; an old one runs only what it lacks |
| Boundary | a second run changes nothing; a file this process already upgraded is not read again |
| Degradation | a step that fails after an ALTER leaves no column and the old version, naming the step; a rename lost to another process is no error |
| Hostile | a file newer than the code is refused; steps out of order are refused; a file that is not a database is refused untouched |
| Boundary | an empty file is a new database; a step's own SQL error stays the step's error |
| Happy | every refusal is a `SchemaError`, the one family a door catches |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest

from specweaver.infrastructure.database import (
    SchemaError,
    SchemaOpenError,
    SchemaStepError,
    SchemaTooNewError,
    Step,
    rename_legacy_tables,
    upgrade,
)
from tests.fixtures.db_utils import user_version

if TYPE_CHECKING:
    from pathlib import Path


def _columns(path: Path, table: str) -> list[str]:
    with closing(sqlite3.connect(path)) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _setup(path: Path, *statements: str) -> None:
    with closing(sqlite3.connect(path)) as conn:
        for statement in statements:
            conn.execute(statement)
        conn.commit()


def _steps(ran: list[str]) -> list[Step]:
    def create(conn: sqlite3.Connection) -> None:
        ran.append("create")
        conn.execute("CREATE TABLE t (a TEXT)")

    def add(conn: sqlite3.Connection) -> None:
        ran.append("add")
        conn.execute("ALTER TABLE t ADD COLUMN b TEXT")

    return [Step(1, "create t", create), Step(2, "add b", add)]


def test_a_new_file_runs_every_step(tmp_path: Path) -> None:
    ran: list[str] = []

    upgrade(tmp_path / "a.db", _steps(ran))

    assert ran == ["create", "add"]
    assert user_version(tmp_path / "a.db") == 2
    assert _columns(tmp_path / "a.db", "t") == ["a", "b"]


def test_an_old_file_runs_only_what_it_lacks(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    _setup(path, "CREATE TABLE t (a TEXT)", "PRAGMA user_version = 1")
    ran: list[str] = []

    upgrade(path, _steps(ran))

    assert ran == ["add"]
    assert user_version(path) == 2


def test_a_second_run_in_a_new_process_changes_nothing(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    upgrade(path, _steps([]))
    ran: list[str] = []

    upgrade(path, _steps(ran), _seen=set())

    assert ran == []
    assert user_version(path) == 2


def test_a_file_this_process_upgraded_is_not_read_again(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    upgrade(path, _steps([]))
    path.unlink()
    ran: list[str] = []

    upgrade(path, _steps(ran))

    assert ran == []


def test_a_failed_step_rolls_back_its_ddl_and_names_itself(tmp_path: Path) -> None:
    path = tmp_path / "a.db"

    def half(conn: sqlite3.Connection) -> None:
        conn.execute("ALTER TABLE t ADD COLUMN b TEXT")
        raise RuntimeError("disk full")

    steps = [_steps([])[0], Step(2, "add b", half)]

    with pytest.raises(SchemaStepError, match="add b") as caught:
        upgrade(path, steps)

    assert str(path) in str(caught.value)
    assert "disk full" in str(caught.value)
    assert user_version(path) == 1
    assert _columns(path, "t") == ["a"]


def test_a_file_newer_than_the_code_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    _setup(path, "PRAGMA user_version = 7")

    with pytest.raises(SchemaTooNewError) as caught:
        upgrade(path, _steps([]))

    message = str(caught.value)
    assert str(path) in message and "7" in message and "2" in message


@pytest.mark.parametrize("versions", [(2, 1), (1, 1), (1, 3), (0, 1)])
def test_steps_out_of_order_are_refused(tmp_path: Path, versions: tuple[int, int]) -> None:
    steps = [Step(v, f"s{v}", lambda conn: None) for v in versions]

    with pytest.raises(ValueError, match="1, 2"):
        upgrade(tmp_path / "a.db", steps)


def test_adopt_runs_once_inside_the_first_missing_step(tmp_path: Path) -> None:
    """An old file already holds step 1's table under its own version record; adopt says so."""
    path = tmp_path / "a.db"
    _setup(path, "CREATE TABLE t (a TEXT)")
    seen: list[int] = []

    def adopt(conn: sqlite3.Connection) -> None:
        seen.append(int(conn.execute("PRAGMA user_version").fetchone()[0]))
        conn.execute("PRAGMA user_version = 1")

    ran: list[str] = []
    upgrade(path, _steps(ran), adopt=adopt)

    assert seen == [0]
    assert ran == ["add"]
    assert user_version(path) == 2


def test_a_rename_lost_to_another_process_is_no_error(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "a.db")
    conn.execute("CREATE TABLE old_name (a TEXT)")
    conn.execute("INSERT INTO old_name VALUES ('kept')")

    rename_legacy_tables(conn, (("old_name", "new_name"), ("absent", "other")))
    rename_legacy_tables(conn, (("old_name", "new_name"),))

    assert conn.execute("SELECT a FROM new_name").fetchall() == [("kept",)]
    conn.close()


def test_an_old_and_a_new_table_side_by_side_are_left_alone(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "a.db")
    conn.execute("CREATE TABLE old_name (a TEXT)")
    conn.execute("CREATE TABLE new_name (a TEXT)")

    rename_legacy_tables(conn, (("old_name", "new_name"),))

    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert names == {"old_name", "new_name"}
    conn.close()


def test_a_file_that_is_not_a_database_is_refused_untouched(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    garbage = b"this is not a database " * 100
    path.write_bytes(garbage)

    with pytest.raises(SchemaOpenError) as caught:
        upgrade(path, _steps([]))

    assert str(caught.value).startswith(f"{path} cannot be opened: ")
    assert path.read_bytes() == garbage


def test_an_empty_file_is_a_new_database(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    path.write_bytes(b"")

    upgrade(path, _steps([]))

    assert user_version(path) == 2


def test_a_steps_own_sql_error_stays_the_steps_error(tmp_path: Path) -> None:
    path = tmp_path / "a.db"
    steps = [Step(1, "bad sql", lambda conn: conn.execute("CREATE TABLE"))]

    with pytest.raises(SchemaStepError, match="bad sql"):
        upgrade(path, steps)


@pytest.mark.parametrize("error", [SchemaOpenError, SchemaStepError, SchemaTooNewError])
def test_every_refusal_is_a_schema_error(error: type[Exception]) -> None:
    assert issubclass(error, SchemaError)
