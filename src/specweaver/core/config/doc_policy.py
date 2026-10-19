# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which docs agents may change, as a project says in the `[docs]` section of its `specweaver.toml`.

A rule gives paths one access: `human` (no agent changes them), `open` (any agent step may) or
`step` (only the named pipeline steps may). A block names a marked region of a file that one `bash`
step fills. The decision itself is the sandbox's (`sandbox.security.doc_access`).
"""

from __future__ import annotations

import re
import tomllib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator

from specweaver.core.config.llm_settings import SettingsFileError

Access = Literal["human", "open", "step"]
_BLOCK_NAME = re.compile(r"[a-z0-9_-]+")


def _inside(entry: str) -> str:
    parts = entry.replace("\\", "/").split("/")
    if not entry.strip() or entry.startswith(("/", "\\")) or entry[1:2] == ":" or ".." in parts:
        msg = f"{entry!r} must be a path inside the project"
        raise ValueError(msg)
    return entry


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DocRule(_Strict):
    paths: list[str] = Field(min_length=1)
    access: Access
    #: Checked even when absent: a `step` rule without steps is the error.
    steps: list[str] = Field(default_factory=list, validate_default=True)

    @field_validator("paths")
    @classmethod
    def _paths_inside(cls, paths: list[str]) -> list[str]:
        return [_inside(path) for path in paths]

    @field_validator("steps")
    @classmethod
    def _steps_with_step_access(cls, steps: list[str], info: ValidationInfo) -> list[str]:
        access = info.data.get("access")
        if access == "step" and not steps:
            raise ValueError('access = "step" names the steps that may change these paths')
        if access != "step" and steps:
            raise ValueError('steps belong to access = "step" only')
        return steps


class DocBlock(_Strict):
    file: str
    name: str
    step: str

    @field_validator("file")
    @classmethod
    def _file_inside(cls, file: str) -> str:
        return _inside(file)

    @field_validator("name")
    @classmethod
    def _plain_name(cls, name: str) -> str:
        if not _BLOCK_NAME.fullmatch(name):
            raise ValueError("a block name is lower-case letters, digits, '-' and '_'")
        return name


class DocPolicy(_Strict):
    rule: list[DocRule] = Field(default_factory=list)
    block: list[DocBlock] = Field(default_factory=list)


def parse_doc_policy(text: str, source: str) -> DocPolicy:
    """The `[docs]` section of a project's settings text; an absent section is an empty policy."""
    try:
        section = tomllib.loads(text).get("docs", {})
    except tomllib.TOMLDecodeError as exc:
        raise SettingsFileError(
            source, "(file)", getattr(exc, "lineno", 0), "not valid TOML"
        ) from None
    try:
        return DocPolicy.model_validate(section)
    except ValidationError as exc:
        errors = sorted(exc.errors(), key=lambda error: error["type"] != "extra_forbidden")
        loc = tuple(str(part) for part in errors[0]["loc"])
        message = errors[0]["msg"].removeprefix("Value error, ")
        raise SettingsFileError(
            source, ".".join(("docs", *loc)), _line(text, loc), message
        ) from None


def _line(text: str, loc: tuple[str, ...]) -> int:
    """The line of `docs.<table>.<index>.<key>`: the key inside the index-th `[[docs.<table>]]`,
    else that header's line, else 1."""
    if len(loc) < 2 or not loc[1].isdigit():
        return 1
    table, index, key = loc[0], int(loc[1]), loc[2] if len(loc) > 2 else None
    header = re.compile(rf"^\s*\[\[\s*docs\.{re.escape(table)}\s*\]\]")
    lines = text.splitlines()
    starts = [number for number, line in enumerate(lines, start=1) if header.match(line)]
    if index >= len(starts):
        return 1
    start = starts[index]
    if key is not None:
        assign = re.compile(rf"^\s*{re.escape(key)}\s*=")
        for number in range(start + 1, len(lines) + 1):
            line = lines[number - 1]
            if line.lstrip().startswith("["):
                break
            if assign.match(line):
                return number
    return start
