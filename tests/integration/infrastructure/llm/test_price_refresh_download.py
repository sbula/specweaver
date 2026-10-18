# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prices follow models.dev: at most one download a day, sent with its ETag, and a failed one changes
nothing.

Proves: TECH-074 FR-7, FR-8, NFR-2

A real SQLite file and the real refresh; only HTTP is faked, with `api.json`-shaped replies.

| Bucket | Case |
|---|---|
| Happy | a store older than a day downloads, stores the changed price, and reports it |
| Boundary | within a day nothing is asked; a forced refresh sends the ETag, and 304 changes nothing; a new model in use sends none |
| Degradation | a timeout or a server error keeps the last prices, warns, and counts as the day's attempt |
| Hostile | a local server is never asked for, even with a `models_dev` name set by mistake; a hosted openai-compatible server is asked for only under its `models_dev` name |
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import httpx2
import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import LlmSettingsFiles
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.price_refresh import refresh_prices
from specweaver.infrastructure.llm.price_store import price_book
from tests.fake_http import fake_httpx2

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration

_OPUS = """\
[servers.anthropic]
kind = "anthropic"
api_key_env = "KEY"
private = false
max_parallel = 1

[roles]
default = "claude-opus-5-5@anthropic"
"""
#: A day back, so a price stored a day after it holds today.
_NOW = datetime.now(UTC) - timedelta(hours=25)


def _api(input_price: float = 4.5) -> dict:
    return {
        "anthropic": {
            "models": {
                "claude-opus-5-5": {
                    "id": "claude-opus-5-5",
                    "cost": {
                        "input": input_price,
                        "output": 20,
                        "cache_read": 0.2,
                        "cache_write": 5,
                    },
                }
            }
        },
        "togetherai": {
            "models": {"qwen3-coder": {"id": "qwen3-coder", "cost": {"input": 0.6, "output": 1.2}}}
        },
    }


def _files(machine: str) -> LlmSettingsFiles:
    return LlmSettingsFiles.from_texts(
        machine_text=machine, machine_source="settings.toml", project_text="", project_source="-"
    )


def _db(tmp_path: Path) -> Database:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path)


def _ok(body: dict, etag: str = '"v1"'):
    return lambda _request: httpx2.Response(200, json=body, headers={"ETag": etag})


def _opus_input(db: Database) -> float:
    server = _files(_OPUS).machine.servers["anthropic"]
    book = price_book(
        db,
        shipped_catalogue(),
        server_name="anthropic",
        server=server,
        model="claude-opus-5-5",
        overrides={},
    )
    price = book.default(TokenKind.INPUT)
    assert price is not None
    return price.usd_per_million


