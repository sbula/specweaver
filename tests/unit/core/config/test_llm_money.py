# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One currency: every amount is shown and taken in it; USD stays the stored unit.

Proves: C-FLOW-13 FR-13

| Bucket | Case |
|---|---|
| Happy | USD shown in the configured currency at its rate; an amount given in it stored as USD |
| Boundary | no `[currency]` → USD, unconverted |
| Degradation | an unknown amount shows as unknown, never as 0 |
| Hostile | not applicable — the rate is validated where the file is parsed (> 0) |
"""

from __future__ import annotations

from datetime import date

import pytest

from specweaver.core.config.llm_settings import Currency, format_money, to_usd

_CHF = Currency(code="CHF", per_usd=0.8, rate_date=date(2026, 9, 26))


def test_usd_is_shown_in_the_configured_currency() -> None:
    assert format_money(1.25, _CHF) == "CHF 1.00"


def test_without_a_currency_usd_is_shown() -> None:
    assert format_money(1.25, None) == "USD 1.25"


def test_an_unknown_amount_is_shown_as_unknown() -> None:
    assert format_money(None, _CHF) == "unknown"


def test_small_prices_keep_their_digits() -> None:
    assert format_money(0.11875, _CHF, places=4) == "CHF 0.0950"


def test_an_amount_in_the_configured_currency_is_stored_as_usd() -> None:
    assert to_usd(4.0, _CHF) == pytest.approx(5.0)
    assert to_usd(4.0, None) == 4.0
