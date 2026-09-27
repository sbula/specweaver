# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prices and spend in the one configured currency, taken from the settings file (US-16 P6).

Proves: C-FLOW-13 FR-12, FR-13, FR-15

| Bucket | Case |
|---|---|
| Happy | `sw costs set` in CHF → stored as USD in the file → `sw costs` shows the CHF price back |
| Boundary | no `[currency]` → every amount in USD |
| Degradation | a model with no price shows as unknown; `sw usage` marks unpriced calls, never 0 |
| Hostile | `sw costs reset` removes only the price; the file's other lines stay |
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.core.config.llm_settings import parse_machine_file
from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()

_MACHINE = """\
# my settings
[currency]
code = "CHF"
per_usd = 0.8
rate_date = 2026-09-26

[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
draft = "qwen3-coder-next@gb10"
"""


def _project(tmp_path: Path) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "costs-demo", "--path", str(project)]).exit_code == 0


def test_a_price_set_in_chf_is_stored_in_usd_and_shown_in_chf(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    machine = _isolate_env / "settings.toml"
    machine.write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)

    set_price = runner.invoke(app, ["costs", "set", "qwen3-coder-next", "0.8", "1.6"])
    shown = runner.invoke(app, ["costs"])

    assert set_price.exit_code == 0, set_price.output
    facts = parse_machine_file(machine.read_text(encoding="utf-8"), "x").models["qwen3-coder-next"]
    assert (facts.usd_per_million_input, facts.usd_per_million_output) == (1.0, 2.0)
    assert shown.exit_code == 0, shown.output
    assert shows(shown.output, "CHF 0.8000")
    assert shows(shown.output, "CHF 1.6000")
    assert shows(shown.output, "rate of 2026-09-26")


def test_without_a_currency_everything_is_usd_and_unknown_stays_unknown(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    without_currency = "[servers.gb10]" + _MACHINE.split("[servers.gb10]")[1]
    (_isolate_env / "settings.toml").write_text(without_currency, encoding="utf-8")
    _project(tmp_path)

    shown = runner.invoke(app, ["costs"])

    assert shown.exit_code == 0, shown.output
    assert shows(shown.output, "USD")
    assert shows(shown.output, "unknown")


def test_reset_removes_only_the_price(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    machine = _isolate_env / "settings.toml"
    machine.write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)
    runner.invoke(app, ["costs", "set", "qwen3-coder-next", "0.8", "1.6"])

    reset = runner.invoke(app, ["costs", "reset", "qwen3-coder-next"])

    assert reset.exit_code == 0, reset.output
    assert machine.read_text(encoding="utf-8").rstrip() == _MACHINE.rstrip()


def test_usage_marks_unpriced_calls_in_the_configured_currency(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    _project(tmp_path)
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(_isolate_env / "specweaver.db") as conn:
        for model, cost in (("claude-opus-5-5", 1.25), ("qwen3-coder-next", None)):
            conn.execute(
                "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider,"
                " prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms)"
                " VALUES (?, 'costs-demo', 'draft', ?, 'x', 1, 1, 2, ?, 10)",
                (now, model, cost),
            )

    usage = runner.invoke(app, ["usage"])

    assert usage.exit_code == 0, usage.output
    assert shows(usage.output, "(CHF)")  # in the title, which Rich never truncates
    assert shows(usage.output, "unknown")
