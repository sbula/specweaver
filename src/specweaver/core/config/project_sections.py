# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Reads one table of a project's `specweaver.toml` into a strict model, naming the line of an error."""

from __future__ import annotations

import re
import tomllib
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.core.config.toml_lines import path_line

_Section = TypeVar("_Section", bound=BaseModel)


def parse_section(text: str, source: str, name: str, model: type[_Section]) -> _Section:
    """The `[name]` table of the settings text as `model`; an absent table is the model's defaults."""
    try:
        section = tomllib.loads(text).get(name, {})
    except tomllib.TOMLDecodeError as exc:
        found = re.search(r"line (\d+)", str(exc))
        raise SettingsFileError(
            source, "(syntax)", int(found.group(1)) if found else 1, "not valid TOML"
        ) from None
    try:
        return model.model_validate(section)
    except ValidationError as exc:
        errors = sorted(exc.errors(), key=lambda error: error["type"] != "extra_forbidden")
        loc = (name, *(str(part) for part in errors[0]["loc"]))
        raise SettingsFileError(
            source, ".".join(loc), path_line(text, loc), errors[0]["msg"]
        ) from None
