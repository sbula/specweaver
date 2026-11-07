# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Column types the SpecWeaver tables share."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.types import String, TypeDecorator


class StrictISODateTime(TypeDecorator[datetime]):
    """A timezone-aware datetime stored as `YYYY-MM-DDTHH:MM:SS.ffffff+00:00`, the format older
    SpecWeaver files hold."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> str | None:
        if value is None:
            return None
        if not isinstance(value, datetime):
            raise TypeError("Value must be a datetime object")
        if value.tzinfo is None:
            raise ValueError("StrictISODateTime must be timezone-aware")
        return value.isoformat()

    def process_result_value(self, value: str | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return datetime.fromisoformat(value)