def test_a_stale_store_downloads_stores_and_reports(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _db(tmp_path)

    with caplog.at_level(logging.WARNING), fake_httpx2(_ok(_api())) as seen:
        result = refresh_prices(db, _files(_OPUS), now=_NOW)

    assert len(seen) == 1
    assert result.changes == ["claude-opus-5-5@anthropic input: 4.0 → 4.5 USD per 1M"]
    assert _opus_input(db) == 4.5
    assert any("4.0 → 4.5" in r.getMessage() for r in caplog.records)


def test_within_a_day_nothing_is_asked(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with fake_httpx2(_ok(_api())):
        refresh_prices(db, _files(_OPUS), now=_NOW)

    with fake_httpx2(_ok(_api(9.0))) as seen:
        result = refresh_prices(db, _files(_OPUS), now=_NOW + timedelta(hours=23))

    assert seen == []
    assert not result.ran


def test_a_day_later_it_asks_again(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with fake_httpx2(_ok(_api())):
        refresh_prices(db, _files(_OPUS), now=_NOW)

    with fake_httpx2(_ok(_api(5.0), '"v2"')) as seen:
        refresh_prices(db, _files(_OPUS), now=_NOW + timedelta(hours=25))

    assert len(seen) == 1
    assert _opus_input(db) == 5.0


def test_a_forced_refresh_sends_the_etag_and_304_changes_nothing(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with fake_httpx2(_ok(_api())):
        refresh_prices(db, _files(_OPUS), now=_NOW)

    with fake_httpx2(lambda _request: httpx2.Response(304)) as seen:
        result = refresh_prices(db, _files(_OPUS), now=_NOW, force=True)

    assert seen[0].headers.get("If-None-Match") == '"v1"'
    assert result.changes == []
    assert _opus_input(db) == 4.5


def test_a_new_model_in_use_sends_no_etag(tmp_path: Path) -> None:
    db = _db(tmp_path)
    with fake_httpx2(_ok(_api())):
        refresh_prices(db, _files(_OPUS), now=_NOW)
    more = _OPUS.replace(
        'default = "claude-opus-5-5@anthropic"',
        'default = "claude-opus-5-5@anthropic"\nreview = "claude-sonnet-5@anthropic"',
    )

    with fake_httpx2(_ok(_api())) as seen:
        refresh_prices(db, _files(more), now=_NOW, force=True)

    assert "If-None-Match" not in seen[0].headers


@pytest.mark.parametrize(
    "fail",
    [
        lambda _request: (_ for _ in ()).throw(httpx2.ReadTimeout("slow")),
        lambda _request: httpx2.Response(500),
        lambda _request: httpx2.Response(200, content=b"not json"),
    ],
    ids=["timeout", "server-error", "not-json"],
)
def test_a_failed_download_keeps_the_last_prices_and_counts_as_the_days(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, fail
) -> None:
    db = _db(tmp_path)

    with caplog.at_level(logging.WARNING), fake_httpx2(fail):
        result = refresh_prices(db, _files(_OPUS), now=_NOW)
    with fake_httpx2(_ok(_api())) as later:
        refresh_prices(db, _files(_OPUS), now=_NOW + timedelta(hours=1))

    assert result.problems and result.changes == []
    assert _opus_input(db) == 4.0
    assert any("last prices stay" in r.getMessage() for r in caplog.records)
    assert later == []


def test_a_local_server_is_never_asked_for(tmp_path: Path) -> None:
    local = """\
[servers.gb10]
kind = "openai-compatible"
base_url = "http://gb10:8000/v1"
private = true
max_parallel = 1
models_dev = "togetherai"

[roles]
default = "qwen3-coder@gb10"
"""
    with fake_httpx2(_ok(_api())) as seen:
        result = refresh_prices(_db(tmp_path), _files(local), now=_NOW)

    assert seen == []
    assert not result.ran


@pytest.mark.parametrize(("key", "asked"), [('models_dev = "togetherai"\n', 1), ("", 0)])
def test_a_hosted_openai_compatible_server_needs_its_models_dev_name(
    tmp_path: Path, key: str, asked: int
) -> None:
    hosted = f"""\
[servers.together]
kind = "openai-compatible"
base_url = "https://api.together.xyz/v1"
private = false
max_parallel = 1
{key}
[roles]
default = "qwen3-coder@together"
"""
    with fake_httpx2(_ok(_api())) as seen:
        result = refresh_prices(_db(tmp_path), _files(hosted), now=_NOW)

    assert len(seen) == asked
    if asked:
        assert result.changes == [
            "qwen3-coder@together input: none → 0.6 USD per 1M",
            "qwen3-coder@together output: none → 1.2 USD per 1M",
        ]


_BRAKE = """
[brake]
hosted_spend_per_run = 10
tokens_per_run = 1000000
agent_turns = 5
"""


def _router(db: Database):
    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.infrastructure.llm.router import build_router

    files = LlmSettingsFiles.from_texts(
        machine_text=_OPUS + _BRAKE,
        machine_source="settings.toml",
        project_text="",
        project_source="-",
        keys={"KEY": "test-key-not-real-0123456789"},
    )
    return build_router(files, project="demo", roles=[TaskType.REVIEW], db=db)


@pytest.mark.price_refresh
def test_a_command_that_calls_a_model_refreshes_first(tmp_path: Path) -> None:
    db = _db(tmp_path)

    with fake_httpx2(_ok(_api())) as seen:
        _router(db)

    assert len(seen) == 1
    assert _opus_input(db) == 4.5


def test_the_suite_never_refreshes_unless_a_test_asks(tmp_path: Path) -> None:
    db = _db(tmp_path)

    with fake_httpx2(_ok(_api())) as seen:
        _router(db)

    assert seen == []


def test_the_download_waits_at_most_five_seconds(tmp_path: Path) -> None:
    with fake_httpx2(_ok(_api())) as seen:
        refresh_prices(_db(tmp_path), _files(_OPUS), now=_NOW)

    assert seen[0].extensions["timeout"] == {"connect": 5, "read": 5, "write": 5, "pool": 5}
