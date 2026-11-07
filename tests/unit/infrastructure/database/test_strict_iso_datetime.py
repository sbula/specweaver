# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""A stored datetime is timezone-aware ISO text; anything else is refused before it is written.

| Bucket | Case |
|---|---|
| Happy | an aware datetime is written as ISO text and read back equal |
| Boundary | `None` passes through both ways |
| Hostile | a naive datetime and a string are refused |
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from specweaver.infrastructure.database import StrictISODateTime

_TYPE = StrictISODateTime()
_WHEN = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


def test_an_aware_datetime_round_trips() -> None:
    stored = _TYPE.process_bind_param(_WHEN, None)

    assert stored == "2026-11-07T12:00:00+00:00"
    assert _TYPE.process_result_value(stored, None) == _WHEN


def test_none_passes_through() -> None:
    assert _TYPE.process_bind_param(None, None) is None
    assert _TYPE.process_result_value(None, None) is None


def test_a_naive_datetime_is_refused() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        _TYPE.process_bind_param(datetime(2026, 11, 7), None)


def test_a_string_is_refused() -> None:
    with pytest.raises(TypeError, match="datetime"):
        _TYPE.process_bind_param("2026-11-07", None)  # type: ignore[arg-type]
