# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one path from a role to an adapter and its generation settings.

A role's model and server come from the settings files; the model's facts (output limit, sampling)
from the catalogue, where the role sets none. A role nobody set falls back to the `default` role —
the only fallback model, set in one place. Every role on one server shares one adapter, so one
parallel limit, and every role of the run shares one spend budget.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from specweaver.core.config.llm_settings import SettingsFileError, resolve_roles, to_usd
from specweaver.infrastructure.llm.budget import CallScope, Limit, Unit
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig
from specweaver.infrastructure.llm.servers import adapter_for_server

if TYPE_CHECKING:
    from collections.abc import Iterable

    from specweaver.core.config.llm_settings import (
        LlmSettingsFiles,
        ModelFacts,
        ResolvedRole,
        RoleEntry,
    )
    from specweaver.infrastructure.llm.budget import SpendBudget
    from specweaver.infrastructure.llm.catalogue import Catalogue

#: The role that covers every role left unset.
DEFAULT_ROLE = "default"
_SAMPLING = ("temperature", "top_p", "top_k")


class RoleResolver:
    """Adapters and generation settings for one command's roles."""

    def __init__(
        self,
        files: LlmSettingsFiles,
        *,
        telemetry_project: str,
        budget: SpendBudget,
        catalogue: Catalogue | None = None,
        run_model: RoleEntry | None = None,
    ) -> None:
        self._files = files
        self._roles = resolve_roles(files, _every_role(files, run_model))
        self._project = telemetry_project
        self._budget = budget
        self._catalogue = catalogue or shipped_catalogue()
        self._by_server: dict[str, TelemetryCollector] = {}

    def require(self, roles: Iterable[str]) -> None:
        """Refuse now, before any call, if one of these roles has no model."""
        for role in roles:
            self._check_key(self._setting(role).server)

    def for_role(self, role: str) -> tuple[TelemetryCollector, GenerationConfig]:
        setting = self._setting(role)
        self._check_key(setting.server)
        server = self._files.machine.servers[setting.server]
        facts = self._catalogue.facts(server.kind, setting.model, self._files.machine.models)
        config = GenerationConfig.model_validate(
            {
                "model": setting.model,
                "max_output_tokens": self._output_limit(role, setting, facts),
                "max_tool_rounds": self._files.machine.brake.agent_turns,
                **_sampling(setting, facts),
            }
        )
        return self._adapter(setting.server), config

    def collectors(self) -> list[TelemetryCollector]:
        """Every collector this resolver built, for flushing their usage records."""
        return list(self._by_server.values())

    def _setting(self, role: str) -> ResolvedRole:
        setting = self._roles.get(role) or self._roles.get(DEFAULT_ROLE)
        if setting is None:
            raise SettingsFileError(
                self._files.machine_source,
                f"roles.{role}",
                0,
                f"no model for role '{role}' and no roles.{DEFAULT_ROLE} — set one of them",
            )
        return setting

    def _check_key(self, server_name: str) -> None:
        variable = self._files.machine.servers[server_name].api_key_env
        if variable and not os.environ.get(variable):
            raise SettingsFileError(
                self._files.machine_source,
                f"servers.{server_name}.api_key_env",
                0,
                f"server '{server_name}' reads its key from {variable}, which is not set",
            )

    def _output_limit(self, role: str, setting: ResolvedRole, facts: ModelFacts | None) -> int:
        limit = setting.max_output_tokens or (facts.max_output if facts else None)
        if limit is None:
            raise SettingsFileError(
                self._files.machine_source,
                f"roles.{role}.max_output_tokens",
                0,
                f"the output limit of '{setting.model}' is unknown — set max_output_tokens on the "
                f'role, or max_output under [models."{setting.model}"]',
            )
        return limit

    def _adapter(self, server_name: str) -> TelemetryCollector:
        if server_name not in self._by_server:
            server = self._files.machine.servers[server_name]
            corrections = self._files.machine.models
            self._by_server[server_name] = TelemetryCollector(
                adapter_for_server(server_name, server),
                self._project,
                prices=lambda model: self._catalogue.facts(server.kind, model, corrections),
                budget=self._budget,
                scope_of=lambda config: self._scope(server_name, config),
            )
        return self._by_server[server_name]

    def _scope(self, server_name: str, config: GenerationConfig) -> CallScope:
        """The limits a call counts against: money on a hosted server, tokens on a private one."""
        server = self._files.machine.servers[server_name]
        facts = self._catalogue.facts(server.kind, config.model, self._files.machine.models)
        setting = self._roles.get(config.task_type.value) or self._roles.get(DEFAULT_ROLE)
        brake = self._files.machine.brake
        unit: Unit
        if server.private:
            unit, field = "tokens", "tokens_per_run"
            run: tuple[str, float | None] = ("brake.tokens_per_run", brake.tokens_per_run)
        else:
            unit, field = "usd", "spend_per_run"
            run = ("brake.hosted_spend_per_run", brake.hosted_spend_per_run)
        candidates = [
            run,
            (f'models."{config.model}".{field}', getattr(facts, field) if facts else None),
        ]
        if setting is not None:
            candidates.append((f"roles.{setting.role}.{field}", getattr(setting, field)))
        currency = self._files.machine.currency
        limits = tuple(
            Limit(key, unit, value if unit == "tokens" else to_usd(value, currency))
            for key, value in candidates
            if value is not None
        )
        return CallScope(limits=limits, facts=facts)


def _sampling(setting: ResolvedRole, facts: ModelFacts | None) -> dict[str, float | int]:
    """Per value: the role's, else the catalogue's; a value neither sets is left out."""
    shipped = facts.sampling if facts else None
    values: dict[str, float | int] = {}
    for name in _SAMPLING:
        value = getattr(setting, name)
        if value is None and shipped is not None:
            value = getattr(shipped, name)
        if value is not None:
            values[name] = value
    return values


def _every_role(files: LlmSettingsFiles, run_model: RoleEntry | None) -> dict[str, RoleEntry]:
    """`--model` for one run: every role the files name, and `default`, get the same model.

    A role nobody named falls back to `default`, so overriding `default` covers it too.
    """
    if run_model is None:
        return {}
    named = {*files.machine.roles, *files.project.roles, DEFAULT_ROLE}
    return dict.fromkeys(named, run_model)
