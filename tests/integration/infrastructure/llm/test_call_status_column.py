# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each ledger row says whether its call is pending, ok or failed; older rows count as ok.

Proves: C-FLOW-01 FR-8

A real SQLite ledger, built by the real start-up.

| Bucket | Case |
|---|---|
| Happy | a call is opened `pending` with its worst case, then closed `ok` with its real numbers |
| Boundary | a ledger from before the column gains it, its rows become `ok`, and a second start changes nothing |
| Degradation | closing a row that is not there changes nothing and says so |
| Hostile | a call cannot be opened as anything but `pending`, nor closed as anything but `ok` or `failed` |
"""

from __future__ import annotations

import asyncio
import sqlite3
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.infrastructure.llm.store import LlmRepository

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


def _record(**overrides: Any) -> dict[str, Any]:
    record = {
        "timestamp": "2026-10-16T08:00:00+00:00",
        "project_name": "greeter",
        "task_type": "implement",
        "model": "coder-a",
        "provider": "openai-compatible",
        "prompt_tokens": 1250,
        "completion_tokens": 1000,
        "total_tokens": 2250,
        "estimated_cost_usd": 0.5,
        "duration_ms": 0,
        "run_id": "r1",
        "server": "gb10",
        "dal_level": "DAL_C",
        "step_name": "generate_code",
    }
    return record | overrides


@pytest.fixture
def db(tmp_path: Path) -> Database:
    bootstrap_database(str(tmp_path / "specweaver.db"))
    return Database(tmp_path / "specweaver.db")


def _rows(path: Path) -> list[tuple[Any, ...]]:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT call_status, total_tokens, estimated_cost, duration_ms FROM llm_usage_log"
        ).fetchall()


async def _open(db: Database, record: dict[str, Any]) -> int:
    async with db.async_session_scope() as session:
        return await LlmRepository(session).open_call(record)


async def _close(db: Database, call_id: int, record: dict[str, Any], status: str) -> bool:
    async with db.async_session_scope() as session:
        return await LlmRepository(session).close_call(call_id, record, status)


def test_a_call_is_opened_pending_then_closed_with_its_real_numbers(
    tmp_path: Path, db: Database
) -> None:
    call_id = asyncio.run(_open(db, _record()))
    opened = _rows(tmp_path / "specweaver.db")

    real = _record(
        prompt_tokens=300,
        completion_tokens=120,
        total_tokens=420,
        estimated_cost_usd=0.07,
        duration_ms=850,
    )
    closed = asyncio.run(_close(db, call_id, real, "ok"))

    assert opened == [("pending", 2250, 0.5, 0)]
    assert closed is True
    assert _rows(tmp_path / "specweaver.db") == [("ok", 420, 0.07, 850)]


def test_an_older_ledger_gains_the_column_and_its_rows_count_as_ok(
    tmp_path: Path, db: Database
) -> None:
    path = tmp_path / "specweaver.db"
    asyncio.run(_open(db, _record()))
    with sqlite3.connect(path) as conn:
        conn.execute("ALTER TABLE llm_usage_log DROP COLUMN call_status")

    bootstrap_database(str(path))
    first = _rows(path)
    bootstrap_database(str(path))

    assert first == [("ok", 2250, 0.5, 0)]
    assert _rows(path) == first


def test_closing_a_missing_row_changes_nothing(tmp_path: Path, db: Database) -> None:
    assert asyncio.run(_close(db, 4711, _record(), "ok")) is False
    assert _rows(tmp_path / "specweaver.db") == []


@pytest.mark.parametrize("status", ["pending", "done", "", "OK"])
def test_a_call_closes_only_as_ok_or_failed(db: Database, status: str) -> None:
    call_id = asyncio.run(_open(db, _record()))

    with pytest.raises(ValueError, match="ok or failed"):
        asyncio.run(_close(db, call_id, _record(), status))
