# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The text of `sw usage`'s *Cached* and cost cells: unknown is never 0, and not applicable is not unknown.

Proves: TECH-074 FR-6, FR-10

| Bucket | Case |
|---|---|
| Happy | a known sum is shown with thousands separators |
| Boundary | a sum with unknown calls says how many |
| Degradation | a group where no call reported a count is unknown |
| Hostile | a local group with no price is n/a; a hosted one with no price stays unknown |
"""

from __future__ import annotations

from specweaver.infrastructure.llm.interfaces.cli import _cached_cell, _usage_cost


def test_a_known_sum_is_shown() -> None:
    assert _cached_cell({"total_cached": 12345, "unknown_cached": 0}) == "12,345"


def test_a_sum_with_unknown_calls_says_how_many() -> None:
    assert _cached_cell({"total_cached": 800, "unknown_cached": 1}) == "800 + 1 unknown"


def test_no_reported_count_is_unknown() -> None:
    assert _cached_cell({"total_cached": None, "unknown_cached": 3}) == "unknown"


def test_a_local_group_with_no_price_is_not_applicable() -> None:
    row = {"total_cost": None, "unpriced_calls": 0, "local_calls": 2}

    assert _usage_cost(row, None) == "n/a"


def test_a_hosted_group_with_no_price_stays_unknown() -> None:
    row = {"total_cost": None, "unpriced_calls": 1, "local_calls": 2}

    assert _usage_cost(row, None) == "unknown"
