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
    from collections.abc import Mapping

    from specweaver.core.config.llm_settings import ModelFacts
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


def build_adapter_for_project(
    db: Any, settings: Any, project: str, machine_models: Mapping[str, ModelFacts] | None = None
) -> tuple[Any, Any]:
    """A telemetry-attributed adapter for `project`, priced from the catalogue and the user's own
    corrections in the machine settings file.

    `db` stays in the signature for the callers until they move to the one resolver.
    """
    del db
    return create_llm_adapter(settings, telemetry_project=project, machine_models=machine_models)[
        :2
    ]


def create_llm_adapter(
    settings: SpecWeaverSettings,
    *,
    telemetry_project: str | None = None,
    machine_models: Mapping[str, ModelFacts] | None = None,
) -> tuple[SpecWeaverSettings, Any, GenerationConfig]:
    """Create and validate an LLM adapter from project settings.

    Creates a ``GeminiAdapter`` and verifies it has valid credentials.
    When *telemetry_project* is provided, the adapter is wrapped in a
    ``TelemetryCollector`` so every call records usage telemetry.

    Args:
        settings: Pre-loaded SpecWeaverSettings.
        telemetry_project: If set, wraps the adapter in a
            ``TelemetryCollector`` for this project.

    Returns:
        Tuple of (settings, adapter_or_collector, generation_config).

    Raises:
        LLMAdapterError: If no API key is configured or the adapter
            is not available.
    """
    from specweaver.infrastructure.llm.models import GenerationConfig

    adapter_cls = _get_adapter_class(settings.llm.provider)
    try:
        adapter: Any = adapter_cls(api_key=settings.llm.api_key or None)
    except ValueError as e:
        msg = f"{e}. Set it up as a server in the machine settings file (settings.toml)."
        raise LLMAdapterError(msg) from e

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
    adapter = AsyncRateLimiterAdapter(adapter, limit=3)

    # Wrap in telemetry collector if project is specified
    if telemetry_project:
        from specweaver.infrastructure.llm.budget import SpendBudget
        from specweaver.infrastructure.llm.catalogue import shipped_catalogue
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        provider = settings.llm.provider
        corrections = machine_models or {}
        adapter = TelemetryCollector(
            adapter,
            telemetry_project,
            lambda model: shipped_catalogue().facts(provider, model, corrections),
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
