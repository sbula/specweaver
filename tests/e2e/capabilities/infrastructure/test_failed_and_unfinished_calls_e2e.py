# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw usage` and `sw costs` name failed calls, and show unfinished ones apart from the totals.

Proves: C-FLOW-01 FR-6

The ledger is written through the repository calls the collector uses; the commands read their own
database (`tests/e2e/conftest.py::_isolate_env`).

| Bucket | Case |
|---|---|
| Happy | an `ok`, a `failed` and a `pending` call: both commands say *of which failed* and *not finished* |
| Boundary | only finished calls: neither line appears |
| Degradation | a failed call with no price and tokens unknown shows as unknown, never 0 |
| Hostile | another project's unfinished call never shows in this project's usage |
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from specweaver.infrastructure.llm.store import LlmRepository
from specweaver.interfaces.cli.main import app
from tests.rendering import shows

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

runner = CliRunner()
pytestmark = pytest.mark.e2e

_PROJECT = "ledger-demo"

_MACHINE = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 4

[roles]
implement = "coder-a@gb10"
"""

_NOT_FINISHED = "not finished (running now, or the process was killed)"


def _record(**overrides: Any) -> dict[str, Any]:
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "project_name": _PROJECT,
        "task_type": "implement",
        "model": "coder-a",
        "provider": "openai-compatible",
        "prompt_tokens": 60,
        "completion_tokens": 40,
        "total_tokens": 100,
        "estimated_cost_usd": 0.11,
        "duration_ms": 10,
        "run_id": "r1",
        "server": "gb10",
        "dal_level": "DAL_C",
        "step_name": "generate_code",
    }
    return record | overrides


def _call(db: Database, status: str | None, **overrides: Any) -> None:
    """One call as the collector writes it; `status` None leaves it `pending`."""
    record = _record(**overrides)

    async def _write() -> None:
        async with db.async_session_scope() as session:
            call_id = await LlmRepository(session).open_call(record)
        if status is not None:
            async with db.async_session_scope() as session:
                await LlmRepository(session).close_call(call_id, record, status)

    asyncio.run(_write())


@pytest.fixture
def project(tmp_path: Path, _isolate_env: Path) -> None:
    (_isolate_env / "settings.toml").write_text(_MACHINE, encoding="utf-8")
    folder = tmp_path / "proj"
    folder.mkdir()
    assert runner.invoke(app, ["init", _PROJECT, "--path", str(folder)]).exit_code == 0


@pytest.mark.parametrize("command", ["usage", "costs"])
def test_failed_calls_are_named_and_unfinished_ones_kept_apart(
    project: None, _mock_db: Database, command: str
) -> None:
    _call(_mock_db, "ok")
    _call(_mock_db, "failed", total_tokens=777, estimated_cost_usd=0.37)
    _call(_mock_db, None, total_tokens=9123, estimated_cost_usd=4.56)

    result = runner.invoke(app, [command])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "of which failed: 1 call, USD 0.37")
    assert shows(result.output, f"{_NOT_FINISHED}: 1 call, at most 9,123 tokens, USD 4.56")
    assert result.output.count("4.56") == 1  # the worst case is in no total


@pytest.mark.parametrize("command", ["usage", "costs"])
def test_only_finished_calls_show_neither_line(
    project: None, _mock_db: Database, command: str
) -> None:
    _call(_mock_db, "ok")

    result = runner.invoke(app, [command])

    assert result.exit_code == 0, result.output
    assert "failed" not in result.output
    assert "not finished" not in result.output


def test_a_failed_call_of_unknown_cost_stays_unknown(project: None, _mock_db: Database) -> None:
    _call(_mock_db, "failed", total_tokens=0, estimated_cost_usd=None)
    _call(_mock_db, "failed", total_tokens=500, estimated_cost_usd=0.25)

    result = runner.invoke(app, ["usage"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, "of which failed: 2 calls, USD 0.25 + 1 unknown")


def test_only_unfinished_calls_still_show_their_line(project: None, _mock_db: Database) -> None:
    _call(_mock_db, None, total_tokens=4000, estimated_cost_usd=None)

    result = runner.invoke(app, ["usage"])

    assert result.exit_code == 0, result.output
    assert shows(result.output, f"{_NOT_FINISHED}: 1 call, at most 4,000 tokens, unknown")


def test_another_projects_unfinished_call_is_not_shown(project: None, _mock_db: Database) -> None:
    _call(_mock_db, "ok")
    _call(_mock_db, None, project_name="someone-else")

    result = runner.invoke(app, ["usage"])

    assert result.exit_code == 0, result.output
    assert "not finished" not in result.output
