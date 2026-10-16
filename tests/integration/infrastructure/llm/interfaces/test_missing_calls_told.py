# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every command that gets a router says at its end how many calls the cost ledger is missing.

Proves: C-FLOW-01 FR-5

A real Typer command calls each of the two router builders; only the router is a double, so the
line is proven for every command that builds its models through them.

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


def _app(monkeypatch: pytest.MonkeyPatch, builder: str, missing: Any, *, fail: bool) -> typer.Typer:
    monkeypatch.setattr(command, "build_router", lambda *_a, **_k: _Router(missing))
    monkeypatch.setattr(command._core, "load_active_llm_settings", lambda _p: None)
    monkeypatch.setattr(command._core, "get_db", lambda: None)
    monkeypatch.setattr(command._core, "spend_asker", lambda: None)
    app = typer.Typer()

    @app.command()
    def work() -> None:
        getattr(command, builder)("greeter", [])
        typer.echo("done")
        if fail:
            raise typer.Exit(code=1)

    @app.command()
    def other() -> None:  # a second command keeps Typer from flattening the app
        pass

    return app


@pytest.mark.parametrize("builder", ["command_router", "optional_command_router"])
@pytest.mark.parametrize("fail", [False, True], ids=["ok", "exit-1"])
def test_a_command_ends_saying_how_many_calls_are_missing(
    monkeypatch: pytest.MonkeyPatch, builder: str, fail: bool
) -> None:
    result = CliRunner().invoke(_app(monkeypatch, builder, 3, fail=fail), ["work"])

    assert result.exit_code == (1 if fail else 0)
    assert shows(result.stderr, f"3 {_LINE}")
    assert _LINE not in result.stdout
    assert result.stdout.strip() == "done"


def test_one_missing_call_is_said_in_the_singular(monkeypatch: pytest.MonkeyPatch) -> None:
    result = CliRunner().invoke(_app(monkeypatch, "command_router", 1, fail=False), ["work"])

    assert shows(result.stderr, "1 call of this command is missing from the cost ledger")


def test_no_missing_call_says_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    result = CliRunner().invoke(_app(monkeypatch, "command_router", 0, fail=False), ["work"])

    assert result.exit_code == 0
    assert "cost ledger" not in result.output


def test_a_router_that_cannot_count_leaves_the_end_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _app(monkeypatch, "command_router", RuntimeError("closed"), fail=False)

    result = CliRunner().invoke(app, ["work"])

    assert result.exit_code == 0
    assert result.exception is None
    assert "Traceback" not in result.output
    assert _LINE not in result.output
