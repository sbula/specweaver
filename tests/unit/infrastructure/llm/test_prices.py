# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The exactly-one check: every call meets exactly one price per token kind.

Proves: TECH-074 FR-1

| Bucket | Case |
|---|---|
| Happy | Opus at Anthropic as rows passes; a later default replaces an earlier one |
| Boundary | a local offering with no rows passes; cached kinds may be left out |
| Degradation | a hosted offering without an input or output default fails; a cached kind that starts before its input fails |
| Hostile | two defaults at one time, two specials with one rule, a rule that sets no condition, an unknown `requires`, a negative price, a price on a local offering |
"""

from datetime import date

import pytest

from specweaver.infrastructure.llm.models import TokenKind
from specweaver.infrastructure.llm.prices import Price, Rule, check_prices

_DAY = date(2026, 10, 17)
_LATER = date(2026, 11, 1)
_HOUR_WRITE = Rule(max_age_seconds=3600)
_CACHED = Rule(min_prefix_tokens=512, max_age_seconds=300, requires="breakpoint")


def _p(kind: TokenKind, usd: float, rule: Rule | None = None, day: date = _DAY) -> Price:
    return Price(kind=kind, usd_per_million=usd, valid_from=day, source="catalogue", rule=rule)


def _opus() -> list[Price]:
    return [
        _p(TokenKind.INPUT, 4.0),
        _p(TokenKind.OUTPUT, 20.0),
        _p(TokenKind.CACHE_WRITE, 5.0),
        _p(TokenKind.CACHE_WRITE, 8.0, _HOUR_WRITE),
        _p(TokenKind.CACHED_READ, 0.2, _CACHED),
    ]


def test_opus_as_rows_passes() -> None:
    assert check_prices(_opus(), local=False) == []


def test_a_later_default_replaces_an_earlier_one() -> None:
    rows = [*_opus(), _p(TokenKind.INPUT, 3.0, day=_LATER)]

    assert check_prices(rows, local=False) == []


def test_a_local_offering_has_no_prices() -> None:
    assert check_prices([], local=True) == []


def test_cached_kinds_may_be_left_out() -> None:
    assert check_prices([_p(TokenKind.INPUT, 1.0), _p(TokenKind.OUTPUT, 2.0)], local=False) == []


@pytest.mark.parametrize("missing", [TokenKind.INPUT, TokenKind.OUTPUT])
def test_a_hosted_offering_needs_an_input_and_an_output_default(missing: TokenKind) -> None:
    rows = [p for p in _opus() if p.kind != missing]

    problems = check_prices(rows, local=False)

    assert len(problems) == 1
    assert missing.value in problems[0]


def test_a_hosted_offering_with_no_rows_fails() -> None:
    assert len(check_prices([], local=False)) == 2


def test_a_cached_price_cannot_start_before_its_input() -> None:
    rows = [
        _p(TokenKind.INPUT, 4.0, day=_LATER),
        _p(TokenKind.OUTPUT, 20.0, day=_LATER),
        _p(TokenKind.CACHE_WRITE, 5.0),
    ]

    problems = check_prices(rows, local=False)

    assert any("2026-10-17" in p and "input" in p for p in problems)


def test_two_defaults_at_one_time_fail() -> None:
    problems = check_prices([*_opus(), _p(TokenKind.INPUT, 4.5)], local=False)

    assert len(problems) == 1
    assert "input" in problems[0]


def test_two_defaults_at_different_times_pass() -> None:
    assert check_prices([*_opus(), _p(TokenKind.OUTPUT, 25.0, day=_LATER)], local=False) == []


def test_two_specials_with_one_rule_fail() -> None:
    problems = check_prices([*_opus(), _p(TokenKind.CACHE_WRITE, 9.0, _HOUR_WRITE)], local=False)

    assert len(problems) == 1
    assert "cache_write" in problems[0]


def test_one_rule_on_two_kinds_passes() -> None:
    rows = [*_opus(), _p(TokenKind.INPUT, 6.0, _HOUR_WRITE)]

    assert check_prices(rows, local=False) == []


def test_a_rule_that_sets_no_condition_fails() -> None:
    problems = check_prices([*_opus(), _p(TokenKind.OUTPUT, 30.0, Rule())], local=False)

    assert len(problems) == 1
    assert "condition" in problems[0]


def test_an_unknown_requirement_fails() -> None:
    problems = check_prices(
        [*_opus(), _p(TokenKind.OUTPUT, 30.0, Rule(requires="'; DROP TABLE llm_price"))],
        local=False,
    )

    assert len(problems) == 1
    assert "requires" in problems[0]


def test_a_negative_price_fails() -> None:
    rows = [p for p in _opus() if p.kind != TokenKind.OUTPUT] + [_p(TokenKind.OUTPUT, -1.0)]

    problems = check_prices(rows, local=False)

    assert len(problems) == 1
    assert "negative" in problems[0]


def test_a_local_offering_with_a_price_fails() -> None:
    problems = check_prices([_p(TokenKind.INPUT, 0.0)], local=True)

    assert len(problems) == 1
    assert "local" in problems[0]


@pytest.mark.parametrize("usd", [float("nan"), float("inf")])
def test_a_price_that_is_not_a_number_fails(usd: float) -> None:
    rows = [p for p in _opus() if p.kind != TokenKind.OUTPUT] + [_p(TokenKind.OUTPUT, usd)]

    assert len(check_prices(rows, local=False)) == 1
