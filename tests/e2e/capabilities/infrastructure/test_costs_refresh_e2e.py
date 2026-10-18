# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw costs refresh` fetches the prices now, says what changed, and `sw costs` shows them.

Proves: TECH-074 FR-7
Proves: C-FLOW-13 FR-18

The real CLI over a real database; only models.dev's reply is faked.

| Bucket | Case |
|---|---|
| Happy | a changed price is reported, and `sw costs` then shows it with source models.dev |
| Boundary | nothing changed says so; `sw costs` names the day models.dev was last reached, or that it never was |
| Degradation | models.dev unreachable: the command says the last prices stay, and exits 0 |
| Hostile | not applicable — the command takes no input |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.fake_http import fake_httpx2
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()

_MACHINE = """\
[servers.anthropic]
kind = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"
private = false
max_parallel = 1

[roles]
draft = "claude-opus-5-5@anthropic"
"""


def _api(price: float) -> dict:
    cost = {"input": price, "output": 20, "cache_read": 0.2, "cache_write": 5}
    return {"anthropic": {"models": {"claude-opus-5-5": {"id": "claude-opus-5-5", "cost": cost}}}}


def _setup(tmp_path: Path, env: Path) -> None:
    (env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "refresh-demo", "--path", str(project)]).exit_code == 0


def test_a_refresh_reports_the_change_and_costs_shows_it(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    _setup(tmp_path, _isolate_env)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_api(4.5))):
        refreshed = runner.invoke(app, ["costs", "refresh"])
    shown = runner.invoke(app, ["costs"])

    assert refreshed.exit_code == 0, refreshed.output
    assert shows(refreshed.output, "4.0 → 4.5")
    assert shows(shown.output, "input USD 4.5000")
    assert shows(shown.output, "per 1M tokens — models.dev")  # the price line, not the header


def test_nothing_changed_says_so(tmp_path: Path, _mock_db: Database, _isolate_env: Path) -> None:
    _setup(tmp_path, _isolate_env)

    with fake_httpx2(lambda _request: httpx2.Response(200, json=_api(4.0))):
        refreshed = runner.invoke(app, ["costs", "refresh"])

    assert refreshed.exit_code == 0, refreshed.output
    assert shows(refreshed.output, "No price changed")


def test_unreachable_keeps_the_last_prices(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    _setup(tmp_path, _isolate_env)

    with fake_httpx2(lambda _request: httpx2.Response(503)):
        refreshed = runner.invoke(app, ["costs", "refresh"])

    assert refreshed.exit_code == 0, refreshed.output
    assert shows(refreshed.output, "last prices stay")


def test_costs_says_when_models_dev_was_last_reached(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    from datetime import UTC, datetime

    _setup(tmp_path, _isolate_env)
    before = runner.invoke(app, ["costs"])
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_api(4.0))):
        runner.invoke(app, ["costs", "refresh"])
    after = runner.invoke(app, ["costs"])

    assert shows(before.output, "models.dev not reached yet")
    assert shows(after.output, f"models.dev reached {datetime.now(UTC).date().isoformat()}")
    assert not shows(after.output, "Prices from the shipped list")


def test_a_failed_refresh_is_not_a_reach(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    _setup(tmp_path, _isolate_env)

    with fake_httpx2(lambda _request: httpx2.Response(503)):
        runner.invoke(app, ["costs", "refresh"])
    shown = runner.invoke(app, ["costs"])

    assert shows(shown.output, "models.dev not reached yet")
