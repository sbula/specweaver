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
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

if TYPE_CHECKING:
    from collections.abc import Iterable

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
    "qwen": "DASHSCOPE_API_KEY",
}

#: Kinds with no single official address: a local server, and DashScope, whose current addresses
#: carry the account's workspace.
_NEEDS_ADDRESS = frozenset({"openai-compatible", "qwen"})

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
        if self.kind in _NEEDS_ADDRESS and not self.base_url:
            msg = f"a {self.kind} server needs a base_url"
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
    """Facts about one model. The shipped catalogue holds them; the machine file corrects them."""

    context: int | None = Field(default=None, ge=1)
    max_output: int | None = Field(default=None, ge=1)
    tool_calls: bool | None = None
    usd_per_million_input: float | None = Field(default=None, ge=0)
    usd_per_million_output: float | None = Field(default=None, ge=0)
    #: One output limit also bounds the model's hidden thinking, so a call's cost has a ceiling.
    thinking_in_output_cap: bool | None = None
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

    @classmethod
    def from_texts(
        cls, *, machine_text: str, machine_source: str, project_text: str, project_source: str
    ) -> LlmSettingsFiles:
        return cls(
            machine=parse_machine_file(machine_text, machine_source),
            machine_source=machine_source,
            machine_text=machine_text,
            project=parse_project_llm(project_text, project_source),
            project_source=project_source,
            project_text=project_text,
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
            origin = source if text is None else f"{source}:{_line_of(text, (*prefix, role))}"
            if entry.server not in files.machine.servers:
                raise SettingsFileError(
                    source,
                    ".".join((*prefix, role)),
                    _line_of(text, (*prefix, role)) if text is not None else 0,
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
                _line_of(files.project_text, ("llm", "private_only")),
                f"the project allows private servers only, but role '{role}' uses "
                f"'{setting.server}', which is not private ({setting.origin['model']})",
            )


def _resolved(role: str, entry: RoleEntry, origin: str) -> ResolvedRole:
    values = {name: getattr(entry, name) for name in _SAMPLING_FIELDS}
    origins = {"model": origin, "server": origin}
    origins.update({name: origin for name, value in values.items() if value is not None})
    return ResolvedRole(role=role, model=entry.model, server=entry.server, origin=origins, **values)


def settings_report(
    files: LlmSettingsFiles, roles: dict[str, ResolvedRole]
) -> list[tuple[str, str, str]]:
    """Every effective LLM setting as (key, value, origin), for `sw config show`."""
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
                at.format(_line_of(files.machine_text, ("servers", name))),
            )
        )
    for role, resolved in sorted(roles.items()):
        rows.append(
            (f"roles.{role}", f"{resolved.model}@{resolved.server}", resolved.origin["model"])
        )
        for name in _SAMPLING_FIELDS:
            value = getattr(resolved, name)
            if value is not None:
                rows.append((f"roles.{role}.{name}", str(value), resolved.origin[name]))
    for name in BrakeValues.model_fields:
        set_here = name in machine.brake.model_fields_set
        origin = at.format(_line_of(files.machine_text, ("brake", name))) if set_here else BUILT_IN
        rows.append((f"brake.{name}", f"{getattr(machine.brake, name):g}", origin))
    if machine.currency is None:
        rows.append(("currency", "not set — costs are shown in USD", BUILT_IN))
    else:
        rate = f"{machine.currency.usd_to_chf:g} CHF per USD, dated {machine.currency.rate_date}"
        rows.append(("currency", rate, at.format(_line_of(files.machine_text, ("currency",)))))
    project = files.project
    if project.private_only:
        rows.append(
            (
                "llm.private_only",
                "true",
                f"{files.project_source}:{_line_of(files.project_text, ('llm', 'private_only'))}",
            )
        )
    return rows


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
