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
from datetime import date
from typing import TYPE_CHECKING, Any, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from specweaver.core.config.settings_file import SettingsFileError
from specweaver.core.config.toml_lines import path_line

if TYPE_CHECKING:
    from specweaver.core.config.llm_settings_parse import LlmSettingsFiles

#: The file shape this SpecWeaver understands.
SCHEMA_VERSION = 1

ServerKind = Literal["gemini", "openai", "anthropic", "mistral", "qwen", "openai-compatible"]
RoleName = Literal[
    "draft", "review", "plan", "implement", "scenario", "validate", "check", "default"
]

_NEEDS_ADDRESS = frozenset({"openai-compatible", "qwen"})

_VARIABLE_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: A model's limit keys.
LIMIT_KEYS = ("spend_per_run", "tokens_per_run")


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
