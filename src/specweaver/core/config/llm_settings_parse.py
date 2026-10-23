# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The LLM settings files parsed: text to models, layered machine file over project section.

Pure: text in, typed model out. Reading the files is `core.config.bootstrap`'s job.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from specweaver.core.config.llm_settings import (
    SCHEMA_VERSION,
    MachineLlmFile,
    ProjectLlmSection,
)
from specweaver.core.config.settings_file import SettingsFileError, load_toml, validate
from specweaver.core.config.toml_lines import path_line

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

#: Keys that decide where code is sent. Only the machine file may set them.
_MACHINE_ONLY_KEYS = frozenset({"servers", "base_url", "api_key_env"})

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
