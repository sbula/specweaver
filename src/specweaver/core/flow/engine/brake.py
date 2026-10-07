# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""What the engine reads from the spend brake."""

from __future__ import annotations

from typing import Any

from specweaver.infrastructure.llm.budget import SpendLimitReachedError


def brake_stop(context: Any) -> SpendLimitReachedError | None:
    """The spend brake's stop in this run, if it stopped a call."""
    router = getattr(getattr(context, "model", None), "llm_router", None)
    stopped = getattr(getattr(router, "budget", None), "stopped", None)
    return stopped if isinstance(stopped, SpendLimitReachedError) else None
