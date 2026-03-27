# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""LLM adapter factory — create and validate an LLM adapter from project settings.

Extracted from ``cli/_helpers.py`` so that both the CLI and the REST API
can obtain a ready-to-use adapter without depending on Typer/Rich.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from specweaver.config.database import Database
    from specweaver.config.settings import SpecWeaverSettings
    from specweaver.llm.models import GenerationConfig

logger = logging.getLogger(__name__)


class LLMAdapterError(Exception):
    """Raised when an LLM adapter cannot be created or validated."""


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
    from specweaver.config.settings import LLMSettings, SpecWeaverSettings, load_settings_for_active
    from specweaver.llm.adapters.gemini import GeminiAdapter
    from specweaver.llm.models import GenerationConfig

    try:
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
                api_key=os.environ.get("GEMINI_API_KEY", ""),
            ),
        )

    adapter: Any = GeminiAdapter(api_key=settings.llm.api_key or None)

    if not adapter.available():
        msg = "No API key configured. Set GEMINI_API_KEY environment variable."
        raise LLMAdapterError(msg)

    # Wrap in telemetry collector if project is specified
    if telemetry_project:
        from specweaver.llm.collector import TelemetryCollector
        from specweaver.llm.telemetry import CostEntry

        try:
            raw_overrides = db.get_cost_overrides()
            cost_overrides = {
                k: CostEntry(*v) for k, v in raw_overrides.items()
            } if raw_overrides else None
        except Exception:
            cost_overrides = None
        adapter = TelemetryCollector(adapter, telemetry_project, cost_overrides)

    gen_config = GenerationConfig(
        model=settings.llm.model,
        temperature=settings.llm.temperature,
        max_output_tokens=settings.llm.max_output_tokens,
    )

    return settings, adapter, gen_config

