# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A cache hit long after its prompt start was last sent warns once: the provider may keep caches
longer than the shipped rule says.

Proves: C-FLOW-14 FR-4

Settings file → `build_router` with a real SQLite database → the real Anthropic adapter → its
collector; only HTTP is faked. Claude Opus 5.5's cached reads live 300 s, so a hit warns only more
than 600 s after the start was last sent.

| Bucket | Case |
|---|---|
| Happy | a hit 20 minutes after the last send warns, also from a new process |
| Boundary | a hit 8 minutes after says nothing; each send renews the time; three late hits warn once; text after the run clock is not part of the start |
| Degradation | a start never sent before says nothing |
| Hostile | the table holds no word of the prompt; a start unsent for 7 days is deleted |
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.infrastructure.llm.models import Message, Role, TaskType
from specweaver.infrastructure.llm.router import build_router
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_MACHINE = """\
[servers.anthropic]
kind = "anthropic"
api_key_env = "ANTHROPIC_API_KEY"
private = false
max_parallel = 1

[roles]
default = { model = "claude-opus-5-5@anthropic", max_output_tokens = 100 }

[brake]
hosted_spend_per_run = 100
tokens_per_run = 10000000
agent_turns = 5
"""
_START = "Review the spec. Always be honest. " * 30


def _reply(cached: int) -> dict:
    return {
        "id": "m1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 1,
            "cache_read_input_tokens": cached,
            "cache_creation_input_tokens": 0,
        },
    }


def _db(tmp_path: Path) -> Database:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path)


def _router(db: Database):
    files = LlmSettingsFiles.from_texts(
        machine_text=_MACHINE,
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys={"ANTHROPIC_API_KEY": "test-key-not-real-0123456789"},
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW], db=db).get_for_task(
        TaskType.REVIEW
    )


async def _call(routed, cached: int, clock: str = "first", start: str = _START) -> None:
    prompt = [Message(role=Role.USER, content=f"{start}<run_clock>\n{clock}\n</run_clock>")]
    with fake_httpx2(lambda _request: httpx2.Response(200, json=_reply(cached))):
        await routed.adapter.generate(prompt, routed.config)


def _age(db: Database, seconds: float) -> None:
    then = (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat()
    with sqlite3.connect(db._db_path) as conn:
        conn.execute("UPDATE llm_prompt_start SET last_sent = ?", (then,))


def _late(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "lifetime" in r.getMessage()]


async def test_a_hit_long_after_the_last_send_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db(tmp_path)
    routed = _router(db)
    await _call(routed, cached=0)
    _age(db, 20 * 60)

    with caplog.at_level(logging.WARNING):
        await _call(routed, cached=2000, clock="second")

    [warning] = _late(caplog)
    assert "claude-opus-5-5" in warning and "300" in warning


async def test_a_new_process_remembers_the_last_send(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db(tmp_path)
    await _call(_router(db), cached=0)
    _age(db, 20 * 60)

    with caplog.at_level(logging.WARNING):
        await _call(_router(db), cached=2000, clock="second")

    assert len(_late(caplog)) == 1


async def test_a_hit_within_twice_the_lifetime_says_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db(tmp_path)
    routed = _router(db)
    await _call(routed, cached=0)
    _age(db, 8 * 60)

    with caplog.at_level(logging.WARNING):
        await _call(routed, cached=2000)

    assert _late(caplog) == []


async def test_three_late_hits_warn_once(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    db = _db(tmp_path)
    routed = _router(db)
    await _call(routed, cached=0)

    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            _age(db, 20 * 60)
            await _call(routed, cached=2000)

    assert len(_late(caplog)) == 1


async def test_a_start_never_sent_before_says_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db(tmp_path)
    routed = _router(db)
    await _call(routed, cached=0)
    _age(db, 20 * 60)

    with caplog.at_level(logging.WARNING):
        await _call(routed, cached=2000, start="Another step entirely. " * 30)

    assert _late(caplog) == []


async def test_the_run_clock_is_not_part_of_the_start(tmp_path: Path) -> None:
    db = _db(tmp_path)
    routed = _router(db)

    await _call(routed, cached=0, clock="09:01")
    await _call(routed, cached=0, clock="09:07")

    with sqlite3.connect(db._db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM llm_prompt_start").fetchone()[0] == 1


async def test_the_table_holds_no_word_of_the_prompt(tmp_path: Path) -> None:
    db = _db(tmp_path)
    await _call(_router(db), cached=0)

    with sqlite3.connect(db._db_path) as conn:
        rows = conn.execute("SELECT * FROM llm_prompt_start").fetchall()

    assert rows
    assert all(
        "Review" not in str(value) and "honest" not in str(value) for row in rows for value in row
    )


async def test_a_start_unsent_for_seven_days_is_deleted(tmp_path: Path) -> None:
    db = _db(tmp_path)
    routed = _router(db)
    await _call(routed, cached=0)
    _age(db, 8 * 24 * 3600)

    await _call(routed, cached=0, start="Another step entirely. " * 30)

    with sqlite3.connect(db._db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM llm_prompt_start").fetchone()[0] == 1


async def test_each_send_renews_the_last_send(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db(tmp_path)
    routed = _router(db)
    await _call(routed, cached=0)
    _age(db, 20 * 60)
    await _call(routed, cached=0, clock="second")

    with caplog.at_level(logging.WARNING):
        await _call(routed, cached=2000, clock="third")

    assert _late(caplog) == []
