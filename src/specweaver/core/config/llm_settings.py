# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The LLM settings files: the machine `settings.toml` and a project's `[llm]` section.

Pure: text in, typed model out. Reading the files is `core.config.bootstrap`'s job.

Every model forbids unknown keys, so a typo refuses instead of becoming a silent default, and every
refusal names the file, the key and the line. A project may choose models; it may not say where code
is sent — servers, addresses and key variables belong to the machine file alone.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from specweaver.core.config.settings_file import SettingsFileError, load_toml, validate
from specweaver.core.config.toml_lines import path_line

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from pathlib import Path

#: The file shape this SpecWeaver understands.
SCHEMA_VERSION = 1

ServerKind = Literal["gemini", "openai", "anthropic", "mistral", "qwen", "openai-compatible"]
RoleName = Literal[
    "draft", "review", "plan", "implement", "scenario", "validate", "check", "default"
]

_NEEDS_ADDRESS = frozenset({"openai-compatible", "qwen"})

_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: Keys that decide where code is sent. Only the machine file may set them.
_MACHINE_ONLY_KEYS = frozenset({"servers", "base_url", "api_key_env"})
#: A model's limit keys.
_LIMIT_KEYS = ("spend_per_run", "tokens_per_run")


class SettingNotSetError(SettingsFileError):
    """A setting nobody set, as opposed to one set wrong: optional model use can skip it."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerEntry(_Strict):
    """One place a model can run: a hosted provider or a local server."""

    kind: ServerKind
    base_url: str | None = None
    api_key_env: str | None = None
    private: bool
    max_parallel: int = Field(ge=1)
    #: The models.dev provider id of a hosted `openai-compatible` server, whose prices are then
    #: refreshed from it; without it, only your settings price the server's models.
    models_dev: str | None = None

    @model_validator(mode="after")
    def _key_variable_and_address(self) -> ServerEntry:
        if self.api_key_env is not None and not _VARIABLE_NAME.fullmatch(self.api_key_env):
            msg = "api_key_env names the environment variable that holds the key, not the key"
            raise ValueError(msg)
        if self.api_key_env is None and self.kind != "openai-compatible":
            msg = (
                f"a {self.kind} server needs api_key_env, the environment variable that holds its "
                'key; a server that needs no key is kind = "openai-compatible"'
            )
            raise ValueError(msg)
        if self.kind in _NEEDS_ADDRESS and not self.base_url:
            msg = f"a {self.kind} server needs a base_url"
            raise ValueError(msg)
        return self


class Sampling(_Strict):
    """Sampling values, within the widest ranges the providers accept."""

    temperature: float | None = Field(default=None, ge=0, le=2)
    top_p: float | None = Field(default=None, ge=0, le=1)
    top_k: int | None = Field(default=None, ge=1)


class RoleEntry(Sampling):
    """Which model does a role's work, on which server, with optional sampling overrides."""

    model: str
    server: str
    max_output_tokens: int | None = Field(default=None, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _split_model_at_server(cls, value: Any) -> Any:
        entry = {"model": value} if isinstance(value, str) else value
        if not isinstance(entry, dict) or not isinstance(entry.get("model"), str):
            return value
        model, sep, server = entry["model"].rpartition("@")
        if not sep or not model or not server:
            msg = 'a role names its model as "model@server"'
            raise ValueError(msg)
        return {**entry, "model": model, "server": server}


class ModelFacts(_Strict):
    """Facts about one model. The shipped catalogue holds them; the machine file corrects them."""

    context: int | None = Field(default=None, ge=1)
    max_output: int | None = Field(default=None, ge=1)
    tool_calls: bool | None = None
    usd_per_million_input: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    usd_per_million_output: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    usd_per_million_cached_read: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    usd_per_million_cache_write: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    #: One output limit also bounds the model's hidden thinking, so a call's cost has a ceiling.
    thinking_in_output_cap: bool | None = None
    sampling: Sampling | None = None
    #: Per-run limits for this model — money (configured currency) for a hosted model, tokens for
    #: one on a private server.
    spend_per_run: float | None = Field(default=None, gt=0)
    tokens_per_run: int | None = Field(default=None, gt=0)


class BrakeValues(_Strict):
    """A run's limits. Values only: how the brake behaves is the spend brake's job.

    None has a default: a value nobody set is unset, and a command that calls a model refuses
    until it is set (`brake_limits`). Commands that call no model never ask.
    """

    #: The run's money total, in the configured currency (`[currency] code`), USD when none is set.
    hosted_spend_per_run: float | None = Field(default=None, gt=0)
    #: The run's token total.
    tokens_per_run: int | None = Field(default=None, gt=0)
    #: Rounds one tool loop may take.
    agent_turns: int | None = Field(default=None, gt=0)


class BrakeLimits(NamedTuple):
    """The three `[brake]` values a command that calls a model needs, all set."""

    hosted_spend_per_run: float
    tokens_per_run: int
    agent_turns: int


def brake_limits(files: LlmSettingsFiles) -> BrakeLimits:
    """The run's limits, or `SettingsFileError` naming the first `[brake]` value left unset."""
    brake = files.machine.brake
    for name in BrakeLimits._fields:
        if getattr(brake, name) is None:
            raise SettingNotSetError(
                files.machine_source,
                f"brake.{name}",
                path_line(files.machine_text, ("brake",)),
                "not set — every command that calls a model needs it; there is no default",
            )
    return BrakeLimits(*(getattr(brake, name) for name in BrakeLimits._fields))


class Currency(_Strict):
    """The one currency every amount is shown and taken in. Stored amounts stay USD."""

    code: str = Field(pattern=r"^[A-Z]{3}$")
    per_usd: float = Field(gt=0)
    rate_date: date

    @model_validator(mode="after")
    def _rate_from_the_past(self) -> Currency:
        if self.rate_date > date.today():
            msg = f"rate_date {self.rate_date} is in the future; give the date the rate was read"
            raise ValueError(msg)
        return self


def format_money(usd: float | None, currency: Currency | None, *, places: int = 2) -> str:
    """A USD amount in the configured currency; `unknown` stays unknown, never 0."""
    if usd is None:
        return "unknown"
    code, value = ("USD", usd) if currency is None else (currency.code, usd * currency.per_usd)
    while value and abs(value) < 10**-places and places < 6:  # never show a real amount as 0
        places += 1
    return f"{code} {value:.{places}f}"


def to_usd(amount: float, currency: Currency | None) -> float:
    """An amount given in the configured currency, as the USD that is stored."""
    return amount if currency is None else amount / currency.per_usd


class StepLimits(_Strict):
    """How a step's limit is taken from the history of similar steps; no value in code."""

    percentile: int = Field(ge=1, le=100)
    min_steps: int = Field(ge=1)


class SearchEntry(_Strict):
    """The web search the agents' `web_search` tool asks: Tavily, its key in `keys.env`."""

    api_key_env: str

    @model_validator(mode="after")
    def _a_variable_name(self) -> SearchEntry:
        if not _VARIABLE_NAME.fullmatch(self.api_key_env):
            msg = "api_key_env names the environment variable that holds the key, not the key"
            raise ValueError(msg)
        return self


class ServeValues(_Strict):
    """`sw serve`'s limits. Unset is refused where it is needed, never filled in."""

    #: Runs the API takes at once.
    max_runs: int | None = Field(default=None, gt=0)


class MachineLlmFile(_Strict):
    """`~/.specweaver/settings.toml`."""

    schema_version: int = SCHEMA_VERSION
    currency: Currency | None = None
    servers: dict[str, ServerEntry] = Field(default_factory=dict)
    roles: dict[RoleName, RoleEntry] = Field(default_factory=dict)
    brake: BrakeValues = Field(default_factory=BrakeValues)
    models: dict[str, ModelFacts] = Field(default_factory=dict)
    step_limits: StepLimits | None = None
    search: SearchEntry | None = None
    serve: ServeValues = Field(default_factory=ServeValues)


class ProjectLlmSection(_Strict):
    """The `[llm]` section of a project's `specweaver.toml`: choices only."""

    schema_version: int = SCHEMA_VERSION
    private_only: bool = False
    roles: dict[RoleName, RoleEntry] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_machine_file(text: str, source: str) -> MachineLlmFile:
    """The machine settings file, or `SettingsFileError` naming what is wrong and where."""
    data = load_toml(text, source)
    _check_schema_version(data, text, source, prefix=())
    return validate(MachineLlmFile, data, text, source, prefix=())


def parse_project_llm(text: str, source: str) -> ProjectLlmSection:
    """A project's `[llm]` section; an absent section is an empty choice."""
    section = load_toml(text, source).get("llm", {})
    _check_schema_version(section, text, source, prefix=("llm",))
    forbidden = _find_machine_only_key(section, ("llm",))
    if forbidden:
        raise SettingsFileError(
            source,
            ".".join(forbidden),
            path_line(text, forbidden),
            "a project may choose models, not define where code is sent — set servers, "
            "addresses and key variables in the machine settings file",
        )
    return validate(ProjectLlmSection, section, text, source, prefix=("llm",))


def _check_schema_version(
    data: dict[str, Any], text: str, source: str, *, prefix: tuple[str, ...]
) -> None:
    version = data.get("schema_version", SCHEMA_VERSION)
    path = (*prefix, "schema_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        message = f"schema_version is a whole number from 1 to {SCHEMA_VERSION}"
    elif version > SCHEMA_VERSION:
        message = (
            f"written for settings schema {version}; this SpecWeaver reads {SCHEMA_VERSION} — "
            "upgrade SpecWeaver"
        )
    else:
        return
    raise SettingsFileError(source, ".".join(path), path_line(text, path), message)


def _find_machine_only_key(value: Any, path: tuple[str, ...]) -> tuple[str, ...] | None:
    if not isinstance(value, dict):
        return None
    for key, child in value.items():
        if key in _MACHINE_ONLY_KEYS:
            return (*path, key)
        found = _find_machine_only_key(child, (*path, key))
        if found:
            return found
    return None


# ---------------------------------------------------------------------------
# Layering: machine → project → run override
# ---------------------------------------------------------------------------

#: Origin of a value that no file set.
BUILT_IN = "built-in default"
#: Origin of a value given for one run on the command line.
RUN_OVERRIDE = "run --model"

_SAMPLING_FIELDS = ("temperature", "max_output_tokens", "top_p", "top_k")


@dataclass(frozen=True)
class LlmSettingsFiles:
    """Both settings files, parsed, with their text kept so every value can name its line."""

    machine: MachineLlmFile
    machine_source: str
    machine_text: str
    project: ProjectLlmSection
    project_source: str
    project_text: str
    project_root: Path | None = None
    #: API keys by variable name, from `keys.env`; never printed.
    keys: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)
    #: Where the keys came from, for messages.
    keys_source: str = "keys.env"

    @classmethod
    def from_texts(
        cls,
        *,
        machine_text: str,
        machine_source: str,
        project_text: str,
        project_source: str,
        project_root: Path | None = None,
        keys: Mapping[str, str] | None = None,
        keys_source: str = "keys.env",
    ) -> LlmSettingsFiles:
        return cls(
            machine=parse_machine_file(machine_text, machine_source),
            machine_source=machine_source,
            machine_text=machine_text,
            project=parse_project_llm(project_text, project_source),
            project_source=project_source,
            project_text=project_text,
            project_root=project_root,
            keys=dict(keys or {}),
            keys_source=keys_source,
        )


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
        for key in _LIMIT_KEYS:
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
