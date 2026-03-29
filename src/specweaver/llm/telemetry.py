# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Token & cost telemetry — pure-logic module (no I/O, no DB access).

Provides data models and cost estimation for LLM usage tracking.
The ``TelemetryCollector`` (in ``collector.py``) uses these to build
``UsageRecord`` instances; callers persist them via ``Database.log_usage()``.

Cost defaults last updated: 2026-03-27.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple

from pydantic import BaseModel

from specweaver.llm.models import GenerationConfig, LLMResponse, TaskType, TokenUsage


class CostEntry(NamedTuple):
    """Per-model pricing: cost per 1,000 tokens (USD)."""

    input_cost_per_1k: float
    output_cost_per_1k: float


def get_default_cost_table() -> dict[str, CostEntry]:
    """Get the merged default pricing from all registered LLM adapters."""
    from specweaver.llm.adapters import get_merged_default_costs

    return get_merged_default_costs()


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
    estimated_cost_usd: float = 0.0
    duration_ms: int = 0


def estimate_cost(
    model: str,
    usage: TokenUsage,
    overrides: dict[str, CostEntry] | None = None,
) -> float:
    """Estimate cost in USD for the given token usage.

    Looks up ``model`` in *overrides* first (user-configured), then falls
    back to ``DEFAULT_COST_TABLE``.  Returns ``0.0`` for unknown models.

    Args:
        model: Model identifier (e.g. ``"gemini-3-flash-preview"``).
        usage: Token counts from the LLM response.
        overrides: Optional user-configured cost table (loaded from DB).

    Returns:
        Estimated cost in USD.
    """
    entry: CostEntry | None = None
    if overrides:
        entry = overrides.get(model)
    if entry is None:
        entry = get_default_cost_table().get(model)
    if entry is None:
        return 0.0

    input_cost = (usage.prompt_tokens / 1000) * entry.input_cost_per_1k
    output_cost = (usage.completion_tokens / 1000) * entry.output_cost_per_1k
    return round(input_cost + output_cost, 8)


def create_usage_record(
    config: GenerationConfig,
    response: LLMResponse,
    provider: str,
    project: str,
    duration_ms: int,
    cost_overrides: dict[str, CostEntry] | None = None,
) -> UsageRecord:
    """Build a ``UsageRecord`` from generation config and response.

    Args:
        config: The GenerationConfig used for the call (carries ``task_type``).
        response: The LLMResponse returned by the adapter.
        provider: Provider name (e.g. ``"gemini"``).
        project: Project name for grouping.
        duration_ms: Wall-clock time of the call in milliseconds.
        cost_overrides: Optional user-configured cost overrides.

    Returns:
        A fully populated ``UsageRecord``.
    """
    task_type = config.task_type if config.task_type else TaskType.UNKNOWN
    cost = estimate_cost(response.model, response.usage, cost_overrides)

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
    )
