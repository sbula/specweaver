# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one ISO-8601 "now".

`TECH-015` moved this out of `core/flow/engine/runner_utils.py`. It was defined **six** times across
the repo as the identical one-liner; this is the L0 leaf where a genuinely cross-cutting helper
belongs, and the flow engine now uses it. The remaining copies — notably
`core/flow/handlers/base._now_iso`, with over twenty importers — are a separate step, as the ticket
requires.
"""

from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    """The current UTC time in ISO-8601 format."""
    return datetime.now(UTC).isoformat()
