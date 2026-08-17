# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one ISO-8601 "now".

This is the L0 leaf where a genuinely cross-cutting helper belongs. One copy remains —
`core/flow/handlers/base._now_iso`, with over twenty importers — and has not been folded in.
"""

from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    """The current UTC time in ISO-8601 format."""
    return datetime.now(UTC).isoformat()
