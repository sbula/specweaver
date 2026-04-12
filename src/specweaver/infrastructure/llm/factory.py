# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""LLM adapter factory — create and validate an LLM adapter from project settings.

Extracted from ``cli/_helpers.py`` so that both the CLI and the REST API
can obtain a ready-to-use adapter without depending on Typer/Rich.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.core.config.database import Database
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.infrastructure.llm.models import GenerationConfig

logger = logging.getLogger(__name__)


class LLMAdapterError(Exception):
    """Raised when an LLM adapter cannot be created or validated."""


def _get_adapter_class(provider: str) -> Any:
    """Return the adapter class for the given provider name."""
    from specweaver.infrastructure.llm.adapters.registry import get_adapter_class, get_all_adapters

    try:
        return get_adapter_class(provider)
    except ValueError as e:
        raise LLMAdapterError(
            f"Unsupported LLM provider: '{provider}'. Available: {list(get_all_adapters().keys())}"
        ) from e


def create_llm_adapter(
    db: Database,
    *,
    llm_role: str = "draft",
    telemetry_project: str | None = None,
) -> tuple[SpecWeaverSettings, Any, GenerationConfig]:
    """Create and validate an LLM adapter from project settings.

    Loads settings for the active project, creates a ``GeminiAdapter``,
    and verifies it has valid credentials.  When *telemetry_project* is
    provided, the adapter is wrapped in a ``TelemetryCollector`` so
    every call records usage telemetry.

    Args:
        db: Database instance for querying project settings.
        llm_role: Which LLM profile role to use (e.g. "draft", "review").
        telemetry_project: If set, wraps the adapter in a
            ``TelemetryCollector`` for this project.

    Returns:
        Tuple of (settings, adapter_or_collector, generation_config).

    Raises:
        LLMAdapterError: If no API key is configured or the adapter
            is not available.
        ValueError: If no project is active (from ``load_settings_for_active``).
    """
    from specweaver.core.config.settings import (
        LLMSettings,
        SpecWeaverSettings,
        load_settings_for_active,
    )
    from specweaver.infrastructure.llm.models import GenerationConfig

    try:
        logger.debug("create_llm_adapter: loading settings for role=%s", llm_role)
        settings = load_settings_for_active(db, llm_role=llm_role)
    except ValueError:
        # Fallback: try loading from env with defaults
        fallback_model = "gemini-3-flash-preview"
        try:
            sys_profile = db.get_llm_profile_by_name("system-default")
            if sys_profile:
                fallback_model = str(sys_profile["model"])
        except Exception:
            pass

        settings = SpecWeaverSettings(
            llm=LLMSettings(
                model=fallback_model,
                provider="gemini",
                api_key=os.environ.get("GEMINI_API_KEY", ""),
            ),
        )

    adapter_cls = _get_adapter_class(settings.llm.provider)
    adapter: Any = adapter_cls(api_key=settings.llm.api_key or None)

    if not adapter.available():
        env_key = getattr(
            adapter_cls, "api_key_env_var", f"{settings.llm.provider.upper()}_API_KEY"
        )
        logger.warning("create_llm_adapter: adapter not available for %s", settings.llm.provider)
        msg = f"No API key configured for {settings.llm.provider}. Set {env_key} environment variable."
        raise LLMAdapterError(msg)

    # Wrap in telemetry collector if project is specified
    if telemetry_project:
        from specweaver.infrastructure.llm.collector import TelemetryCollector
        from specweaver.infrastructure.llm.telemetry import CostEntry

        try:
            raw_overrides = db.get_cost_overrides()
            cost_overrides = (
                {k: CostEntry(*v) for k, v in raw_overrides.items()} if raw_overrides else None
            )
        except Exception:
            cost_overrides = None
        adapter = TelemetryCollector(adapter, telemetry_project, cost_overrides)

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
