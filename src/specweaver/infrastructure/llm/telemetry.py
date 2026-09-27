# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Token & cost telemetry — pure-logic module (no I/O, no DB access).

Provides data models and cost estimation for LLM usage tracking.
The ``TelemetryCollector`` (in ``collector.py``) uses these to build
``UsageRecord`` instances; callers persist them via ``Database.log_usage()``.

"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel

from specweaver.infrastructure.llm.models import GenerationConfig, LLMResponse, TaskType, TokenUsage

if TYPE_CHECKING:
    from specweaver.core.config.llm_settings import ModelFacts

logger = logging.getLogger(__name__)


class UsageRecord(BaseModel):
    """A single LLM usage telemetry record.

    One record per ``generate()`` / ``generate_with_tools()`` /
    ``generate_stream()`` call.  Persisted as one row in
    ``llm_usage_log``.
    """

    timestamp: str
    project_name: str
    task_type: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    duration_ms: int = 0
    run_id: str = ""


def estimate_cost(usage: TokenUsage, facts: ModelFacts | None) -> float | None:
    """The call's cost in USD, or `None` when the model's price is not fully known.

    Prices are USD per 1M tokens, from the catalogue (and the machine file's corrections). Unknown is
    never reported as 0: a free model and an unpriced one are different facts.
    """
    if facts is None:
        return None
    price_in, price_out = facts.usd_per_million_input, facts.usd_per_million_output
    if price_in is None or price_out is None:
        return None
    cost = usage.prompt_tokens * price_in + usage.completion_tokens * price_out
    return round(cost / 1_000_000, 8)


def create_usage_record(
    config: GenerationConfig,
    response: LLMResponse,
    provider: str,
    project: str,
    duration_ms: int,
    facts: ModelFacts | None = None,
) -> UsageRecord:
    """Build a ``UsageRecord`` from generation config and response.

    Args:
        config: The GenerationConfig used for the call (carries ``task_type``).
        response: The LLMResponse returned by the adapter.
        provider: Provider name (e.g. ``"gemini"``).
        project: Project name for grouping.
        duration_ms: Wall-clock time of the call in milliseconds.
        facts: The requested model's catalogue facts, for its price; `None` if unknown.

    Returns:
        A fully populated ``UsageRecord``.
    """
    task_type = config.task_type if config.task_type else TaskType.UNKNOWN
    logger.debug(
        "Creating usage record for %r (model: %r, project: %r)",
        task_type,
        response.model,
        project,
    )
    cost = estimate_cost(response.usage, facts)

    return UsageRecord(
        timestamp=datetime.now(UTC).isoformat(),
        project_name=project,
        task_type=str(task_type),
        model=response.model,
        provider=provider,
        prompt_tokens=response.usage.prompt_tokens,
        completion_tokens=response.usage.completion_tokens,
        total_tokens=response.usage.total_tokens,
        estimated_cost_usd=cost,
        duration_ms=duration_ms,
        run_id=config.run_id,
    )
