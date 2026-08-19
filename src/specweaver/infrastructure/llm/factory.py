# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""LLM adapter factory — create and validate an LLM adapter from project settings.

Extracted from ``cli/_helpers.py`` so that both the CLI and the REST API
can obtain a ready-to-use adapter without depending on Typer/Rich.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

# Re-exported, not defined: it lives in `errors.py`, a leaf, so `_rate_limit` can raise it without
# importing `factory` back. Eleven files import it from here, so the name keeps resolving — new
# code should import from `errors`.
from specweaver.infrastructure.llm.errors import LLMAdapterError as LLMAdapterError

if TYPE_CHECKING:
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.models import GenerationConfig

logger = logging.getLogger(__name__)


def _get_adapter_class(provider: str) -> Any:
    """Return the adapter class for the given provider name."""
    from specweaver.infrastructure.llm.adapters.registry import get_adapter_class, get_all_adapters

    try:
        return get_adapter_class(provider)
    except ValueError as e:
        raise LLMAdapterError(
            f"Unsupported LLM provider: '{provider}'. Available: {list(get_all_adapters().keys())}"
        ) from e


def build_adapter_for_project(db: Any, settings: Any, project: str) -> tuple[Any, Any]:
    """A telemetry-attributed adapter for `project`, priced from the user's own rates.

    One call site for `sw implement` and both `sw review` paths. As copies they each have to
    remember `cost_overrides`, and a copy that forgets prices the run from the built-in table — or
    at `0.0` for a model absent from it — while `sw costs` still echoes back the rate the user set.

    Deliberately narrow. Two things that looked shareable are not, and `tach` said so rather than
    a reviewer: loading settings would drag `core.config.bootstrap` into `llm`, and turning
    `LLMAdapterError` / `ValueError` into a message and an exit code is presentation. Both stay at
    the call site. What is left is the part that was actually wrong everywhere.
    """
    return create_llm_adapter(
        settings,
        telemetry_project=project,
        cost_overrides=load_cost_overrides(db),
    )[:2]


def load_cost_overrides(db: Any) -> dict[str, tuple[float, float]]:
    """User-configured model rates from `llm_cost_overrides`, or `{}` if unreadable.

    `create_llm_adapter` accepts `cost_overrides`, and this is what supplies it. Without it a rate
    set with `sw costs set` is echoed back by `sw costs` and then ignored by every run, which prices
    from the built-in table instead, or at `0.0` for a model absent from it.

    Never raises: a pricing table that fails to load must not stop a run, for the same reason
    `TelemetryCollector.flush` swallows its own failures. Telemetry observes the work; it is never
    a precondition for it.
    """
    import anyio

    from specweaver.infrastructure.llm.store import LlmRepository

    async def _read() -> dict[str, tuple[float, float]]:
        async with db.async_session_scope() as session:
            return await LlmRepository(session).get_cost_overrides()

    try:
        return anyio.run(_read)
    except Exception:
        logger.warning("Could not load cost overrides; falling back to default pricing")
        return {}


def create_llm_adapter(
    settings: SpecWeaverSettings,
    *,
    telemetry_project: str | None = None,
    cost_overrides: dict[str, tuple[float, float]] | None = None,
) -> tuple[SpecWeaverSettings, Any, GenerationConfig]:
    """Create and validate an LLM adapter from project settings.

    Creates a ``GeminiAdapter`` and verifies it has valid credentials.
    When *telemetry_project* is provided, the adapter is wrapped in a
    ``TelemetryCollector`` so every call records usage telemetry.

    Args:
        settings: Pre-loaded SpecWeaverSettings.
        telemetry_project: If set, wraps the adapter in a
            ``TelemetryCollector`` for this project.
        cost_overrides: Optional cost overrides for telemetry.

    Returns:
        Tuple of (settings, adapter_or_collector, generation_config).

    Raises:
        LLMAdapterError: If no API key is configured or the adapter
            is not available.
    """
    from specweaver.infrastructure.llm.models import GenerationConfig

    adapter_cls = _get_adapter_class(settings.llm.provider)
    adapter: Any = adapter_cls(api_key=settings.llm.api_key or None)

    if not adapter.available():
        env_key = getattr(
            adapter_cls, "api_key_env_var", f"{settings.llm.provider.upper()}_API_KEY"
        )
        logger.warning("create_llm_adapter: adapter not available for %s", settings.llm.provider)
        msg = f"No API key configured for {settings.llm.provider}. Set {env_key} environment variable."
        raise LLMAdapterError(msg)

    # Wrap in rate limiter transparently mapped per-provider
    from specweaver.infrastructure.llm.adapters._rate_limit import AsyncRateLimiterAdapter

    # We use a default concurrency limit of 3.
    # Note: Global Semaphore guarantees limits horizontally across parallel running adapters.
    adapter = AsyncRateLimiterAdapter(adapter, limit=3, timeout=30.0)

    # Wrap in telemetry collector if project is specified
    if telemetry_project:
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.infrastructure.llm.telemetry import CostEntry

        overrides = (
            {k: CostEntry(*v) for k, v in cost_overrides.items()} if cost_overrides else None
        )
        from specweaver.infrastructure.llm.budget import SpendBudget

        adapter = TelemetryCollector(
            adapter,
            telemetry_project,
            overrides,
            budget=SpendBudget(
                limit_usd=settings.llm.max_spend_usd,
                token_limit=settings.llm.max_tokens_per_run,
            ),
        )

    gen_config = GenerationConfig(
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_output_tokens=settings.llm.max_output_tokens,
    )

    logger.debug(
        "create_llm_adapter: created %s adapter, model=%s, telemetry=%s",
        settings.llm.provider,
        settings.llm.model,
        telemetry_project or "off",
    )
    return settings, adapter, gen_config
