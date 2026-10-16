# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one path from a role to an adapter and its generation settings.

A role's model and server come from the settings files; the model's facts (output limit, sampling)
from the catalogue, where the role sets none. A role nobody set falls back to the `default` role —
the only fallback model, set in one place. Every role on one server shares one adapter, so one
parallel limit, and every role of the run shares one spend budget.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, NoReturn

from specweaver.core.config.llm_settings import (
    SettingNotSetError,
    SettingsFileError,
    resolve_roles,
    to_usd,
)
from specweaver.core.config.toml_lines import line_of
from specweaver.infrastructure.llm.budget import STEP_LIMIT_PREFIX, CallScope, Limit, Unit
from specweaver.infrastructure.llm.catalogue import shipped_catalogue
from specweaver.infrastructure.llm.collector import TelemetryCollector
from specweaver.infrastructure.llm.models import GenerationConfig
from specweaver.infrastructure.llm.redaction import Redactor, vault_values
from specweaver.infrastructure.llm.servers import adapter_for_server
from specweaver.infrastructure.llm.store import step_history_limit

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

logger = logging.getLogger(__name__)

#: The role that covers every role left unset.
DEFAULT_ROLE = "default"
#: The scenario agent's role: `--model` never sets it, so it stays apart from the coder.
SCENARIO_ROLE = "scenario"
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
        history: Any = None,
    ) -> None:
        self._files = files
        self._roles = resolve_roles(files, _every_role(files, run_model))
        if run_model is not None:
            own = resolve_roles(files)
            kept = own.get(SCENARIO_ROLE) or own.get(DEFAULT_ROLE)
            if kept is not None:
                self._roles[SCENARIO_ROLE] = kept
        self._project = telemetry_project
        self._budget = budget
        self._catalogue = catalogue or shipped_catalogue()
        self._by_server: dict[str, TelemetryCollector] = {}
        self._vault = vault_values(files.project_root)
        self._history = history
        self._step_limits: dict[tuple[str, ...], float | None] = {}
        self._uncapped: set[str] = set()

    @property
    def budget(self) -> SpendBudget:
        return self._budget

    def require(self, roles: Iterable[str]) -> None:
        """Refuse now, before any call, if one of these roles has no model."""
        for role in roles:
            setting = self._setting(role)
            self._check_key(setting.server)
            self._check_bounded(setting)

    def for_role(self, role: str) -> tuple[TelemetryCollector, GenerationConfig]:
        setting = self._setting(role)
        self._check_key(setting.server)
        self._check_bounded(setting)
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

    def model_of(self, role: str) -> str:
        """The model this role's calls use."""
        return self._setting(role).model

    def named_models(self) -> set[str]:
        """The models the settings files name for any role, before `--model`."""
        return {setting.model for setting in resolve_roles(self._files).values()}

    def collectors(self) -> list[TelemetryCollector]:
        """Every collector this resolver built, for flushing their usage records."""
        return list(self._by_server.values())

    def _setting(self, role: str) -> ResolvedRole:
        setting = self._roles.get(role) or self._roles.get(DEFAULT_ROLE)
        if setting is None:
            key = f"roles.{role}"
            raise SettingNotSetError(
                self._files.machine_source,
                key,
                line_of(self._files.machine_text, key, "roles"),
                f"no model for role '{role}' and no roles.{DEFAULT_ROLE} — set one of them, "
                f"e.g. sw config set-role {role} <model@server>",
            )
        return setting

    def _check_bounded(self, setting: ResolvedRole) -> None:
        """Refuse a hosted model with no price; warn when its thinking may not be bounded."""
        server = self._files.machine.servers[setting.server]
        if server.private:
            return
        facts = self._catalogue.facts(server.kind, setting.model, self._files.machine.models)
        table = f'models."{setting.model}"'
        if facts is None or None in (facts.usd_per_million_input, facts.usd_per_million_output):
            self._refuse(
                f"{table}.usd_per_million_input",
                f"the hosted model '{setting.model}' has no known price; set usd_per_million_input "
                f"and usd_per_million_output under [{table}]",
                f"roles.{setting.role}",
            )
        if facts is not None and facts.thinking_in_output_cap is not True:
            self._warn_uncapped(setting.model, table)

    def _warn_uncapped(self, model: str, table: str) -> None:
        if model in self._uncapped:
            return
        self._uncapped.add(model)
        logger.warning(
            "it is not known whether the output limit of '%s' also bounds its thinking, so a "
            "call may cost more than its worst case; set %s.thinking_in_output_cap once you "
            "have checked",
            model,
            table,
        )

    def search_key(self) -> str | None:
        """The web-search key `[search]` names, from keys.env; None when there is no `[search]`."""
        search = self._files.machine.search
        if search is None:
            return None
        key = self._files.keys.get(search.api_key_env)
        if not key:
            self._refuse(
                "search.api_key_env",
                f"web search reads its key from {search.api_key_env}, which "
                f"{self._files.keys_source} does not set",
                "search",
            )
        return key

    def _refuse(self, key: str, message: str, *near: str) -> NoReturn:
        """Refuse naming `key`'s line, else the line of the first of `near` in the file."""
        line = line_of(self._files.machine_text, key, *near)
        raise SettingsFileError(self._files.machine_source, key, line, message)

    def _check_key(self, server_name: str) -> None:
        variable = self._files.machine.servers[server_name].api_key_env
        if variable and not self._files.keys.get(variable):
            self._refuse(
                f"servers.{server_name}.api_key_env",
                f"server '{server_name}' reads its key from {variable}, which "
                f"{self._files.keys_source} does not set",
                f"servers.{server_name}",
            )

    def _output_limit(self, role: str, setting: ResolvedRole, facts: ModelFacts | None) -> int:
        limit = setting.max_output_tokens or (facts.max_output if facts else None)
        if limit is None:
            self._refuse(
                f"roles.{role}.max_output_tokens",
                f"the output limit of '{setting.model}' is unknown — set max_output_tokens on the "
                f'role, or max_output under [models."{setting.model}"]',
                f"roles.{role}",
                "roles",
            )
        return limit

    def _adapter(self, server_name: str) -> TelemetryCollector:
        if server_name not in self._by_server:
            server = self._files.machine.servers[server_name]
            corrections = self._files.machine.models
            adapter = adapter_for_server(server_name, server, self._files.keys)
            keys = list(self._files.keys.values())
            self._by_server[server_name] = TelemetryCollector(
                adapter,
                self._project,
                prices=lambda model: self._catalogue.facts(server.kind, model, corrections),
                budget=self._budget,
                scope_of=lambda config: self._scope(server_name, config),
                redactor=Redactor([*keys, *self._vault]),
                server=server_name,
                ledger=self._history,
            )
        return self._by_server[server_name]

    def _scope(self, server_name: str, config: GenerationConfig) -> CallScope:
        """The limits a call counts against: money on a hosted server, tokens on a private one."""
        server = self._files.machine.servers[server_name]
        facts = self._catalogue.facts(server.kind, config.model, self._files.machine.models)
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
        currency = self._files.machine.currency
        limits = tuple(
            Limit(key, unit, value if unit == "tokens" else to_usd(value, currency))
            for key, value in candidates
            if value is not None
        )
        return CallScope(limits=(*limits, *self._step_limit(config, unit)), facts=facts)

    def _step_limit(self, config: GenerationConfig, unit: Unit) -> tuple[Limit, ...]:
        """The step's limit from the history of its group, read once per run and group."""
        settings = self._files.machine.step_limits
        if settings is None or self._history is None or not config.step_name:
            return ()
        task = config.task_type.value
        group = (config.run_id, task, config.model, config.dal_level, unit)
        if group not in self._step_limits:
            self._step_limits[group] = step_history_limit(
                self._history,
                task_type=task,
                model=config.model,
                dal_level=config.dal_level,
                unit=unit,
                steps=settings.min_steps,
                percentile=settings.percentile,
            )
        value = self._step_limits[group]
        if value is None:
            return ()
        # The run keeps sub-runs that share a step name apart; retries share the key.
        key = f"{STEP_LIMIT_PREFIX}{task}.{config.step_name}"
        name = f"{key}@{config.run_id[:8]}" if config.run_id else key
        return (Limit(name, unit, value, on_spent=True),)


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
    """`--model` for one run: every role the files name, and `default`, get the same model —
    all but the scenario agent's, which keeps its own so the two sides of a dual run stay apart.

    A role nobody named falls back to `default`, so overriding `default` covers it too.
    """
    if run_model is None:
        return {}
    named = {*files.machine.roles, *files.project.roles, DEFAULT_ROLE} - {SCENARIO_ROLE}
    return dict.fromkeys(named, run_model)
