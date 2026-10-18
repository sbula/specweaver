# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The price store's tables: one row per model at a host, prices that belong to it.

Proves: TECH-074 FR-1

| Bucket | Case |
|---|---|
| Happy | an offering, a default price and a special price with its rule are stored |
| Boundary | one model at two hosts is two offerings |
| Degradation | not applicable — the tables are created, not called |
| Hostile | a second row for one model at one host, and a price for no offering, are refused |
"""

from datetime import date

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from specweaver.infrastructure.llm.store import Base, LlmOffering, LlmPrice, LlmPriceRule


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda conn, _: conn.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _offering(s: Session, model: str = "claude-opus-5-5", host: str = "anthropic") -> LlmOffering:
    row = LlmOffering(model=model, host=host)
    s.add(row)
    s.flush()
    return row


def test_an_offering_holds_a_default_and_a_special_price(session: Session) -> None:
    opus = _offering(session)
    rule = LlmPriceRule(max_age_seconds=3600, requires="nothing")
    session.add(rule)
    session.flush()
    session.add_all(
        [
            LlmPrice(
                offering_id=opus.id,
                token_kind="cache_write",
                usd_per_million=5.0,
                valid_from=date(2026, 10, 17),
                source="catalogue",
            ),
            LlmPrice(
                offering_id=opus.id,
                token_kind="cache_write",
                usd_per_million=8.0,
                valid_from=date(2026, 10, 17),
                source="catalogue",
                rule_id=rule.id,
            ),
        ]
    )
    session.flush()

    rows = session.query(LlmPrice).order_by(LlmPrice.usd_per_million).all()

    assert [(r.usd_per_million, r.rule_id) for r in rows] == [(5.0, None), (8.0, rule.id)]


def test_one_model_at_two_hosts_is_two_offerings(session: Session) -> None:
    _offering(session, "qwen3-coder", "together")
    _offering(session, "qwen3-coder", "fireworks")

    assert session.query(LlmOffering).count() == 2


def test_one_model_at_one_host_is_one_row(session: Session) -> None:
    _offering(session)

    with pytest.raises(IntegrityError):
        _offering(session)


def test_a_price_needs_its_offering(session: Session) -> None:
    session.add(
        LlmPrice(
            offering_id=99,
            token_kind="input",
            usd_per_million=1.0,
            valid_from=date(2026, 10, 17),
            source="catalogue",
        )
    )

    with pytest.raises(IntegrityError):
        session.flush()
