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
import tomllib
from datetime import date
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

_M = TypeVar("_M", bound=BaseModel)

#: The file shape this SpecWeaver understands.
SCHEMA_VERSION = 1

ServerKind = Literal["gemini", "openai", "anthropic", "mistral", "qwen", "openai-compatible"]
RoleName = Literal["draft", "review", "plan", "implement", "validate", "check", "default"]

#: The variable each hosted provider's adapter reads when a server entry names none.
_DEFAULT_KEY_ENV: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "mistral": "MISTRAL_API_KEY",
    "qwen": "QWEN_API_KEY",
}

#: Keys that decide where code is sent. Only the machine file may set them.
_MACHINE_ONLY_KEYS = frozenset({"servers", "base_url", "api_key_env"})


class SettingsFileError(ValueError):
    """A settings file that cannot be used, located by file, key and line."""

    def __init__(self, source: str, key: str, line: int, message: str) -> None:
        self.source = source
        self.key = key
        self.line = line
        self.message = message
        super().__init__(f"{source}:{line}: {key}: {message}")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ServerEntry(_Strict):
    """One place a model can run: a hosted provider or a local server."""

    kind: ServerKind
    base_url: str | None = None
    api_key_env: str | None = None
    private: bool
    max_parallel: int = Field(ge=1)

    @model_validator(mode="after")
    def _key_variable_and_address(self) -> ServerEntry:
        if self.api_key_env is None:
            self.api_key_env = _DEFAULT_KEY_ENV.get(self.kind)
        if self.kind == "openai-compatible" and not self.base_url:
            msg = "an openai-compatible server needs a base_url"
            raise ValueError(msg)
        return self


class RoleEntry(_Strict):
    """Which model does a role's work, on which server, with optional sampling overrides."""

    model: str
    server: str
    temperature: float | None = None
    max_output_tokens: int | None = Field(default=None, ge=1)
    top_p: float | None = None
    top_k: int | None = None

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


class Sampling(_Strict):
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None


class ModelFacts(_Strict):
    """Facts about a model the shipped catalogue lacks or gets wrong."""

    context: int | None = Field(default=None, ge=1)
    max_output: int | None = Field(default=None, ge=1)
    tool_calls: bool | None = None
    sampling: Sampling | None = None


class BrakeValues(_Strict):
    """Check-in intervals per run. Values only: how the brake behaves is the spend brake's job."""

    hosted_chf_per_run: float = Field(default=20, gt=0)
    local_gpu_hours_per_run: float = Field(default=2, gt=0)
    agent_turns: int = Field(default=10, ge=1)


class Currency(_Strict):
    usd_to_chf: float = Field(gt=0)
    rate_date: date


class MachineLlmFile(_Strict):
    """`~/.specweaver/settings.toml`."""

    schema_version: int = SCHEMA_VERSION
    currency: Currency | None = None
    servers: dict[str, ServerEntry] = Field(default_factory=dict)
    roles: dict[RoleName, RoleEntry] = Field(default_factory=dict)
    brake: BrakeValues = Field(default_factory=BrakeValues)
    models: dict[str, ModelFacts] = Field(default_factory=dict)


class ProjectLlmSection(_Strict):
    """The `[llm]` section of a project's `specweaver.toml`: choices only."""

    private_only: bool = False
    roles: dict[RoleName, RoleEntry] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_machine_file(text: str, source: str) -> MachineLlmFile:
    """The machine settings file, or `SettingsFileError` naming what is wrong and where."""
    data = _load_toml(text, source)
    version = data.get("schema_version", SCHEMA_VERSION)
    if isinstance(version, int) and version > SCHEMA_VERSION:
        raise SettingsFileError(
            source,
            "schema_version",
            _line_of(text, ("schema_version",)),
            f"written for settings schema {version}; this SpecWeaver reads {SCHEMA_VERSION} — "
            "upgrade SpecWeaver",
        )
    return _validate(MachineLlmFile, data, text, source, prefix=())


def parse_project_llm(text: str, source: str) -> ProjectLlmSection:
    """A project's `[llm]` section; an absent section is an empty choice."""
    section = _load_toml(text, source).get("llm", {})
    forbidden = _find_machine_only_key(section, ("llm",))
    if forbidden:
        raise SettingsFileError(
            source,
            ".".join(forbidden),
            _line_of(text, forbidden),
            "a project may choose models, not define where code is sent — set servers, "
            "addresses and key variables in the machine settings file",
        )
    return _validate(ProjectLlmSection, section, text, source, prefix=("llm",))


def _load_toml(text: str, source: str) -> dict[str, Any]:
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        # `lineno` exists only from Python 3.14; before that the line is in the message.
        found = re.search(r"line (\d+)", str(exc))
        line = int(found.group(1)) if found else 1
        raise SettingsFileError(source, "(syntax)", line, "not valid TOML") from exc


def _validate(
    model: type[_M], data: dict[str, Any], text: str, source: str, *, prefix: tuple[str, ...]
) -> _M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        # An unknown key first: a typo also shows up as the real key "missing", and the typo is
        # the line the user has to fix.
        errors = sorted(exc.errors(), key=lambda error: error["type"] != "extra_forbidden")
        first = errors[0]
        loc = prefix + tuple(str(part) for part in first["loc"] if part != "[key]")
        # The message only: pydantic's `input` would echo the value, which may be a secret.
        raise SettingsFileError(source, ".".join(loc), _line_of(text, loc), first["msg"]) from None


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
# Locating a key path in the source text
# ---------------------------------------------------------------------------
#
# Neither `tomllib` nor `tomlkit` reports where a key sits, so the line is found by scanning: the
# deepest table header that is a prefix of the key path, then the first line in that table that
# assigns the next key — which covers inline tables, whose keys share their parent's line.

_HEADER = re.compile(r"^\s*\[+\s*(.+?)\s*\]+\s*(#.*)?$")
_PART = re.compile(r'"([^"]*)"|\'([^\']*)\'|([^.\s]+)')


def _header_parts(raw: str) -> tuple[str, ...]:
    return tuple(next(g for g in match.groups() if g is not None) for match in _PART.finditer(raw))


def _line_of(text: str, path: tuple[str, ...]) -> int:
    lines = text.splitlines()
    tables = _tables(lines)
    for start, parts in sorted(tables, key=lambda table: -len(table[1])):
        if path[: len(parts)] == parts:
            end = min((s for s, _ in tables if s > start), default=len(lines) + 1)
            return _line_in_table(lines, start, end, path[len(parts) :])
    return 1


def _tables(lines: list[str]) -> list[tuple[int, tuple[str, ...]]]:
    """Every table header as (line number, key parts); the top level is (0, ())."""
    tables: list[tuple[int, tuple[str, ...]]] = [(0, ())]
    for index, line in enumerate(lines):
        header = _HEADER.match(line)
        if header:
            tables.append((index + 1, _header_parts(header.group(1))))
    return tables


def _line_in_table(lines: list[str], start: int, end: int, rest: tuple[str, ...]) -> int:
    """The line assigning `rest[0]` inside a table, else the table's own line."""
    if rest:
        assign = re.compile(rf"^\s*[\"']?{re.escape(rest[0])}[\"']?\s*=")
        for number in range(start + 1, end):
            if assign.match(lines[number - 1]):
                return number
    return max(start, 1)
