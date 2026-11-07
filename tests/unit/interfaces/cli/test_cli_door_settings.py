# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The CLI door sets its process settings: a 30 s lock wait, and logging to the active project's
file once a command uses the database.

Proves: TECH-090 FR-2, FR-8, AD-4, AD-5

| Bucket | Case |
|---|---|
| Happy | after a command the lock wait is 30 s; a command that uses the database logs to the active project's file at its levels |
| Boundary | a command that needs no database logs at the defaults, to `_global`; two commands in one process each log to their own project |
| Degradation | a project level the database cannot give falls back to the defaults |
| Hostile | no active project: a command that uses the database logs to `_global` |
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.database import lock_wait_seconds, set_lock_wait
from specweaver.interfaces.cli.main import app
from specweaver.interfaces.cli_kit import _core

runner = CliRunner()


@pytest.fixture()
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "data"
    path.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(path))
    # tests/unit/conftest.py points the config database elsewhere; bring it back into this dir.
    monkeypatch.setattr(
        "specweaver.core.config.bootstrap.db_bootstrap.config_db_path",
        lambda: path / "specweaver.db",
    )
    return path


def _init(tmp_path: Path, name: str) -> None:
    root = tmp_path / name
    root.mkdir()
    result = runner.invoke(app, ["init", name, "--path", str(root)])
    assert result.exit_code == 0, result.output


def _file_handler() -> RotatingFileHandler:
    handlers = logging.getLogger("specweaver").handlers
    (handler,) = [h for h in handlers if isinstance(h, RotatingFileHandler)]
    return handler


def _log_file() -> Path:
    return Path(_file_handler().baseFilename)


def test_the_cli_sets_a_30_second_lock_wait(data_dir: Path) -> None:
    set_lock_wait(1)

    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert lock_wait_seconds() == 30


def test_a_command_that_uses_the_database_logs_to_the_active_project(
    data_dir: Path, tmp_path: Path
) -> None:
    _init(tmp_path, "alpha")
    _core.run_repo_op(lambda r: r.set_log_level("alpha", "INFO"))

    result = runner.invoke(app, ["projects"])

    assert result.exit_code == 0, result.output
    assert _log_file() == data_dir / "logs" / "alpha" / "specweaver.log"
    assert _file_handler().level == logging.INFO


def test_a_command_that_needs_no_database_logs_at_the_defaults(
    data_dir: Path, tmp_path: Path
) -> None:
    _init(tmp_path, "alpha")
    _core.run_repo_op(lambda r: r.set_log_level("alpha", "INFO"))

    result = runner.invoke(app, ["run", "--help"])

    assert result.exit_code == 0, result.output
    assert _log_file() == data_dir / "logs" / "_global" / "specweaver.log"
    assert _file_handler().level == logging.DEBUG


def test_two_commands_in_one_process_each_log_to_their_own_project(
    data_dir: Path, tmp_path: Path
) -> None:
    _init(tmp_path, "alpha")
    _init(tmp_path, "beta")
    assert runner.invoke(app, ["use", "alpha"]).exit_code == 0

    assert runner.invoke(app, ["projects"]).exit_code == 0
    assert _log_file().parent.name == "alpha"

    assert runner.invoke(app, ["use", "beta"]).exit_code == 0
    assert runner.invoke(app, ["projects"]).exit_code == 0
    assert _log_file().parent.name == "beta"


def test_no_active_project_logs_to_global(data_dir: Path) -> None:
    result = runner.invoke(app, ["projects"])

    assert result.exit_code == 0, result.output
    assert _log_file() == data_dir / "logs" / "_global" / "specweaver.log"


def test_an_unreadable_project_level_falls_back_to_the_defaults(
    data_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _init(tmp_path, "alpha")
    from specweaver.workspace.store import WorkspaceRepository

    async def _broken(self: object, name: str) -> str:
        raise ValueError("no such level")

    monkeypatch.setattr(WorkspaceRepository, "get_log_level", _broken)

    result = runner.invoke(app, ["projects"])

    assert result.exit_code == 0, result.output
    assert _log_file().parent.name == "alpha"
    assert _file_handler().level == logging.DEBUG
