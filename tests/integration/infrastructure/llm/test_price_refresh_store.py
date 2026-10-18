# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Downloaded prices are stored through the one writer: a change is a new row, the rest nothing.

Proves: TECH-074 FR-7, FR-8

A real SQLite file, created and seeded by the same start-up every command runs.

| Bucket | Case |
|---|---|
| Happy | a changed price is stored from today, reported old → new, and read back with its source |
| Boundary | an unchanged price stores nothing; the same download twice stores once |
| Degradation | a set that breaks the exactly-one check stores nothing, and the stored price stays |
| Hostile | a second default for one kind on one day is refused by the database itself |
"""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import create_engine

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.config.llm_settings import ServerEntry
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.price_store import price_book, store_downloaded
from specweaver.infrastructure.llm.prices import Price

if TYPE_CHECKING:
    from pathlib import Path

_TODAY = date.today()
_ANTHROPIC = ServerEntry(
    kind="anthropic", api_key_env="ANTHROPIC_API_KEY", private=False, max_parallel=1
)


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "specweaver.db"
    bootstrap_database(str(path))
    return path


def _store(path: Path, rows: list[Price]) -> tuple[list[str], list[str]]:
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        return store_downloaded(conn, "claude-opus-5-5", "anthropic", rows)


def _input(path: Path) -> Price | None:
    book = price_book(
        Database(path),
        shipped_catalogue(),
        server_name="anthropic",
        server=_ANTHROPIC,
        model="claude-opus-5-5",
        overrides={},
    )
    return book.default(TokenKind.INPUT)


def _count(path: Path) -> int:
    with sqlite3.connect(path) as conn:
        return conn.execute("SELECT COUNT(*) FROM llm_price").fetchone()[0]


def _p(kind: TokenKind, usd: float) -> Price:
    return Price(kind, usd, _TODAY, "models.dev")


def test_a_changed_price_is_stored_and_reported(tmp_path: Path) -> None:
    path = _db(tmp_path)

    changes, problems = _store(path, [_p(TokenKind.INPUT, 4.5), _p(TokenKind.OUTPUT, 20.0)])

    assert problems == []
    assert changes == ["claude-opus-5-5@anthropic input: 4.0 → 4.5 USD per 1M"]
    price = _input(path)
    assert price is not None and (price.usd_per_million, price.source) == (4.5, "models.dev")


def test_an_unchanged_price_stores_nothing(tmp_path: Path) -> None:
    path = _db(tmp_path)
    before = _count(path)

    changes, _ = _store(path, [_p(TokenKind.INPUT, 4.0), _p(TokenKind.OUTPUT, 20.0)])

    assert changes == []
    assert _count(path) == before


def test_the_same_download_twice_stores_once(tmp_path: Path) -> None:
    path = _db(tmp_path)
    _store(path, [_p(TokenKind.INPUT, 4.5)])
    after_first = _count(path)

    changes, _ = _store(path, [_p(TokenKind.INPUT, 4.5)])

    assert changes == []
    assert _count(path) == after_first


def test_a_set_that_breaks_the_check_stores_nothing(tmp_path: Path) -> None:
    path = _db(tmp_path)
    before = _count(path)

    changes, problems = _store(path, [_p(TokenKind.INPUT, 4.5), _p(TokenKind.INPUT, 4.6)])

    assert changes == []
    assert problems and "input" in problems[0]
    assert _count(path) == before
    price = _input(path)
    assert price is not None and price.usd_per_million == 4.0


def test_the_database_refuses_a_second_default_on_one_day(tmp_path: Path) -> None:
    path = _db(tmp_path)

    with sqlite3.connect(path) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO llm_price (offering_id, token_kind, usd_per_million, valid_from, source)"
            " SELECT offering_id, token_kind, 9.0, valid_from, 'x' FROM llm_price"
            " WHERE token_kind = 'input' AND rule_id IS NULL LIMIT 1"
        )
