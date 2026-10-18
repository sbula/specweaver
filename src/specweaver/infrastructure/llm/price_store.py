# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prices in the database: written from the shipped list at start-up, read back per model and host.

Only the start-up seed (and later the refresh) writes these rows; a price in the settings file is
applied when read, never stored.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from specweaver.infrastructure.llm.catalogue import corrections
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.prices import Price, PriceBook, Rule, check_prices
from specweaver.infrastructure.llm.store import LlmOffering, LlmPrice, LlmPriceRule

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy import Connection

    from specweaver.core.config.llm_settings import ModelFacts, ServerEntry
    from specweaver.infrastructure.llm.catalogue import Catalogue

logger = logging.getLogger(__name__)

_OFFERING = LlmOffering.__table__
_PRICE = LlmPrice.__table__
_RULE = LlmPriceRule.__table__


def offering_host(server_name: str, server: ServerEntry) -> str:
    """Where a model runs, for its price: the provider, or the server itself when it is a host of
    its own (`openai-compatible`)."""
    return server_name if server.kind == "openai-compatible" else server.kind


def seed_prices(conn: Connection, catalogue: Catalogue) -> None:
    """Store each listed price not yet stored. A model whose prices would break the exactly-one
    check gets none of them, and a warning. Idempotent."""
    for key in catalogue.models:
        kind, model = key.split("/", 1)
        listed = catalogue.prices(kind, model)
        if listed:
            _seed_one(conn, model, kind, listed)


def _seed_one(conn: Connection, model: str, host: str, listed: list[Price]) -> None:
    offering = _offering_id(conn, model, host)
    stored = _stored_rows(conn, offering) if offering is not None else []
    new = [price for price in listed if price not in stored]
    if not new:
        return
    problems = check_prices([*stored, *new], local=False)
    if problems:
        logger.warning("Prices of %s@%s not stored: %s", model, host, "; ".join(problems))
        return
    _insert(conn, model, host, offering, new)


def store_downloaded(
    conn: Connection, model: str, host: str, downloaded: list[Price]
) -> tuple[list[str], list[str]]:
    """Store each downloaded price that differs from the one holding today; the changes, old → new,
    and why nothing was stored when the set breaks the exactly-one check.

    Two commands refreshing at once never store a price twice: the database refuses the second,
    and the loser stores nothing.
    """
    offering = _offering_id(conn, model, host)
    stored = _stored_rows(conn, offering) if offering is not None else []
    book = PriceBook(tuple(stored), local=False)
    holding = {(p.kind, p.rule): p for kind in TokenKind for p in book.current(kind)}
    new = [
        price
        for price in downloaded
        if (held := holding.get((price.kind, price.rule))) is None
        or held.usd_per_million != price.usd_per_million
    ]
    if not new:
        return [], []
    problems = check_prices([*stored, *new], local=False)
    if problems:
        return [], problems
    try:
        with conn.begin_nested():
            _insert(conn, model, host, offering, new)
    except IntegrityError:  # expected: another command stored the same prices first
        logger.debug("Prices of %s@%s already stored by another command", model, host)
        return [], []
    return [_change(model, host, holding.get((p.kind, p.rule)), p) for p in new], []


def _change(model: str, host: str, old: Price | None, new: Price) -> str:
    kind = new.kind.value + (" (special)" if new.rule else "")
    before = "none" if old is None else f"{old.usd_per_million}"
    return f"{model}@{host} {kind}: {before} → {new.usd_per_million} USD per 1M"


def _offering_id(conn: Connection, model: str, host: str) -> int | None:
    return conn.execute(
        select(_OFFERING.c.id).where(_OFFERING.c.model == model, _OFFERING.c.host == host)
    ).scalar()


def _insert(
    conn: Connection, model: str, host: str, offering: int | None, new: list[Price]
) -> None:
    if offering is None:
        offering = conn.execute(insert(LlmOffering).values(model=model, host=host)).lastrowid
    for price in new:
        conn.execute(
            insert(LlmPrice).values(
                offering_id=offering,
                token_kind=price.kind.value,
                usd_per_million=price.usd_per_million,
                valid_from=price.valid_from,
                source=price.source,
                rule_id=_rule_id(conn, price.rule),
            )
        )


def price_book(
    db: Any,
    catalogue: Catalogue,
    *,
    server_name: str,
    server: ServerEntry,
    model: str,
    overrides: Mapping[str, ModelFacts],
) -> PriceBook:
    """The model's prices at the server's host, with the settings file's prices over them.

    A local server has no stored prices; a price you set for its model still applies. Without a
    database, or when it cannot be read, the shipped list's prices are used.
    """
    own = corrections(server.kind, model, overrides)
    if server.private:
        return PriceBook((), local=True).with_settings(own)
    stored = _read(db, model, offering_host(server_name, server)) if db is not None else []
    prices = stored or catalogue.prices(server.kind, model)
    return PriceBook(tuple(prices), local=False).with_settings(own)


def _read(db: Any, model: str, host: str) -> list[Price]:
    query = """
    SELECT p.token_kind, p.usd_per_million, p.valid_from, p.source,
           r.min_prefix_tokens, r.max_age_seconds, r.min_prompt_tokens, r.requires, p.rule_id
    FROM llm_price p
    JOIN llm_offering o ON o.id = p.offering_id
    LEFT JOIN llm_price_rule r ON r.id = p.rule_id
    WHERE o.model = ? AND o.host = ?
    """
    try:
        with db.connect() as conn:
            rows = conn.execute(query, (model, host)).fetchall()
    except sqlite3.Error as exc:
        logger.warning("Prices of %s@%s unreadable, using the shipped list: %s", model, host, exc)
        return []
    return [_price(row) for row in rows]


def _price(row: Any) -> Price:
    kind, usd, valid_from, source, prefix, age, prompt, requires, rule_id = row
    rule = None if rule_id is None else Rule(prefix, age, prompt, requires)
    return Price(TokenKind(kind), usd, date.fromisoformat(str(valid_from)), source, rule)


def _stored_rows(conn: Connection, offering: int) -> list[Price]:
    rows = conn.execute(
        select(
            _PRICE.c.token_kind,
            _PRICE.c.usd_per_million,
            _PRICE.c.valid_from,
            _PRICE.c.source,
            _RULE.c.min_prefix_tokens,
            _RULE.c.max_age_seconds,
            _RULE.c.min_prompt_tokens,
            _RULE.c.requires,
            _PRICE.c.rule_id,
        )
        .select_from(_PRICE.outerjoin(_RULE, _RULE.c.id == _PRICE.c.rule_id))
        .where(_PRICE.c.offering_id == offering)
    ).all()
    return [_price(row) for row in rows]


def _rule_id(conn: Connection, rule: Rule | None) -> int | None:
    """The stored rule with these values, stored first if new."""
    if rule is None:
        return None
    values = {
        "min_prefix_tokens": rule.min_prefix_tokens,
        "max_age_seconds": rule.max_age_seconds,
        "min_prompt_tokens": rule.min_prompt_tokens,
        "requires": rule.requires,
    }
    found = conn.execute(
        select(_RULE.c.id).where(
            *(
                _RULE.c[name].is_(value) if value is None else _RULE.c[name] == value
                for name, value in values.items()
            )
        )
    ).scalar()
    return (
        found
        if found is not None
        else conn.execute(insert(LlmPriceRule).values(**values)).lastrowid
    )
