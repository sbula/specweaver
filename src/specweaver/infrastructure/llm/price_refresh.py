# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Prices from models.dev, refreshed at most once a day for the models the roles use.

models.dev offers only its whole list, `api.json`; it is asked for with the last ETag, so an
unchanged list comes back empty, and only the offerings in use are stored. models.dev gives prices,
never cache rules: a downloaded cached price keeps the shipped list's rule for its kind. A price that
cannot be right — missing, zero, negative, not a number — is refused, and the stored one stays. A
download that fails keeps every price and counts as the day's attempt.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx2
from sqlalchemy import create_engine, insert, select, update

from specweaver.commons.async_bridge import run_sync
from specweaver.core.config.llm_settings import resolve_roles
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.price_store import offering_host, store_downloaded
from specweaver.infrastructure.llm.prices import Price, Rule
from specweaver.infrastructure.llm.store import LlmPriceRefresh

if TYPE_CHECKING:
    from sqlalchemy import Connection

    from specweaver.core.config.llm_settings import LlmSettingsFiles

logger = logging.getLogger(__name__)

_STATE = LlmPriceRefresh.__table__

URL = "https://models.dev/api.json"
#: How long a refresh at the start of a command may wait before the last prices are used.
TIMEOUT_SECONDS = 5
EVERY = timedelta(hours=24)
#: models.dev's provider id for each first-party server kind.
PROVIDER_OF_KIND = {
    "anthropic": "anthropic",
    "openai": "openai",
    "gemini": "google",
    "mistral": "mistral",
    "qwen": "alibaba-cn",
}

#: models.dev's name for each cost field.
_FIELDS = {
    "input": TokenKind.INPUT,
    "output": TokenKind.OUTPUT,
    "cache_read": TokenKind.CACHED_READ,
    "cache_write": TokenKind.CACHE_WRITE,
}
_NEEDED = (TokenKind.INPUT, TokenKind.OUTPUT)
#: A tier table, such as `context_over_200k`: its prices apply from that prompt length on.
_TIER = re.compile(r"context_over_(\d+)k")
SOURCE = "models.dev"


def downloaded_prices(
    entry: dict[str, Any], *, day: date, rules: dict[TokenKind, Rule | None]
) -> tuple[list[Price], list[str]]:
    """The entry's prices from `day`, and why each refused one was refused."""
    cost = entry.get("cost")
    if not isinstance(cost, dict):
        return [], [f"{entry.get('id', '?')}: no cost table"]
    rows, problems = _table(cost, day, rules, tier=None)
    for key, table in cost.items():
        match = _TIER.fullmatch(key)
        if match and isinstance(table, dict):
            tier_rows, tier_problems = _table(table, day, rules, tier=int(match[1]) * 1000)
            rows += tier_rows
            problems += [p for p in tier_problems if "missing" not in p]
    return rows, problems


def shipped_rules(prices: list[Price]) -> dict[TokenKind, Rule | None]:
    """Per kind, the rule of the shipped price a single downloaded one replaces: the untiered one
    with the shortest cache lifetime, as `PriceBook.price_for` picks."""
    rules: dict[TokenKind, Rule | None] = {}
    for kind in TokenKind:
        untiered = [
            p for p in prices if p.kind == kind and not (p.rule and p.rule.min_prompt_tokens)
        ]
        if untiered:
            first = min(untiered, key=lambda p: (p.rule.max_age_seconds or 0) if p.rule else 0)
            rules[kind] = first.rule
    return rules


def _table(
    table: dict[str, Any], day: date, rules: dict[TokenKind, Rule | None], *, tier: int | None
) -> tuple[list[Price], list[str]]:
    rows: list[Price] = []
    problems: list[str] = []
    for name, kind in _FIELDS.items():
        value = table.get(name)
        if value is None:
            if kind in _NEEDED:
                problems.append(f"{name}: missing")
            continue
        if isinstance(value, bool) or not isinstance(value, int | float):
            problems.append(f"{name}: {value!r} is not a price")
        elif not math.isfinite(value) or value <= 0:
            problems.append(f"{name}: {value} is not a price")
        else:
            rows.append(Price(kind, float(value), day, SOURCE, _rule(rules.get(kind), tier)))
    return rows, problems


def _rule(shipped: Rule | None, tier: int | None) -> Rule | None:
    if tier is None:
        return shipped
    base = shipped or Rule()
    return Rule(base.min_prefix_tokens, base.max_age_seconds, tier, base.requires)


