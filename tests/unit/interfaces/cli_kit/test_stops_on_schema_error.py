# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The CLI's one catch: a file that cannot be brought up to date stops the command, nothing else.

Proves: TECH-090 FR-7

| Bucket | Case |
|---|---|
| Happy | a `SchemaError` prints its message and exits 1 |
| Boundary | no error: the body's result comes back |
| Degradation | each member of the family is caught |
| Hostile | any other error passes through untouched, so the catch never hides a bug |
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from specweaver.infrastructure.database import SchemaOpenError, SchemaStepError, SchemaTooNewError
from specweaver.interfaces.cli_kit import _core

_FILE = Path("/data/specweaver.db")


@pytest.mark.parametrize(
    "error",
    [
        SchemaOpenError(_FILE, OSError("file is not a database")),
        SchemaStepError(_FILE, "create the configuration tables", RuntimeError("disk full")),
        SchemaTooNewError(_FILE, 99, 1),
    ],
    ids=["open", "step", "too-new"],
)
def test_a_schema_error_prints_its_message_and_exits_1(
    error: Exception, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(typer.Exit) as caught, _core.stops_on_schema_error():
        raise error

    assert caught.value.exit_code == 1
    assert str(_FILE) in capsys.readouterr().out.replace("\n", "")


def test_without_an_error_the_body_runs() -> None:
    with _core.stops_on_schema_error():
        result = 42

    assert result == 42


def test_any_other_error_passes_through() -> None:
    with pytest.raises(ValueError, match="a bug"), _core.stops_on_schema_error():
        raise ValueError("a bug")
