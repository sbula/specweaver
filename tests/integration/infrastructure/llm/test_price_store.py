# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The shipped list's prices reach the database at start-up, and a model's prices are read back.

Proves: TECH-074 FR-1, FR-2, FR-9, NFR-2, NFR-3

A real SQLite file, created by the same start-up every command runs.

| Bucket | Case |
|---|---|
| Happy | after start-up Opus reads 4 / 20, cache writes 5 and 8, cached reads 0.20 with its rule |
| Boundary | a second start-up writes nothing; a newer list adds its prices and keeps the old ones |
| Degradation | without a database, or with a broken one, the shipped list's prices are used and logged |
| Hostile | a list that breaks the exactly-one check writes nothing and warns; a settings price, hosted or local, is never written |
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

from sqlalchemy import create_engine

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import ModelFacts, ServerEntry
from specweaver.infrastructure.llm.catalogue import Catalogue, shipped_catalogue
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.price_store import offering_host, price_book, seed_prices
from specweaver.infrastructure.llm.prices import Rule
from specweaver.infrastructure.llm.store import Base

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

_ANTHROPIC = ServerEntry(
    kind="anthropic", api_key_env="ANTHROPIC_API_KEY", private=False, max_parallel=1
)
_GB10 = ServerEntry(
    kind="openai-compatible", base_url="http://gb10:8000/v1", private=True, max_parallel=1
)


def _started(tmp_path: Path) -> Database:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return Database(path)


def _count(db: Database, where: str = "1") -> int:
    with db.connect() as conn:
        return conn.execute(f"SELECT COUNT(*) FROM llm_price WHERE {where}").fetchone()[0]


def _opus(db: Database | None, overrides: dict[str, ModelFacts] | None = None):
    return price_book(
        db,
        shipped_catalogue(),
        server_name="anthropic",
        server=_ANTHROPIC,
        model="claude-opus-5-5",
        overrides=overrides or {},
    )


def test_opus_reads_its_prices_after_start_up(tmp_path: Path) -> None:
    book = _opus(_started(tmp_path))

    defaults = {k: book.default(k) for k in TokenKind}
    assert {k.value: p.usd_per_million for k, p in defaults.items() if p} == {
        "input": 4.0,
        "output": 20.0,
        "cache_write": 5.0,
    }
    assert sorted(p.usd_per_million for p in book.current(TokenKind.CACHE_WRITE)) == [5.0, 8.0]
    [cached] = book.current(TokenKind.CACHED_READ)
    assert (cached.usd_per_million, cached.rule) == (
        0.2,
        Rule(min_prefix_tokens=512, max_age_seconds=300, requires="breakpoint"),
    )


def test_a_second_start_up_writes_nothing_and_says_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    db = _started(tmp_path)
    before = _count(db)

    with caplog.at_level(logging.WARNING):
        bootstrap_database(str(tmp_path / "specweaver.db"))

    assert before > 0
    assert _count(db) == before
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_a_settings_price_wins_and_is_never_written(tmp_path: Path) -> None:
    db = _started(tmp_path)

    book = _opus(db, {"claude-opus-5-5": ModelFacts(usd_per_million_input=3.0)})

    price = book.default(TokenKind.INPUT)
    assert price is not None and (price.usd_per_million, price.source) == (3.0, "settings")
    assert _count(db, "source != 'catalogue'") == 0


def test_a_newer_list_adds_its_prices_and_keeps_the_old(tmp_path: Path) -> None:
    db = _started(tmp_path)
    before = _count(db)
    newer = Catalogue.from_text(
        'schema_version = 1\nchecked = "2026-10-18"\n'
        '[models."anthropic/claude-opus-5-5"]\nusd_per_million_input = 3.5\n'
        "usd_per_million_output = 20\n"
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'specweaver.db'}")

    with engine.begin() as conn:
        seed_prices(conn, newer)

    assert _count(db) == before + 2
    price = _opus(db).default(TokenKind.INPUT)
    assert price is not None and price.usd_per_million == 3.5


def test_a_list_that_breaks_the_check_writes_nothing_and_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'bad.db'}")
    Base.metadata.create_all(engine)
    bad = Catalogue.from_text(
        'schema_version = 1\nchecked = "2026-10-17"\n'
        '[models."openai/gpt-x"]\nusd_per_million_input = 1\n'
    )

    with (
        caplog.at_level(logging.WARNING, logger="specweaver.infrastructure.llm.price_store"),
        engine.begin() as conn,
    ):
        seed_prices(conn, bad)

    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM llm_price").scalar() == 0
    assert any("gpt-x" in r.getMessage() and "output" in r.getMessage() for r in caplog.records)


def test_without_a_database_the_shipped_prices_are_used() -> None:
    price = _opus(None).default(TokenKind.INPUT)

    assert price is not None and price.usd_per_million == 4.0


def test_a_broken_database_falls_back_to_the_shipped_prices_and_logs(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    sqlite3.connect(tmp_path / "empty.db").close()

    with caplog.at_level(logging.WARNING, logger="specweaver.infrastructure.llm.price_store"):
        price = _opus(Database(tmp_path / "empty.db")).default(TokenKind.INPUT)

    assert price is not None and price.usd_per_million == 4.0
    assert any("shipped" in r.getMessage() for r in caplog.records)


def test_a_local_server_has_no_prices(tmp_path: Path) -> None:
    book = price_book(
        _started(tmp_path),
        shipped_catalogue(),
        server_name="gb10",
        server=_GB10,
        model="qwen3-coder-next",
        overrides={},
    )

    assert book.local
    assert all(book.default(k) is None for k in TokenKind)


def test_a_price_you_set_for_a_local_model_still_applies(tmp_path: Path) -> None:
    db = _started(tmp_path)

    book = price_book(
        db,
        shipped_catalogue(),
        server_name="gb10",
        server=_GB10,
        model="qwen3-coder-next",
        overrides={"qwen3-coder-next": ModelFacts(usd_per_million_input=0.1)},
    )

    price = book.default(TokenKind.INPUT)
    assert price is not None and price.usd_per_million == 0.1
    assert _count(db, "source = 'settings'") == 0


def test_a_hosted_openai_compatible_server_is_its_own_host() -> None:
    together = ServerEntry(
        kind="openai-compatible",
        base_url="https://api.together.xyz/v1",
        private=False,
        max_parallel=1,
    )

    assert offering_host("together", together) == "together"
    assert offering_host("my-anthropic", _ANTHROPIC) == "anthropic"


def test_prices_stored_for_one_host_never_price_another(tmp_path: Path) -> None:
    db = _started(tmp_path)
    together = ServerEntry(
        kind="openai-compatible",
        base_url="https://api.together.xyz/v1",
        private=False,
        max_parallel=1,
    )

    book = price_book(
        db,
        shipped_catalogue(),
        server_name="together",
        server=together,
        model="claude-opus-5-5",
        overrides={},
    )

    assert all(book.default(k) is None for k in TokenKind)
