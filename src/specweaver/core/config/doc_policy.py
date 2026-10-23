# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Which docs agents may change, as a project says in the `[docs]` section of its `specweaver.toml`.

A rule gives paths one access: `human` (no agent changes them), `open` (any agent step may) or
`step` (only the named pipeline steps may). A block names a marked region of a file that one `bash`
step fills. The decision itself is the sandbox's (`sandbox.security.doc_access`).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from specweaver.core.config.settings_file import SettingsFileError, load_toml, validate

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
    section = load_toml(text, source).get("docs", {})
    policy = validate(
        DocPolicy, section, text, source, prefix=("docs",), line_of=lambda t, loc: _line(t, loc[1:])
    )
    _one_block_each(policy, text, source)
    return policy


def _one_block_each(policy: DocPolicy, text: str, source: str) -> None:
    """A step fills one block, and a block is filled by one step."""
    steps: set[str] = set()
    places: set[tuple[str, str]] = set()
    for index, block in enumerate(policy.block):
        place = (block.file.lower(), block.name)
        clash = None
        if place in places:
            clash = ("name", f"{block.file} already has a block named {block.name!r}")
        elif block.step in steps:
            clash = ("step", f"step {block.step!r} already fills a block; a step fills one")
        if clash:
            loc = ("block", str(index), clash[0])
            raise SettingsFileError(source, ".".join(("docs", *loc)), _line(text, loc), clash[1])
        steps.add(block.step)
        places.add(place)


def _markers(name: str) -> tuple[str, str]:
    return f"<!-- sw:block {name} -->", f"<!-- sw:end {name} -->"


def _span(text: str, name: str) -> tuple[int, int] | None:
    """Where the block's body lies: after its start marker, up to its end marker."""
    start, end = _markers(name)
    if text.count(start) != 1 or text.count(end) != 1:
        return None
    first, last = text.index(start) + len(start), text.index(end)
    return (first, last) if first <= last else None


def fill_block(text: str, name: str, body: str) -> str:
    """`text` with the body of block `name` replaced by `body`, on its own lines."""
    start, end = _markers(name)
    if start in body or end in body:
        msg = f"the output holds a marker of its own block ({start} or {end})"
        raise ValueError(msg)
    span = _span(text, name)
    if span is None:
        msg = f"needs one {start} and, after it, one {end}"
        raise ValueError(msg)
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = body.rstrip("\r\n").splitlines()
    inner = newline.join(lines) + newline if lines else ""
    return text[: span[0]] + newline + inner + text[span[1] :]


def outside_blocks(text: str, names: list[str]) -> str:
    """`text` with the named blocks' bodies emptied; a block without its markers is left as it is."""
    for name in names:
        span = _span(text, name)
        if span is not None:
            text = text[: span[0]] + text[span[1] :]
    return text


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
