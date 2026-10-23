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
    from collections.abc import Callable, Iterable

    from specweaver.core.config.llm_settings import RoleEntry
    from specweaver.core.config.llm_settings_parse import LlmSettingsFiles
    from specweaver.infrastructure.llm.budget import SpendBudget
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
        return RouterResult(
            adapter=adapter, config=config.model_copy(update={"task_type": task_type})
        )

    def model_of(self, task_type: TaskType) -> str:
        """The model a task type's calls use."""
        return self._resolver.model_of(task_type.value)

    def named_models(self) -> set[str]:
        """The models the settings name for any role, before `--model`."""
        return self._resolver.named_models()

    @property
    def budget(self) -> SpendBudget:
        """The run's spend brake, shared by every role."""
        return self._resolver.budget

    @property
    def search_key(self) -> str | None:
        """The web-search key, or None when the machine file names no search."""
        return self._resolver.search_key()

    def collectors(self) -> list[TelemetryCollector]:
        """Every collector the run's calls went through, for flushing their usage records."""
        return self._resolver.collectors()

    def unwritten(self) -> int:
        """Calls of this command that could not be written to the cost ledger."""
        return sum(collector.unwritten for collector in self._resolver.collectors())


def build_router(
    files: LlmSettingsFiles,
    *,
    project: str,
    roles: Iterable[TaskType | str],
    run_model: RoleEntry | None = None,
    ask: Callable[[str], bool] | None = None,
    db: Any = None,
) -> ModelRouter:
    """A command's router: its limits and every role it will use checked now, before any call.

    One spend budget covers every role of the command, its limits from `[brake]` in the machine
    file. `db` holds the cost history the step limits come from, and the prices, refreshed first
    when a day old; without it there are neither.
    Raises `SettingsFileError` naming the role or key a settings file is missing.
    """
    from specweaver.core.config.llm_settings import brake_limits
    from specweaver.infrastructure.llm import price_refresh
    from specweaver.infrastructure.llm.budget import SpendBudget
    from specweaver.infrastructure.llm.resolve import RoleResolver

    brake_limits(files)
    if db is not None:
        price_refresh.refresh_at_start(db, files)
    budget = SpendBudget(currency=files.machine.currency, ask=ask)
    resolver = RoleResolver(
        files, telemetry_project=project, budget=budget, run_model=run_model, history=db
    )
    resolver.require(role.value if isinstance(role, TaskType) else role for role in roles)
    resolver.search_key()
    return ModelRouter(resolver)
