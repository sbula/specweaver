# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A `sw usage` cost cell: the configured currency, and unknown never shown as 0.

Proves: C-FLOW-13 FR-12, FR-13
"""

from __future__ import annotations

from datetime import date

from specweaver.core.config.llm_settings import Currency
from specweaver.infrastructure.llm.interfaces.cli import _usage_cost

_CHF = Currency(code="CHF", per_usd=0.8, rate_date=date(2026, 9, 26))


def test_a_known_cost_is_shown_in_the_currency() -> None:
    assert _usage_cost({"total_cost": 1.25, "unpriced_calls": 0}, _CHF) == "CHF 1.0000"


def test_unpriced_calls_are_named_beside_the_known_cost() -> None:
    assert _usage_cost({"total_cost": 1.25, "unpriced_calls": 2}, _CHF) == "CHF 1.0000 + 2 unknown"


def test_only_unpriced_calls_are_unknown_not_zero() -> None:
    assert _usage_cost({"total_cost": None, "unpriced_calls": 3}, None) == "unknown"
