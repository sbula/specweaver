# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw costs` shows the prices the ledger uses: the base input price, not the cache-write price.

Proves: TECH-074 FR-2, FR-4

| Bucket | Case |
|---|---|
| Happy | an Opus role shows input 4 and output 20 from the catalogue |
| Boundary | a price in the settings file is shown, and named as yours; a model with no cached price says its cached reads are billed as input |
| Degradation | not applicable — a missing database is covered by the integration tests |
| Hostile | not applicable — the command reads no input but the settings file, covered by its own tests |
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
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


def _project(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "price-demo", "--path", str(project)]).exit_code == 0


def test_costs_shows_the_base_input_price(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)

    shown = runner.invoke(app, ["costs"])

    assert shown.exit_code == 0, shown.output
    assert shows(shown.output, "input USD 4.0000")
    assert shows(shown.output, "output USD 20.0000")
    assert shows(shown.output, "catalogue")


def test_costs_shows_a_settings_price_as_yours(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(
        _MACHINE + '\n[models."claude-opus-5-5"]\nusd_per_million_input = 3.25\n', encoding="utf-8"
    )
    _project(tmp_path)

    shown = runner.invoke(app, ["costs"])

    assert shown.exit_code == 0, shown.output
    assert shows(shown.output, "input USD 3.2500")
    assert shows(shown.output, "your settings file")


def test_costs_says_when_cached_reads_are_billed_as_input(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(
        """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 1

[roles]
draft = "big-model@hosted"

[models."big-model"]
usd_per_million_input = 2.0
usd_per_million_output = 8.0
""",
        encoding="utf-8",
    )
    _project(tmp_path)

    shown = runner.invoke(app, ["costs"])

    assert shown.exit_code == 0, shown.output
    assert shows(shown.output, "cached reads billed as input")


def test_costs_says_nothing_when_cached_reads_have_their_price(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)

    shown = runner.invoke(app, ["costs"])

    assert not shows(shown.output, "billed as input")
