# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ModelRouter — config-driven per-task-type LLM adapter resolution (3.12b).

Resolves which LLM adapter and generation settings to use for each pipeline
step, based on database routing entries keyed by TaskType.

Adapter instances are cached by (provider, api_key_hash) so that multiple
task types using the same provider share a single adapter connection. The
model name and temperature travel in RouterResult, not the adapter itself —
enabling e.g. gemini-pro at 0.5 for spec writing and 0.2 for review using
one GeminiAdapter instance.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, NamedTuple

from specweaver.core.config.settings import load_settings
from specweaver.infrastructure.llm.adapters.registry import get_adapter_class

if TYPE_CHECKING:
    from specweaver.core.config.database import Database
    from specweaver.infrastructure.llm.models import TaskType

logger = logging.getLogger(__name__)


class RouterResult(NamedTuple):
    """Resolved routing result for one LLM call.

    All fields are read by the handler to build GenerationConfig and select
    the adapter. Temperature is profile-wins: use routed.temperature, not the
    handler's hardcoded default.
    """

    adapter: Any  # LLMAdapter or TelemetryCollector proxy
    model: str
    temperature: float
    max_output_tokens: int
    provider: str  # for logging / diagnostics
    profile_name: str  # for logging / diagnostics


class ModelRouter:
    """Resolves the correct LLM adapter + settings per TaskType.

    Created once per pipeline run by the CLI layer. Injected into
    RunContext.llm_router. Caches adapter instances by (provider, api_key_hash)
    so that multiple task types sharing the same provider reuse one adapter.

    Multiple task types MAY use the same provider with different models
    (e.g. draft → gemini-flash, implement → gemini-pro). They share one
    adapter instance; model differences are in RouterResult.model and
    temperature differences are in RouterResult.temperature.
    """

    def __init__(
        self,
        db: Database,
        project_name: str,
        telemetry_project: str | None = None,
    ) -> None:
        self._db = db
        self._project_name = project_name
        self._telemetry_project = telemetry_project
        self._cache: dict[str, Any] = {}  # key: f"{provider}:{hash(api_key)}"

    def get_for_task(self, task_type: TaskType) -> RouterResult | None:
        """Return RouterResult for this task_type, or None if no routing configured.

        None → caller MUST fall back to context.llm + context.config.llm.model.
        Never raises — all exceptions are caught and logged.
        """
        role_key = f"task:{task_type.value}"

        # First check: does a routing entry exist for this task type?
        # We must not fall through to load_settings' system-default fallback —
        # that would incorrectly treat the absence of a routing entry as a configured route.
        try:
            profile = self._db.get_project_profile(self._project_name, role_key)
        except Exception:
            logger.warning(
                "[routing] DB error checking task_type=%s",
                task_type.value,
                exc_info=True,
            )
            return None

        if not profile:
            logger.debug(
                "[routing] no entry for task_type=%s, using default",
                task_type.value,
            )
            return None

        try:
            settings = load_settings(self._db, self._project_name, llm_role=role_key)
        except ValueError:
            logger.debug(
                "[routing] load_settings failed for task_type=%s",
                task_type.value,
            )
            return None
        except Exception:
            logger.warning(
                "[routing] lookup failed for task_type=%s",
                task_type.value,
                exc_info=True,
            )
            return None

        cache_key = f"{settings.llm.provider}:{hash(settings.llm.api_key)}"
        if cache_key not in self._cache:
            try:
                adapter_cls = get_adapter_class(settings.llm.provider)
                api_key = settings.llm.api_key or os.environ.get(
                    getattr(
                        adapter_cls,
                        "api_key_env_var",
                        f"{settings.llm.provider.upper()}_API_KEY",
                    ),
                    "",
                )
                adapter: Any = adapter_cls(api_key=api_key or None)  # type: ignore[call-arg]
                if self._telemetry_project:
                    from specweaver.infrastructure.llm.collector import TelemetryCollector
                    from specweaver.infrastructure.llm.telemetry import CostEntry

                    try:
                        raw = self._db.get_cost_overrides()
                        overrides = {k: CostEntry(*v) for k, v in raw.items()} if raw else None
                    except Exception:
                        overrides = None
                    adapter = TelemetryCollector(adapter, self._telemetry_project, overrides)
                self._cache[cache_key] = adapter
            except Exception:
                logger.warning(
                    "[routing] adapter creation failed for provider=%s",
                    settings.llm.provider,
                    exc_info=True,
                )
                return None

        logger.debug(
            "[routing] task_type=%s → provider=%s, model=%s, temperature=%.2f",
            task_type.value,
            settings.llm.provider,
            settings.llm.model,
            settings.llm.temperature,
        )
        return RouterResult(
            adapter=self._cache[cache_key],
            model=settings.llm.model,
            temperature=settings.llm.temperature,
            max_output_tokens=settings.llm.max_output_tokens,
            provider=settings.llm.provider,
            profile_name="",
        )
