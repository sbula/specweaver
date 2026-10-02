# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""ModelRouter — the pipeline's view of the one resolver.

A step names its task type; the router answers with that role's adapter and generation settings,
exactly as `RoleResolver` resolves them from the settings files; a task type no role names — such
as `unknown` — gets the `default` role. There is no other source: a step never builds an adapter or picks a model itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

from specweaver.infrastructure.llm.models import TaskType

if TYPE_CHECKING:
    from collections.abc import Iterable

    from specweaver.core.config.llm_settings import LlmSettingsFiles
    from specweaver.infrastructure.llm.collector import TelemetryCollector
    from specweaver.infrastructure.llm.models import GenerationConfig
    from specweaver.infrastructure.llm.resolve import RoleResolver


class RouterResult(NamedTuple):
    """One task type's adapter and the settings its calls use."""

    adapter: Any  # TelemetryCollector
    config: GenerationConfig


class ModelRouter:
    """Resolves each task type to its role's adapter and settings."""

    def __init__(self, resolver: RoleResolver) -> None:
        self._resolver = resolver

    def get_for_task(self, task_type: TaskType) -> RouterResult:
        adapter, config = self._resolver.for_role(task_type.value)
        return RouterResult(adapter=adapter, config=config)

    def collectors(self) -> list[TelemetryCollector]:
        """Every collector the run's calls went through, for flushing their usage records."""
        return self._resolver.collectors()


def build_router(
    files: LlmSettingsFiles,
    *,
    project: str,
    roles: Iterable[TaskType | str],
    spend_limit_usd: float | None,
    token_limit: int | None,
) -> ModelRouter:
    """A command's router: every role it will use checked now, before the first call.

    One spend budget covers every role of the command. Raises `SettingsFileError` naming the role
    or key a settings file is missing.
    """
    from specweaver.infrastructure.llm.budget import SpendBudget
    from specweaver.infrastructure.llm.resolve import RoleResolver

    resolver = RoleResolver(
        files,
        telemetry_project=project,
        budget=SpendBudget(limit_usd=spend_limit_usd, token_limit=token_limit),
    )
    resolver.require(role.value if isinstance(role, TaskType) else role for role in roles)
    return ModelRouter(resolver)
