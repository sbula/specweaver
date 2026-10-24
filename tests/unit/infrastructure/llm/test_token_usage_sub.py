# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The usage of a tool loop's latest rounds: the sum so far less what was already counted.

Proves: TECH-092 FR-4

| Bucket | Case |
|---|---|
| Happy | every count subtracts field by field |
| Boundary | nothing counted yet leaves the sum; the same sum twice leaves nothing |
| Degradation | an unknown cached count stays unknown |
| Hostile | not applicable — both sides are counts the adapters summed |
"""

from __future__ import annotations

from specweaver.infrastructure.llm.models import TokenUsage


def _usage(prompt: int, completion: int, cached: int | None = 0) -> TokenUsage:
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        cached_read_tokens=cached,
        cache_write_tokens=0,
    )


def test_counts_subtract_field_by_field() -> None:
    assert _usage(300, 120, 50) - _usage(100, 20, 10) == _usage(200, 100, 40)


def test_nothing_counted_leaves_the_sum() -> None:
    assert _usage(300, 120) - TokenUsage() == _usage(300, 120)


def test_the_same_sum_twice_leaves_nothing() -> None:
    assert (_usage(300, 120) - _usage(300, 120)).total_tokens == 0


def test_an_unknown_cached_count_stays_unknown() -> None:
    assert (_usage(300, 120, None) - _usage(100, 20, 10)).cached_read_tokens is None
