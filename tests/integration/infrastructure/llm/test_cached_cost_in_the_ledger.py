# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each token kind is billed at its own price, and the ledger row keeps the prices it was billed at.

Proves: TECH-074 FR-4, FR-6, FR-10, NFR-1

Settings file → `build_router` with a real SQLite ledger → a real adapter → its collector. Only HTTP
is faked. Prices, USD per 1M: input 1,000, cached read 100, output 1,000.

| Bucket | Case |
|---|---|
| Happy | 10,000 prompt tokens with 9,000 cached cost 1.91 USD, not 10.01; the row holds the counts and one price line per kind |
| Boundary | a model with no cached price bills its cached reads at the input price, and the line says so |
| Degradation | a reply with no cached count bills the whole prompt as uncached input; a database from before has the new columns after start-up |
| Hostile | a local call with no price set is marked local, not unpriced, and warns nothing |
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_BRAKE = """
[brake]
hosted_spend_per_run = 1000
tokens_per_run = 10000000
agent_turns = 5
"""
_HOSTED = (
    """\
[servers.hosted]
kind = "openai-compatible"
base_url = "http://hosted.example/v1"
private = false
max_parallel = 2

[roles]
default = { model = "big-model@hosted", max_output_tokens = 100 }

[models."big-model"]
usd_per_million_input = 1000.0
usd_per_million_output = 1000.0
{cached}thinking_in_output_cap = true
"""
    + _BRAKE
)
_CACHED = "usd_per_million_cached_read = 100.0\n"
_GB10 = (
    """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "qwen3-coder-next@gb10", max_output_tokens = 100 }
"""
    + _BRAKE
)
_PROMPT = [Message(role=Role.USER, content="hello")]


def _reply(details: dict | None) -> dict:
    usage = {"prompt_tokens": 10_000, "completion_tokens": 10, "total_tokens": 10_010}
    if details is not None:
        usage["prompt_tokens_details"] = details
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 1,
        "model": "m",
        "choices": [
            {"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}
        ],
        "usage": usage,
    }


async def _call(tmp_path: Path, machine: str, reply: dict) -> sqlite3.Connection:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    files = LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="settings.toml", project_text="", project_source="-"
    )
    routed = build_router(
        files, project="demo", roles=[TaskType.REVIEW], db=Database(path)
    ).get_for_task(TaskType.REVIEW)
    with fake_httpx2(lambda _request: httpx2.Response(200, json=reply)):
        await routed.adapter.generate(_PROMPT, routed.config)
    return sqlite3.connect(path)


def _row(conn: sqlite3.Connection) -> tuple:
    return conn.execute(
        "SELECT prompt_tokens, cached_read_tokens, cache_write_tokens, estimated_cost, local "
        "FROM llm_usage_log"
    ).fetchone()


def _lines(conn: sqlite3.Connection) -> list[tuple]:
    return conn.execute(
        "SELECT token_kind, usd_per_million, source FROM llm_usage_price ORDER BY token_kind"
    ).fetchall()


async def test_each_kind_is_billed_at_its_own_price(tmp_path: Path) -> None:
    conn = await _call(
        tmp_path, _HOSTED.replace("{cached}", _CACHED), _reply({"cached_tokens": 9000})
    )

    prompt, read, write, cost, local = _row(conn)
    assert (prompt, read, write, local) == (10_000, 9000, 0, 0)
    assert cost == pytest.approx(1.91)
    assert _lines(conn) == [
        ("cached_read", 100.0, "settings"),
        ("input", 1000.0, "settings"),
        ("output", 1000.0, "settings"),
    ]


async def test_a_cached_read_without_its_own_price_is_billed_as_input(tmp_path: Path) -> None:
    conn = await _call(tmp_path, _HOSTED.replace("{cached}", ""), _reply({"cached_tokens": 9000}))

    assert _row(conn)[3] == pytest.approx(10.01)
    assert ("cached_read", 1000.0, "settings, as input") in _lines(conn)


async def test_an_unknown_cached_count_bills_the_whole_prompt_as_input(tmp_path: Path) -> None:
    conn = await _call(tmp_path, _HOSTED.replace("{cached}", _CACHED), _reply(None))

    prompt, read, _write, cost, _local = _row(conn)
    assert (prompt, read) == (10_000, None)
    assert cost == pytest.approx(10.01)


async def test_a_local_call_is_local_not_unpriced(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        conn = await _call(tmp_path, _GB10, _reply({"cached_tokens": 9000}))

    _prompt, read, _write, cost, local = _row(conn)
    assert (read, cost, local) == (9000, None, 1)
    assert _lines(conn) == []
    assert not [r for r in caplog.records if "no known price" in r.getMessage()]


def test_an_older_database_gains_the_columns_and_keeps_its_rows(tmp_path: Path) -> None:
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE llm_usage_log (id INTEGER PRIMARY KEY, timestamp VARCHAR NOT NULL,"
            " project_name VARCHAR NOT NULL, task_type VARCHAR NOT NULL, model VARCHAR NOT NULL,"
            " provider VARCHAR NOT NULL, prompt_tokens INTEGER NOT NULL,"
            " completion_tokens INTEGER NOT NULL, total_tokens INTEGER NOT NULL,"
            " estimated_cost FLOAT, duration_ms INTEGER NOT NULL, run_id VARCHAR)"
        )
        conn.execute(
            "INSERT INTO llm_usage_log VALUES (1, '2026-01-01T00:00:00+00:00', 'p', 'draft', 'm',"
            " 'x', 10, 5, 15, 0.5, 10, 'r')"
        )

    bootstrap_database(str(path))

    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT prompt_tokens, cached_read_tokens, cache_write_tokens, local FROM llm_usage_log"
        ).fetchone()
    assert row == (10, None, None, None)


async def test_the_usage_summary_counts_cached_unknown_and_local_calls(tmp_path: Path) -> None:
    from specweaver.infrastructure.llm.store import LlmRepository

    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    with sqlite3.connect(path) as conn:
        rows = ((800, 0.1, 0), (None, 0.1, 0), (300, None, 1), (None, None, 0), (None, None, None))
        for cached, cost, local in rows:
            conn.execute(
                "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider,"
                " prompt_tokens, completion_tokens, total_tokens, estimated_cost, duration_ms,"
                " cached_read_tokens, local) VALUES ('2026-10-18T00:00:00+00:00', 'p', 'review',"
                " 'm', 'x', 1000, 1, 1001, ?, 10, ?, ?)",
                (cost, cached, local),
            )

    async with Database(path).async_session_scope() as session:
        [row] = await LlmRepository(session).get_usage_summary(project="p")

    assert (row["total_cached"], row["unknown_cached"]) == (1100, 3)
    assert (row["unpriced_calls"], row["local_calls"]) == (2, 1)
