# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each role's model and sampling, resolved across the layers, and the report that shows them."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from specweaver.core.config.llm_settings import (
    LIMIT_KEYS,
    BrakeValues,
    ModelFacts,
    RoleEntry,
    StepLimits,
)
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.config.toml_lines import path_line

if TYPE_CHECKING:
    from collections.abc import Iterable

    from specweaver.core.config.llm_settings_parse import LlmSettingsFiles

#: Origin of a value that no file set.
BUILT_IN = "built-in default"
#: Origin of a value given for one run on the command line.
RUN_OVERRIDE = "run --model"

_SAMPLING_FIELDS = ("temperature", "max_output_tokens", "top_p", "top_k")


@dataclass(frozen=True)
class ResolvedRole:
    """The one setting a role's calls use, and where each part of it came from."""

    role: str
    model: str
    server: str
    temperature: float | None = None
    max_output_tokens: int | None = None
    top_p: float | None = None
    top_k: int | None = None
    origin: dict[str, str] = field(default_factory=dict)


def resolve_roles(
    files: LlmSettingsFiles, run_overrides: dict[str, RoleEntry] | None = None
) -> dict[str, ResolvedRole]:
    """Each role's setting. A higher layer that names a role replaces it whole — model and sampling
    together, since sampling tuned for one model means nothing for another."""
    overrides = run_overrides or {}
    layers: list[tuple[Iterable[tuple[str, RoleEntry]], str, str | None, tuple[str, ...]]] = [
        (files.machine.roles.items(), files.machine_source, files.machine_text, ("roles",)),
        (files.project.roles.items(), files.project_source, files.project_text, ("llm", "roles")),
        (overrides.items(), RUN_OVERRIDE, None, ()),
    ]
    resolved: dict[str, ResolvedRole] = {}
    for entries, source, text, prefix in layers:
        for role, entry in entries:
            origin = source if text is None else f"{source}:{path_line(text, (*prefix, role))}"
            if entry.server not in files.machine.servers:
                raise SettingsFileError(
                    source,
                    ".".join((*prefix, role)),
                    path_line(text, (*prefix, role)) if text is not None else 0,
                    f"names server '{entry.server}', which the machine settings file does not "
                    "define",
                )
            resolved[role] = _resolved(role, entry, origin)
    if files.project.private_only:
        _refuse_hosted(files, resolved)
    return resolved


def _refuse_hosted(files: LlmSettingsFiles, resolved: dict[str, ResolvedRole]) -> None:
    """A private-only project must not send code to a server that is not private."""
    for role, setting in sorted(resolved.items()):
        if not files.machine.servers[setting.server].private:
            raise SettingsFileError(
                files.project_source,
                "llm.private_only",
                path_line(files.project_text, ("llm", "private_only")),
                f"the project allows private servers only, but role '{role}' uses "
                f"'{setting.server}', which is not private ({setting.origin['model']})",
            )


def _resolved(role: str, entry: RoleEntry, origin: str) -> ResolvedRole:
    values = {name: getattr(entry, name) for name in _SAMPLING_FIELDS}
    origins = {"model": origin, "server": origin}
    origins.update({name: origin for name, value in values.items() if value is not None})
    return ResolvedRole(role=role, model=entry.model, server=entry.server, origin=origins, **values)


def _step_limit_rows(files: LlmSettingsFiles) -> list[tuple[str, str, str]]:
    limits = files.machine.step_limits
    if limits is None:
        return [("step_limits", "off — [step_limits] is not set", "-")]
    return [
        (
            f"step_limits.{name}",
            str(getattr(limits, name)),
            f"{files.machine_source}:{path_line(files.machine_text, ('step_limits', name))}",
        )
        for name in StepLimits.model_fields
    ]


def _file_role_rows(roles: dict[str, ResolvedRole]) -> list[tuple[str, str, str]]:
    """Each role as the settings files set it."""
    rows: list[tuple[str, str, str]] = []
    for role, resolved in sorted(roles.items()):
        rows.append(
            (f"roles.{role}", f"{resolved.model}@{resolved.server}", resolved.origin["model"])
        )
        for name in _SAMPLING_FIELDS:
            value = getattr(resolved, name)
            if value is not None:
                rows.append((f"roles.{role}.{name}", str(value), resolved.origin[name]))
    return rows


def settings_report(
    files: LlmSettingsFiles,
    roles: dict[str, ResolvedRole],
    role_rows: list[tuple[str, str, str]] | None = None,
) -> list[tuple[str, str, str]]:
    """Every effective LLM setting as (key, value, origin), for `sw config show`.

    `role_rows`, when given, replaces the roles as the files set them with what a call sends.
    """
    machine = files.machine
    at = f"{files.machine_source}:{{}}"
    rows: list[tuple[str, str, str]] = []
    for name, server in sorted(machine.servers.items()):
        value = f"{server.kind} {server.base_url or ''} private={server.private} "
        value += f"max_parallel={server.max_parallel} key={server.api_key_env or '-'}"
        rows.append(
            (
                f"servers.{name}",
                " ".join(value.split()),
                at.format(path_line(files.machine_text, ("servers", name))),
            )
        )
    rows.extend(role_rows if role_rows is not None else _file_role_rows(roles))
    for name in BrakeValues.model_fields:
        value = getattr(machine.brake, name)
        if value is None:
            rows.append(
                (f"brake.{name}", "unset — required by any command that calls a model", "-")
            )
        else:
            line = path_line(files.machine_text, ("brake", name))
            rows.append((f"brake.{name}", _number(value), at.format(line)))
    rows.extend(_stored_limits(files, "models", machine.models.items()))
    rows.extend(_step_limit_rows(files))
    if machine.currency is None:
        rows.append(("currency", "not set — costs are shown in USD", BUILT_IN))
    else:
        currency = machine.currency
        rate = f"{currency.code}, {currency.per_usd:g} per USD, rate of {currency.rate_date}"
        rows.append(("currency", rate, at.format(path_line(files.machine_text, ("currency",)))))
    project = files.project
    if project.private_only:
        rows.append(
            (
                "llm.private_only",
                "true",
                f"{files.project_source}:{path_line(files.project_text, ('llm', 'private_only'))}",
            )
        )
    return rows


def _stored_limits(
    files: LlmSettingsFiles, table: str, entries: Iterable[tuple[str, ModelFacts]]
) -> list[tuple[str, str, str]]:
    """Model limits, each with its line."""
    rows = []
    for name, entry in sorted(entries, key=lambda item: item[0]):
        for key in LIMIT_KEYS:
            value = getattr(entry, key)
            if value is not None:
                line = path_line(files.machine_text, (table, name, key))
                rows.append(
                    (
                        f"{table}.{name}.{key}",
                        _number(value),
                        f"{files.machine_source}:{line}",
                    )
                )
    return rows


def _number(value: float) -> str:
    """A limit as written: no exponent, no trailing `.0`."""
    return str(int(value)) if float(value).is_integer() else str(value)
