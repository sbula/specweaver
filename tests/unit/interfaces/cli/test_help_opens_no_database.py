# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Help and the version open no database: they show even when the database file is broken.

Proves: TECH-090 FR-8, NFR-4

| Bucket | Case |
|---|---|
| Happy | `sw --help`, `sw --version`, `sw run --help`, `sw graph build --help` show and exit 0 |
| Boundary | on an empty data dir, help creates no database file |
| Degradation | a `specweaver.db` that is not a database does not stop help |
| Hostile | a `pipeline_state.db` that is not a database does not stop help |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app

if TYPE_CHECKING:
    from pathlib import Path

runner = CliRunner()

_GARBAGE = b"this is not a database " * 100

_HELP = [
    pytest.param(["--help"], "Usage", id="sw --help"),
    pytest.param(["--version"], "SpecWeaver v", id="sw --version"),
    pytest.param(["run", "--help"], "Usage", id="sw run --help"),
    pytest.param(["graph", "build", "--help"], "Usage", id="sw graph build --help"),
]


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


@pytest.mark.parametrize(("args", "shown"), _HELP)
@pytest.mark.parametrize("broken", ["specweaver.db", "pipeline_state.db"])
def test_help_shows_with_a_broken_database(
    data_dir: Path, args: list[str], shown: str, broken: str
) -> None:
    (data_dir / broken).write_bytes(_GARBAGE)

    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.output
    assert shown in result.output
    assert (data_dir / broken).read_bytes() == _GARBAGE


@pytest.mark.parametrize(("args", "shown"), _HELP)
def test_help_creates_no_database(data_dir: Path, args: list[str], shown: str) -> None:
    result = runner.invoke(app, args)

    assert result.exit_code == 0, result.output
    assert sorted(p.name for p in data_dir.glob("*.db")) == []
