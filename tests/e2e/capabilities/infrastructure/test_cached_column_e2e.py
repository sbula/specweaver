# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw usage` shows how many prompt tokens came from a cache; unknown is never shown as 0.

Proves: TECH-074 FR-6, FR-10

| Bucket | Case |
|---|---|
| Happy | two calls with 800 and 200 cached tokens show 1,000 |
| Boundary | not here: a cell's text is width-bound in a table, so `test_usage_cells.py` checks it |
| Degradation | not here, for the same reason |
| Hostile | a local call with no price shows its cost as n/a, never as unknown |
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from typer.testing import CliRunner

from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()


def _usage(tmp_path: Path, env: Path, rows: list[tuple]) -> str:
    project = tmp_path / "proj"
    project.mkdir()
    assert runner.invoke(app, ["init", "cache-demo", "--path", str(project)]).exit_code == 0
    now = datetime.now(UTC).isoformat()
    with sqlite3.connect(env / "specweaver.db") as conn:
        for model, cached, cost, local in rows:
            conn.execute(
                "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider,"
                " prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms,"
                " cached_read_tokens, local) VALUES (?, 'cache-demo', 'review', ?, 'x', 1000, 1,"
                " 1001, ?, 10, ?, ?)",
                (now, model, cost, cached, local),
            )
    result = runner.invoke(app, ["usage"])
    assert result.exit_code == 0, result.output
    return result.output


def test_cached_tokens_are_summed(tmp_path: Path, _mock_db: Database, _isolate_env: Path) -> None:
    output = _usage(tmp_path, _isolate_env, [("m", 800, 0.1, 0), ("m", 200, 0.1, 0)])

    assert shows(output, "Cached")
    assert shows(output, "1,000")


def test_a_local_call_without_a_price_costs_n_a(
    tmp_path: Path, _mock_db: Database, _isolate_env: Path
) -> None:
    output = _usage(tmp_path, _isolate_env, [("m", 300, None, 1)])

    assert shows(output, "n/a")
    assert not shows(output, "unknown")
