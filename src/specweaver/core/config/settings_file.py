# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Settings text to a strict model, or an error naming the file, key and line."""

from __future__ import annotations

import re
import tomllib
from typing import TYPE_CHECKING, Any, TypeVar

from pydantic import BaseModel, ValidationError

from specweaver.core.config.toml_lines import path_line

if TYPE_CHECKING:
    from collections.abc import Callable

_M = TypeVar("_M", bound=BaseModel)


class SettingsFileError(ValueError):
    """A settings file that cannot be used, located by file, key and line."""

    def __init__(self, source: str, key: str, line: int, message: str) -> None:
        self.source = source
        self.key = key
        self.line = line
        self.message = message
        super().__init__(f"{source}:{line}: {key}: {message}")


def load_toml(text: str, source: str) -> dict[str, Any]:
    """The parsed text, or `SettingsFileError` at the line of the syntax error."""
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        # `lineno` exists only from Python 3.14; before that the line is in the message.
        found = re.search(r"line (\d+)", str(exc))
        line = int(found.group(1)) if found else 1
        raise SettingsFileError(source, "(syntax)", line, "not valid TOML") from None


def validate(
    model: type[_M],
    data: Any,
    text: str,
    source: str,
    *,
    prefix: tuple[str, ...] = (),
    line_of: Callable[[str, tuple[str, ...]], int] = path_line,
) -> _M:
    """`data` as `model`, or `SettingsFileError` naming the first wrong key and its line."""
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        # An unknown key first: a typo also shows up as the real key "missing", and the typo is
        # the line the user has to fix.
        errors = sorted(exc.errors(), key=lambda error: error["type"] != "extra_forbidden")
        first = errors[0]
        loc = prefix + tuple(str(part) for part in first["loc"] if part != "[key]")
        # The message only: pydantic's `input` would echo the value, which may be a secret.
        message = first["msg"].removeprefix("Value error, ")
        raise SettingsFileError(source, ".".join(loc), line_of(text, loc), message) from None


def parse_section(text: str, source: str, name: str, model: type[_M]) -> _M:
    """The `[name]` table of the settings text as `model`; an absent table is the model's defaults."""
    return validate(model, load_toml(text, source).get(name, {}), text, source, prefix=(name,))
