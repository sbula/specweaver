# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The run setup brings `reservations.db` up to date before the first step, creating it if missing.

A real database and project; no model step, so no model is needed.

Proves: TECH-090 FR-7

| Bucket | Case |
|---|---|
| Happy | a project without `reservations.db` gets one at the current version from `build_run` |
| Boundary | a current file is left as it is, with its held locks; a removed project folder is not made again |
| Degradation | a file newer than the code makes `build_run` raise, naming it; `sw run` stops with the message |
| Hostile | a file that is not a database makes `build_run` raise `SchemaOpenError` |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
from specweaver.core.flow.engine.reservation import SQLiteReservationSystem, reservations_path
from specweaver.infrastructure.database import (
    Database,
    SchemaError,
    SchemaOpenError,
    SchemaTooNewError,
)
from specweaver.interfaces.cli.main import app
from specweaver.interfaces.run_setup.builder import RunRequest, build_run_sync
from tests.fixtures.db_utils import register_test_project, set_user_version, user_version
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

runner = CliRunner()


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Database, Path]:
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(data))
    bootstrap_database(str(data / "specweaver.db"))
    db = Database(data / "specweaver.db")
    root = tmp_path / "proj"
    (root / "specs").mkdir(parents=True)
    (root / "specs" / "orders_spec.md").write_text("# Orders\n", encoding="utf-8")
    register_test_project(db, "proj", str(root))
    return db, root


def _request(db: Database, root: Path) -> RunRequest:
    pipeline = PipelineDefinition.create_single_step("one", StepAction.VALIDATE, StepTarget.SPEC)
    return RunRequest(
        project_root=root,
        spec_path=root / "specs" / "orders_spec.md",
        pipeline=pipeline,
        project="proj",
        db=db,
    )


def test_the_run_setup_creates_reservations_at_the_current_version(
    world: tuple[Database, Path],
) -> None:
    db, root = world
    path = root / ".specweaver" / "reservations.db"

    build_run_sync(_request(db, root))

    assert user_version(path) == 1


def test_a_current_file_keeps_its_held_locks(world: tuple[Database, Path]) -> None:
    db, root = world
    assert SQLiteReservationSystem(reservations_path(root)).acquire("res", "run-1")

    build_run_sync(_request(db, root))

    assert not SQLiteReservationSystem(reservations_path(root)).acquire("res", "run-2")


def test_a_removed_project_folder_is_not_made_again(world: tuple[Database, Path]) -> None:
    db, root = world
    request = _request(db, root)
    for entry in sorted(root.rglob("*"), reverse=True):
        entry.rmdir() if entry.is_dir() else entry.unlink()
    root.rmdir()

    build_run_sync(request)

    assert not root.exists()


def test_a_newer_file_makes_the_run_setup_raise(world: tuple[Database, Path]) -> None:
    db, root = world
    path = root / ".specweaver" / "reservations.db"
    set_user_version(path, 99)

    with pytest.raises(SchemaTooNewError, match="schema version 99") as caught:
        build_run_sync(_request(db, root))

    assert isinstance(caught.value, SchemaError)
    assert str(path) in str(caught.value)


def test_a_file_that_is_not_a_database_makes_the_run_setup_raise(
    world: tuple[Database, Path],
) -> None:
    db, root = world
    path = root / ".specweaver" / "reservations.db"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"this is not a database " * 100)

    with pytest.raises(SchemaOpenError, match="cannot be opened"):
        build_run_sync(_request(db, root))


def test_sw_run_stops_on_a_newer_reservations_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SPECWEAVER_DATA_DIR", str(tmp_path / "data"))
    root = tmp_path / "proj"
    root.mkdir()
    assert runner.invoke(app, ["init", "proj", "--path", str(root)]).exit_code == 0
    (root / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (root / "spec.md").write_text("# Spec\n", encoding="utf-8")
    path = root / ".specweaver" / "reservations.db"
    set_user_version(path, 99)

    result = runner.invoke(
        app, ["run", "validate_only", str(root / "spec.md"), "--project", str(root)]
    )

    assert result.exit_code == 1, result.output
    assert isinstance(result.exception, SystemExit), result.exception
    assert shows(result.output, str(path)), result.output
    assert shows(result.output, "schema version 99"), result.output
    assert not shows(result.output, "Running"), result.output
    # The door's own message, not the run's catch-all naming the exception class.
    assert not shows(result.output, "SchemaTooNewError"), result.output
