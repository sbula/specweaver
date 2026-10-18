# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The shipped list's prices and rules, and the price book that holds one model's prices at a host.

Proves: TECH-074 FR-2, FR-9

| Bucket | Case |
|---|---|
| Happy | the list gives a model its default prices and its special prices with their rules |
| Boundary | the newest price of a kind and rule holds; a price that starts tomorrow does not |
| Degradation | a model on a local server has no prices; a list with no check date holds from always |
| Hostile | a special price of an unknown kind, or with an unknown field, refuses and names the line |
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from specweaver.core.config.llm_settings import ModelFacts, SettingsFileError
from specweaver.infrastructure.llm.catalogue import Catalogue
from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.prices import Price, PriceBook, Rule

_LIST = """\
schema_version = 1
checked = "2026-10-17"

[models."anthropic/claude-opus-5-5"]
usd_per_million_input = 4
usd_per_million_output = 20
usd_per_million_cache_write = 5
specials = [
  { kind = "cache_write", usd_per_million = 8, max_age_seconds = 3600 },
  { kind = "cached_read", usd_per_million = 0.2, min_prefix_tokens = 512, max_age_seconds = 300, requires = "breakpoint" },
]

[models."openai-compatible/qwen3-coder-next"]
context = 262144
"""
_DAY = date(2026, 10, 17)


def _by_kind(prices: list[Price]) -> dict[tuple[str, Rule | None], float]:
    return {(p.kind.value, p.rule): p.usd_per_million for p in prices}


class TestTheListsPrices:
    def test_a_model_has_its_defaults_and_its_special_prices(self) -> None:
        prices = Catalogue.from_text(_LIST).prices("anthropic", "claude-opus-5-5")

        assert _by_kind(prices) == {
            ("input", None): 4.0,
            ("output", None): 20.0,
            ("cache_write", None): 5.0,
            ("cache_write", Rule(max_age_seconds=3600)): 8.0,
            (
                "cached_read",
                Rule(min_prefix_tokens=512, max_age_seconds=300, requires="breakpoint"),
            ): 0.2,
        }
        assert {(p.valid_from, p.source) for p in prices} == {(_DAY, "catalogue")}

    def test_a_local_model_has_no_prices(self) -> None:
        assert Catalogue.from_text(_LIST).prices("openai-compatible", "qwen3-coder-next") == []

    def test_an_unknown_model_has_no_prices(self) -> None:
        assert Catalogue.from_text(_LIST).prices("anthropic", "claude-x") == []

    def test_prices_without_a_check_date_hold_from_always(self) -> None:
        text = _LIST.replace('checked = "2026-10-17"', "")

        prices = Catalogue.from_text(text).prices("anthropic", "claude-opus-5-5")

        assert {p.valid_from for p in prices} == {date.min}

    def test_a_special_price_of_an_unknown_kind_refuses(self) -> None:
        text = _LIST.replace(
            'kind = "cache_write", usd_per_million = 8', 'kind = "free", usd_per_million = 8'
        )

        with pytest.raises(SettingsFileError) as caught:
            Catalogue.from_text(text)

        assert caught.value.key.startswith("anthropic/claude-opus-5-5.specials")

    def test_a_special_price_with_an_unknown_field_refuses(self) -> None:
        text = _LIST.replace("max_age_seconds = 3600", "max_age_secs = 3600")

        with pytest.raises(SettingsFileError):
            Catalogue.from_text(text)


def _p(kind: TokenKind, usd: float, day: date = _DAY, rule: Rule | None = None) -> Price:
    return Price(kind=kind, usd_per_million=usd, valid_from=day, source="catalogue", rule=rule)


_HOUR = Rule(max_age_seconds=3600)
_BOOK = PriceBook(
    (
        _p(TokenKind.INPUT, 5.0, _DAY - timedelta(days=10)),
        _p(TokenKind.INPUT, 4.0),
        _p(TokenKind.INPUT, 1.0, date.today() + timedelta(days=1)),
        _p(TokenKind.OUTPUT, 20.0),
        _p(TokenKind.CACHE_WRITE, 5.0),
        _p(TokenKind.CACHE_WRITE, 8.0, rule=_HOUR),
    ),
    local=False,
)


class TestThePriceBook:
    def test_the_newest_price_holds_and_tomorrows_does_not(self) -> None:
        default = _BOOK.default(TokenKind.INPUT)

        assert default is not None and default.usd_per_million == 4.0

    def test_the_current_prices_of_a_kind_are_its_default_and_its_specials(self) -> None:
        assert sorted(p.usd_per_million for p in _BOOK.current(TokenKind.CACHE_WRITE)) == [5.0, 8.0]

    def test_the_newest_price_holds_in_any_order(self) -> None:
        book = PriceBook((_BOOK.prices[1], _BOOK.prices[0]), local=False)

        default = book.default(TokenKind.INPUT)
        assert default is not None and default.usd_per_million == 4.0

    def test_a_kind_with_no_price_has_no_default(self) -> None:
        assert _BOOK.default(TokenKind.CACHED_READ) is None

    def test_a_settings_price_replaces_every_price_of_its_kind(self) -> None:
        book = _BOOK.with_settings(ModelFacts(usd_per_million_cache_write=6.0))

        assert [
            (p.usd_per_million, p.rule, p.source) for p in book.current(TokenKind.CACHE_WRITE)
        ] == [(6.0, None, "settings")]

    def test_a_settings_price_leaves_the_other_kinds(self) -> None:
        book = _BOOK.with_settings(ModelFacts(usd_per_million_output=25.0))

        input_price = book.default(TokenKind.INPUT)
        assert input_price is not None and input_price.usd_per_million == 4.0

    def test_no_settings_change_nothing(self) -> None:
        assert _BOOK.with_settings(None) == _BOOK

    def test_a_local_book_is_empty(self) -> None:
        assert PriceBook((), local=True).default(TokenKind.INPUT) is None
