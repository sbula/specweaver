# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every command that gets a router says at its end how many calls the cost ledger is missing.

Proves: C-FLOW-01 FR-5

A real Typer command hands its router to `tell_missing_at_end`, as every command's run setup does
(`interfaces/cli/run_doors.py`); only the router is a double.

| Bucket | Case |
|---|---|
| Happy | a command with 3 missing calls ends with the line, on stderr |
| Boundary | none missing: no line; the line also comes after `typer.Exit(1)` |
| Degradation | a router that cannot count leaves a warning, never a traceback or a failed end |
| Hostile | stdout stays free of the line, so `--json` output stays clean |
"""

from __future__ import annotations

from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from specweaver.infrastructure.llm.interfaces import command
from tests.rendering import shows

pytestmark = pytest.mark.integration

_LINE = "calls of this command are missing from the cost ledger or were not closed in it"


class _Router:
    def __init__(self, missing: Any) -> None:
        self.missing = missing

    def unwritten(self) -> int:
        if isinstance(self.missing, Exception):
            raise self.missing
        return self.missing


def _app(missing: Any, *, fail: bool) -> typer.Typer:
    app = typer.Typer()

    @app.command()
    def work() -> None:
        command.tell_missing_at_end(_Router(missing))
        typer.echo("done")
        if fail:
            raise typer.Exit(code=1)

    @app.command()
    def other() -> None:  # a second command keeps Typer from flattening the app
        pass

    return app


@pytest.mark.parametrize("fail", [False, True], ids=["ok", "exit-1"])
def test_a_command_ends_saying_how_many_calls_are_missing(fail: bool) -> None:
    result = CliRunner().invoke(_app(3, fail=fail), ["work"])

    assert result.exit_code == (1 if fail else 0)
    assert shows(result.stderr, f"3 {_LINE}")
    assert _LINE not in result.stdout
    assert result.stdout.strip() == "done"


def test_one_missing_call_is_said_in_the_singular() -> None:
    result = CliRunner().invoke(_app(1, fail=False), ["work"])

    assert shows(result.stderr, "1 call of this command is missing from the cost ledger")


def test_no_missing_call_says_nothing() -> None:
    result = CliRunner().invoke(_app(0, fail=False), ["work"])

    assert result.exit_code == 0
    assert "cost ledger" not in result.output


def test_a_router_that_cannot_count_leaves_the_end_alone() -> None:
    app = _app(RuntimeError("closed"), fail=False)

    result = CliRunner().invoke(app, ["work"])

    assert result.exit_code == 0
    assert result.exception is None
    assert "Traceback" not in result.output
    assert _LINE not in result.output
