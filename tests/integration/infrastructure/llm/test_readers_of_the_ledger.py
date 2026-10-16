# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The ledger's readers count real spend: failed calls in, unfinished ones apart, never in a total.

Proves: C-FLOW-01 FR-6
Proves: C-FLOW-01 FR-7

A real SQLite ledger; its rows are written through the same repository calls the collector uses.

| Bucket | Case |
|---|---|
| Happy | an `ok`, a `failed` and a `pending` call: every total holds the first two only |
| Boundary | a `pending` row on a passed step (a killed run, then resumed) leaves the step limit as it was |
| Degradation | a failed call with tokens unknown leaves its step out of a token history |
| Hostile | a project name shaped like SQL reads nothing; a ledger with no rows gives no totals |
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.infrastructure.llm.store import LlmRepository, step_history_limit
from tests.ledger import Ledger

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database

pytestmark = pytest.mark.integration

_SINCE = datetime(2026, 10, 1, tzinfo=UTC)


def _record(n: int = 0, **overrides: Any) -> dict[str, Any]:
    record = {
        "timestamp": f"2026-10-16T08:{n:02d}:00+00:00",
        "project_name": "greeter",
        "task_type": "implement",
        "model": "coder-a",
        "provider": "openai-compatible",
        "prompt_tokens": 60,
        "completion_tokens": 40,
        "total_tokens": 100,
        "estimated_cost_usd": 0.1,
        "duration_ms": 10,
        "run_id": f"run-{n}",
        "server": "gb10",
        "dal_level": "DAL_C",
        "step_name": "generate_code",
    }
    return record | overrides


async def _call(db: Database, record: dict[str, Any], status: str | None) -> None:
    """One call as the collector writes it: opened `pending`, then closed unless `status` is None."""
    async with db.async_session_scope() as session:
        call_id = await LlmRepository(session).open_call(record)
    if status is not None:
        async with db.async_session_scope() as session:
            await LlmRepository(session).close_call(call_id, record, status)


def _write(db: Database, record: dict[str, Any], status: str | None) -> None:
    asyncio.run(_call(db, record, status))


async def _read(db: Database, query: str, *args: Any) -> Any:
    async with db.async_session_scope() as session:
        return await getattr(LlmRepository(session), query)(*args)


@pytest.fixture
def ledger(tmp_path: Path) -> Ledger:
    """One `ok` call, one billed `failed` call, one call still `pending` with a large worst case."""
    found = Ledger(tmp_path)
    _write(found.db, _record(1), "ok")
    _write(found.db, _record(2, total_tokens=50, estimated_cost_usd=0.2), "failed")
    _write(found.db, _record(3, total_tokens=9000, estimated_cost_usd=5.0), None)
    return found


def test_the_usage_summary_counts_ok_and_failed_never_pending(ledger: Ledger) -> None:
    [row] = asyncio.run(_read(ledger.db, "get_usage_summary", "greeter", _SINCE))

    assert (row["call_count"], row["total_tokens"]) == (2, 150)
    assert row["total_cost"] == pytest.approx(0.3)


def test_spend_by_server_counts_ok_and_failed_never_pending(ledger: Ledger) -> None:
    [row] = asyncio.run(_read(ledger.db, "get_spend_by_server", "greeter", _SINCE))

    assert row["total_cost"] == pytest.approx(0.3)
    assert row["unpriced_calls"] == 0


def test_usage_by_task_type_counts_ok_and_failed_never_pending(ledger: Ledger) -> None:
    [row] = asyncio.run(_read(ledger.db, "get_usage_by_task_type", "greeter"))

    assert (row["call_count"], row["total_tokens"]) == (2, 150)


def test_the_status_totals_name_failed_and_pending_calls_apart(ledger: Ledger) -> None:
    _write(ledger.db, _record(4, total_tokens=0, estimated_cost_usd=None), "failed")

    totals = asyncio.run(_read(ledger.db, "get_status_totals", "greeter", _SINCE))

    assert set(totals) == {"failed", "pending"}
    failed, pending = totals["failed"], totals["pending"]
    assert (failed["calls"], failed["tokens"], failed["unpriced_calls"]) == (2, 50, 1)
    assert failed["cost"] == pytest.approx(0.2)
    assert (pending["calls"], pending["tokens"], pending["unpriced_calls"]) == (1, 9000, 0)
    assert pending["cost"] == pytest.approx(5.0)


def test_status_totals_keep_to_the_project_and_the_month(ledger: Ledger) -> None:
    _write(ledger.db, _record(5, project_name="other"), None)
    _write(ledger.db, _record(6, timestamp="2026-09-30T23:59:00+00:00"), None)

    totals = asyncio.run(_read(ledger.db, "get_status_totals", "greeter", _SINCE))

    assert totals["pending"]["calls"] == 1


@pytest.mark.parametrize("project", ["greeter' OR 1=1 --", ""])
def test_a_project_shaped_like_sql_reads_nothing(ledger: Ledger, project: str) -> None:
    assert asyncio.run(_read(ledger.db, "get_status_totals", project, _SINCE)) == {}


def test_an_empty_ledger_gives_no_totals(tmp_path: Path) -> None:
    assert asyncio.run(_read(Ledger(tmp_path).db, "get_status_totals", "greeter", _SINCE)) == {}


# --- step history (FR-7) ------------------------------------------------------------------------


def _passed(db: Database, runs: range) -> None:
    with db.connect() as conn:
        conn.executemany(
            "INSERT INTO llm_step_outcome (run_id, step_name, outcome) VALUES (?, 'generate_code', 'passed')",
            [(f"run-{n}",) for n in runs],
        )


def _limit(db: Database, unit: str = "tokens") -> float | None:
    return step_history_limit(
        db,
        task_type="implement",
        model="coder-a",
        dal_level="DAL_C",
        unit=unit,
        steps=2,
        percentile=100,
    )


def test_a_pending_row_of_a_resumed_run_never_joins_the_history(tmp_path: Path) -> None:
    db = Ledger(tmp_path).db
    _write(db, _record(1, total_tokens=100), "ok")
    _write(db, _record(2, total_tokens=200), "ok")
    _passed(db, range(1, 3))
    before = (_limit(db), _limit(db, "usd"))

    _write(db, _record(2, total_tokens=90_000, estimated_cost_usd=50.0), None)  # killed, resumed

    assert before == (200, pytest.approx(0.1))
    assert (_limit(db), _limit(db, "usd")) == before


def test_a_billed_failed_call_counts_in_its_steps_history(tmp_path: Path) -> None:
    db = Ledger(tmp_path).db
    _write(db, _record(1, total_tokens=100), "ok")
    _write(db, _record(2, total_tokens=200), "ok")
    _write(db, _record(2, total_tokens=50, estimated_cost_usd=0.2), "failed")
    _passed(db, range(1, 3))

    assert _limit(db) == 250
    assert _limit(db, "usd") == pytest.approx(0.3)


def test_a_failed_call_with_tokens_unknown_leaves_its_step_out_of_a_token_history(
    tmp_path: Path,
) -> None:
    db = Ledger(tmp_path).db
    _write(db, _record(1, total_tokens=100), "ok")
    _write(db, _record(2, total_tokens=200), "ok")
    _write(db, _record(2, total_tokens=0, estimated_cost_usd=None), "failed")
    _passed(db, range(1, 3))

    assert _limit(db) is None
    assert _limit(db, "usd") is None
