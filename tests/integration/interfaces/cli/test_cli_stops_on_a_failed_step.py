# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A CLI command whose file cannot be brought up to date stops with a message, not a warning.

Real files in a temporary data dir, the real schema routine, the real commands.

Proves: TECH-090 FR-7

| Bucket | Case |
|---|---|
| Happy | after a command, `specweaver.db` is at the current version |
| Degradation | `specweaver.db` newer than the code stops `sw projects`, naming the file and both versions |
| Degradation | `pipeline_state.db` newer than the code stops `sw run` and `sw resume` before any step |
| Degradation | `graph.db` newer than the code stops `sw graph build`, naming the file |
| Hostile | a file with the pre-`TECH-005` table names stops the command, naming the file and step 1 |
| Hostile | a `specweaver.db` that is not a database stops the command: it cannot be opened |
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()
pytestmark = pytest.mark.integration


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(path))
    return path


def _at_version(path: Path, version: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as conn:
        conn.execute(f"PRAGMA user_version = {version}")


def _version(path: Path) -> int:
    with closing(sqlite3.connect(path)) as conn:
        return int(conn.execute("PRAGMA user_version").fetchone()[0])


def _stopped(result: object, *needles: str) -> None:
    output = result.output  # type: ignore[attr-defined]
    assert result.exit_code == 1, output  # type: ignore[attr-defined]
    assert isinstance(result.exception, SystemExit), result.exception  # type: ignore[attr-defined]
    assert "Traceback" not in output
    for needle in needles:
        assert shows(output, needle), (needle, output)


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    result = runner.invoke(app, ["init", "proj", "--path", str(root)])
    assert result.exit_code == 0, result.output
    (root / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
    return root


def test_a_command_leaves_the_config_database_current(data_dir: Path) -> None:
    result = runner.invoke(app, ["projects"])

    assert result.exit_code == 0, result.output
    assert _version(data_dir / "specweaver.db") == 1


def test_a_config_database_newer_than_the_code_stops_the_command(data_dir: Path) -> None:
    path = data_dir / "specweaver.db"
    _at_version(path, 99)

    result = runner.invoke(app, ["projects"])

    _stopped(result, str(path), "schema version 99", "only up to 1")


def test_a_file_with_the_old_table_names_stops_the_command(data_dir: Path) -> None:
    path = data_dir / "specweaver.db"
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE projects (name TEXT PRIMARY KEY, root_path TEXT)")
        conn.commit()

    result = runner.invoke(app, ["projects"])

    _stopped(result, str(path), "create the configuration tables")


def test_a_config_database_that_is_not_a_database_stops_the_command(data_dir: Path) -> None:
    path = data_dir / "specweaver.db"
    path.write_bytes(b"this is not a database " * 100)

    result = runner.invoke(app, ["projects"])

    _stopped(result, f"{path} cannot be opened")


def test_a_pipeline_state_newer_than_the_code_stops_sw_resume(data_dir: Path) -> None:
    path = data_dir / "pipeline_state.db"
    _at_version(path, 99)

    result = runner.invoke(app, ["resume"])

    _stopped(result, str(path), "schema version 99")


def test_a_pipeline_state_newer_than_the_code_stops_sw_run(data_dir: Path, tmp_path: Path) -> None:
    path = data_dir / "pipeline_state.db"
    _at_version(path, 99)
    root = _project(tmp_path)

    result = runner.invoke(
        app, ["run", "validate_only", str(root / "spec.md"), "--project", str(root)]
    )

    _stopped(result, str(path), "schema version 99")


def test_a_graph_database_newer_than_the_code_stops_sw_graph_build(
    data_dir: Path, tmp_path: Path
) -> None:
    root = _project(tmp_path)
    (root / "app.py").write_text("x = 1\n", encoding="utf-8")
    path = root / ".specweaver" / "graph.db"
    _at_version(path, 99)

    result = runner.invoke(app, ["graph", "build", str(root), "--project-path", str(root)])

    assert result.exit_code == 1, result.output
    assert shows(result.output, str(path)), result.output
    assert shows(result.output, "schema version 99"), result.output