@dataclass(frozen=True)
class Offering:
    model: str
    host: str
    kind: str
    provider: str

    @property
    def key(self) -> str:
        return f"{self.provider}/{self.model}@{self.host}"


@dataclass
class Refresh:
    """What a refresh did: whether it asked models.dev, what changed, and what it refused."""

    ran: bool = False
    changes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def refresh_at_start(db: Any, files: LlmSettingsFiles) -> None:
    """The refresh a command that calls a model runs first: at most once a day."""
    refresh_prices(db, files)


def refresh_prices(
    db: Any, files: LlmSettingsFiles, *, force: bool = False, now: datetime | None = None
) -> Refresh:
    """Refresh the prices of the offerings the roles use, if the last attempt is a day old or
    `force`; report each change and each refusal at warning level, so the console shows them."""
    moment = now or datetime.now(UTC)
    offerings = offerings_in_use(files)
    if not offerings:
        return Refresh()
    engine = create_engine("sqlite://", creator=db.connect)
    try:
        with engine.begin() as conn:
            last = conn.execute(
                select(_STATE.c.checked_at, _STATE.c.etag, _STATE.c.offerings).where(
                    _STATE.c.id == 1
                )
            ).first()
            if last and not force and moment - last.checked_at < EVERY:
                return Refresh()
            covered = " ".join(sorted(o.key for o in offerings))
            etag = last.etag if last and last.offerings == covered else None
            result = _download_and_store(conn, offerings, etag, moment.date())
            _record(conn, moment, result.etag if result.etag is not None else etag, covered)
    finally:
        engine.dispose()
    for line in result.refresh.changes:
        logger.warning("Price changed: %s", line)
    for line in result.refresh.problems:
        logger.warning("Price not refreshed: %s", line)
    return result.refresh


def offerings_in_use(files: LlmSettingsFiles) -> list[Offering]:
    """The hosted offerings the roles use that models.dev prices; a local server never."""
    found: dict[str, Offering] = {}
    for setting in resolve_roles(files).values():
        server = files.machine.servers.get(setting.server)
        if server is None or server.private:
            continue
        provider = server.models_dev or PROVIDER_OF_KIND.get(server.kind)
        if provider is None:
            continue
        offering = Offering(
            setting.model, offering_host(setting.server, server), server.kind, provider
        )
        found[offering.key] = offering
    return list(found.values())


@dataclass
class _Outcome:
    refresh: Refresh
    etag: str | None = None


def _download_and_store(
    conn: Connection, offerings: list[Offering], etag: str | None, day: date
) -> _Outcome:
    try:
        status, api, new_etag = run_sync(lambda: _fetch(etag))
    except (httpx2.HTTPError, ValueError) as exc:
        return _Outcome(
            Refresh(ran=True, problems=[f"models.dev unreachable, the last prices stay: {exc}"])
        )
    if status == 304:
        return _Outcome(Refresh(ran=True), etag)
    refresh = Refresh(ran=True)
    for offering in offerings:
        entry = api.get(offering.provider, {}).get("models", {}).get(offering.model)
        if not isinstance(entry, dict):
            refresh.problems.append(
                f"{offering.model}: not in models.dev's {offering.provider} list"
            )
            continue
        rules = shipped_rules(shipped_catalogue().prices(offering.kind, offering.model))
        rows, refused = downloaded_prices(entry, day=day, rules=rules)
        refresh.problems += [f"{offering.model}@{offering.host} {line}" for line in refused]
        changes, problems = store_downloaded(conn, offering.model, offering.host, rows)
        refresh.changes += changes
        refresh.problems += problems
    return _Outcome(refresh, new_etag)


async def _fetch(etag: str | None) -> tuple[int, dict[str, Any], str | None]:
    headers = {"If-None-Match": etag} if etag else {}
    async with httpx2.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.get(URL, headers=headers)
    if response.status_code == 304:
        return 304, {}, etag
    response.raise_for_status()
    body = response.json()
    if not isinstance(body, dict):
        msg = "api.json is not a table of providers"
        raise ValueError(msg)
    return 200, body, response.headers.get("ETag")


def _record(conn: Connection, moment: datetime, etag: str | None, covered: str) -> None:
    values = {"checked_at": moment, "etag": etag, "offerings": covered}
    if conn.execute(select(_STATE.c.id).where(_STATE.c.id == 1)).first():
        conn.execute(update(LlmPriceRefresh).where(_STATE.c.id == 1).values(**values))
    else:
        conn.execute(insert(LlmPriceRefresh).values(id=1, **values))
