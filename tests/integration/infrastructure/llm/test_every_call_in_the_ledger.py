# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Every request is in the cost ledger from the moment it is sent, whatever happens next.

Proves: C-FLOW-01 FR-1
Proves: C-FLOW-01 FR-2
Proves: C-FLOW-01 FR-3
Proves: C-FLOW-01 FR-4
Proves: C-FLOW-01 FR-5
Proves: C-FLOW-01 NFR-2
Proves: C-FLOW-01 NFR-3

A real collector over a real SQLite ledger; the provider double reads the ledger while the call
is still running.

| Bucket | Case |
|---|---|
| Happy | a call is `pending` while it runs and `ok` with its real numbers after; a stream likewise |
| Boundary | a tool loop's `pending` row grows with each round's worst case; a call the brake refuses leaves no row |
| Degradation | a ledger that cannot be written: the call still returns, and the miss is counted once per call |
| Boundary (NFR) | an unpriced call's cost stays unknown, never 0; a row from years ago is still there |
| Hostile (NFR) | no row holds a word of the prompt or the answer |
| Hostile | a call that raises is `failed` with the usage it reported, else with tokens unknown; nothing writes rows but the collector |
"""

from __future__ import annotations

import asyncio
import sqlite3
from typing import TYPE_CHECKING, Any

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.infrastructure.llm.budget import SpendBudget
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import (
    GenerationConfig,
    LLMResponse,
    Message,
    Role,
    TokenUsage,
)
from specweaver.infrastructure.llm.store import LlmRepository

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_CONFIG = GenerationConfig(
    model="coder-a", max_output_tokens=1000, run_id="r1", step_name="generate_code"
)
_ASK = [Message(role=Role.USER, content="hello " * 40)]


class _Provider:
    """A provider that looks at the ledger while it answers."""

    provider_name = "openai-compatible"

    def __init__(self, ledger: Path, *, fail: BaseException | None = None) -> None:
        self.ledger = ledger
        self.fail = fail
        self.seen: list[list[tuple[Any, ...]]] = []

    def available(self) -> bool:
        return True

    def _look(self) -> None:
        with sqlite3.connect(self.ledger) as conn:
            self.seen.append(
                conn.execute("SELECT call_status, total_tokens FROM llm_usage_log").fetchall()
            )

    def _answer(self) -> LLMResponse:
        self._look()
        if self.fail is not None:
            raise self.fail
        return LLMResponse(
            text="hi",
            model="coder-a",
            usage=TokenUsage(prompt_tokens=300, completion_tokens=120, total_tokens=420),
        )

    async def generate(self, messages: Any, config: Any) -> LLMResponse:
        return self._answer()

    async def generate_with_tools(
        self,
        messages: Any,
        config: Any,
        tools: Any,
        on_tool_round: Any = None,
        before_request: Any = None,
    ) -> LLMResponse:
        self._look()
        before_request(1, 40_000)  # a second round with a much longer prompt
        await asyncio.sleep(0.05)  # let the ledger hear about it
        return self._answer()

    async def generate_stream(self, messages: Any, config: Any) -> Any:
        self._look()
        yield "h"
        yield "i"


@pytest.fixture
def ledger(tmp_path: Path) -> tuple[Database, Path]:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path), path


def _collector(
    db: Any, provider: _Provider, budget: SpendBudget | None = None
) -> TelemetryCollector:
    return TelemetryCollector(provider, "greeter", budget=budget, ledger=db, server="gb10")


def _rows(path: Path) -> list[tuple[Any, ...]]:
    with sqlite3.connect(path) as conn:
        return conn.execute(
            "SELECT call_status, prompt_tokens, completion_tokens, project_name, run_id, step_name"
            " FROM llm_usage_log"
        ).fetchall()


def test_a_call_is_pending_while_it_runs_then_ok(ledger: tuple[Database, Path]) -> None:
    db, path = ledger
    provider = _Provider(path)

    asyncio.run(_collector(db, provider).generate(_ASK, _CONFIG))

    assert [status for status, _ in provider.seen[0]] == ["pending"]
    assert _rows(path) == [("ok", 300, 120, "greeter", "r1", "generate_code")]


def test_a_stream_is_pending_until_it_ends(ledger: tuple[Database, Path]) -> None:
    db, path = ledger
    provider = _Provider(path)

    async def _drain() -> str:
        return "".join([c async for c in _collector(db, provider).generate_stream(_ASK, _CONFIG)])

    assert asyncio.run(_drain()) == "hi"
    assert [status for status, _ in provider.seen[0]] == ["pending"]
    assert [row[0] for row in _rows(path)] == ["ok"]


def test_a_tool_loops_pending_row_grows_round_by_round(ledger: tuple[Database, Path]) -> None:
    db, path = ledger
    provider = _Provider(path)

    asyncio.run(_collector(db, provider).generate_with_tools(_ASK, _CONFIG, tool_executor=object()))

    first, later = provider.seen[0], provider.seen[1]
    assert first[0][0] == "pending" and later[0][0] == "pending"
    assert later[0][1] > first[0][1]
    assert [row[0] for row in _rows(path)] == ["ok"]


def test_a_call_the_brake_refuses_leaves_no_row(ledger: tuple[Database, Path]) -> None:
    db, path = ledger

    class _Refusing(SpendBudget):
        def before_call(self, scope: Any, worst: Any) -> Any:
            raise RuntimeError("limit reached")

    with pytest.raises(RuntimeError, match="limit"):
        asyncio.run(_collector(db, _Provider(path), _Refusing()).generate(_ASK, _CONFIG))

    assert _rows(path) == []


def test_a_ledger_that_cannot_be_written_never_stops_the_call(tmp_path: Path) -> None:
    class _Broken:
        def async_session_scope(self) -> Any:
            raise OSError("disk full")

    collector = _collector(_Broken(), _Provider(tmp_path / "none.db"))
    provider_path = tmp_path / "none.db"
    sqlite3.connect(provider_path).execute(
        "CREATE TABLE llm_usage_log (call_status TEXT, total_tokens INT)"
    ).connection.commit()

    response = asyncio.run(collector.generate(_ASK, _CONFIG))

    assert response.text == "hi"
    assert collector.unwritten == 1


class _BilledError(Exception):
    usage = TokenUsage(prompt_tokens=300, completion_tokens=7, total_tokens=307)


@pytest.mark.parametrize(
    ("error", "tokens"),
    [(_BilledError("cut off"), (300, 7)), (TimeoutError("no answer"), (0, 0))],
    ids=["reported-usage", "tokens-unknown"],
)
def test_a_call_that_raises_is_failed(
    ledger: tuple[Database, Path], error: Exception, tokens: tuple[int, int]
) -> None:
    db, path = ledger

    with pytest.raises(type(error)):
        asyncio.run(_collector(db, _Provider(path, fail=error)).generate(_ASK, _CONFIG))

    assert _rows(path) == [("failed", *tokens, "greeter", "r1", "generate_code")]


def _refuse(monkeypatch: pytest.MonkeyPatch, write: str) -> None:
    async def _refused(*_args: Any) -> Any:
        raise OSError("disk full")

    monkeypatch.setattr(LlmRepository, write, _refused)


@pytest.mark.parametrize(
    ("write", "missing", "left"),
    [("open_call", 1, []), ("close_call", 1, ["pending"]), ("widen_call", 0, ["ok"])],
    ids=["never-opened", "never-closed", "not-widened"],
)
def test_a_call_counts_as_missing_only_when_its_row_is_missing_or_never_closed(
    ledger: tuple[Database, Path],
    monkeypatch: pytest.MonkeyPatch,
    write: str,
    missing: int,
    left: list[str],
) -> None:
    db, path = ledger
    _refuse(monkeypatch, write)
    collector = _collector(db, _Provider(path))

    asyncio.run(collector.generate_with_tools(_ASK, _CONFIG, tool_executor=object()))

    assert collector.unwritten == missing
    assert [row[0] for row in _rows(path)] == left


def test_a_row_gone_before_its_call_ends_counts_as_missing(
    ledger: tuple[Database, Path],
) -> None:
    db, path = ledger

    class _Deleting(_Provider):
        def _answer(self) -> LLMResponse:
            with sqlite3.connect(self.ledger) as conn:
                conn.execute("DELETE FROM llm_usage_log")
            return super()._answer()

    collector = _collector(db, _Deleting(path))
    asyncio.run(collector.generate(_ASK, _CONFIG))

    assert collector.unwritten == 1


def test_a_call_whose_open_and_close_both_fail_counts_once(
    ledger: tuple[Database, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    db, path = ledger
    _refuse(monkeypatch, "open_call")
    _refuse(monkeypatch, "close_call")
    collector = _collector(db, _Provider(path))

    asyncio.run(collector.generate(_ASK, _CONFIG))

    assert collector.unwritten == 1


def test_an_unpriced_calls_cost_stays_unknown(ledger: tuple[Database, Path]) -> None:
    db, path = ledger

    asyncio.run(_collector(db, _Provider(path)).generate(_ASK, _CONFIG))

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT estimated_cost FROM llm_usage_log").fetchall() == [(None,)]


def test_no_row_holds_the_prompt_or_the_answer(ledger: tuple[Database, Path]) -> None:
    db, path = ledger
    secret = [Message(role=Role.USER, content="the-launch-code-is-4711 " * 20)]

    asyncio.run(_collector(db, _Provider(path)).generate(secret, _CONFIG))

    with sqlite3.connect(path) as conn:
        cells = [str(cell) for row in conn.execute("SELECT * FROM llm_usage_log") for cell in row]
    assert cells
    assert not any("launch-code" in cell or cell == "hi" for cell in cells)


def test_a_row_from_years_ago_is_kept(ledger: tuple[Database, Path]) -> None:
    db, path = ledger
    with sqlite3.connect(path) as conn:
        conn.execute(
            "INSERT INTO llm_usage_log (timestamp, project_name, task_type, model, provider,"
            " prompt_tokens, completion_tokens, total_tokens, duration_ms)"
            " VALUES ('2020-01-01T00:00:00+00:00', 'greeter', 'draft', 'old', 'x', 1, 1, 2, 1)"
        )

    bootstrap_database(str(path))
    asyncio.run(_collector(db, _Provider(path)).generate(_ASK, _CONFIG))

    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT model FROM llm_usage_log ORDER BY id").fetchall() == [
            ("old",),
            ("coder-a",),
        ]


def test_only_the_collector_writes_rows() -> None:
    from specweaver.infrastructure.llm import collector

    assert not hasattr(collector.TelemetryCollector, "flush")
    assert not hasattr(collector.TelemetryCollector, "flush_async")


_SETTINGS = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 2

[roles]
default = { model = "coder-a@gb10", max_output_tokens = 1000 }

[brake]
hosted_spend_per_run = 1000
tokens_per_run = 100000000
agent_turns = 5
"""


def test_a_commands_router_writes_every_call_to_its_ledger(
    ledger: tuple[Database, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one path every command and REST endpoint builds its models through (`build_router`)."""
    from specweaver.core.config.llm_settings import LlmSettingsFiles
    from specweaver.infrastructure.llm import resolve
    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.infrastructure.llm.router import build_router

    db, path = ledger
    monkeypatch.setattr(resolve, "adapter_for_server", lambda *_a: _Provider(path))
    files = LlmSettingsFiles.from_texts(
        machine_text=_SETTINGS, machine_source="settings.toml", project_text="", project_source=""
    )
    router = build_router(files, project="greeter", roles=[TaskType.IMPLEMENT], db=db)

    adapter, config = router.get_for_task(TaskType.IMPLEMENT)
    asyncio.run(adapter.generate(_ASK, config))

    assert [(row[0], row[3]) for row in _rows(path)] == [("ok", "greeter")]
    assert router.unwritten() == 0
