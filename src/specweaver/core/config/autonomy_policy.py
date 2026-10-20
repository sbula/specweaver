# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How far agentic work may go in a project, as its `specweaver.toml` says in `[autonomy]`.

`mode` is the project's default for its generate steps; a step may say otherwise. `agentic_max_dal`
is the riskiest DAL an agentic step may run at; there is none until the project names one, and
then no step runs agentic. The decision itself is the engine's (`core.flow.engine.autonomy`).
"""

from __future__ import annotations

import re
import tomllib
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.core.config.toml_lines import path_line


class AutonomyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["oneshot", "agentic"] = "oneshot"
    agentic_max_dal: DALLevel | None = None


def parse_autonomy(text: str, source: str) -> AutonomyPolicy:
    """The `[autonomy]` section of a project's settings text; an absent section is the empty policy."""
    try:
        section = tomllib.loads(text).get("autonomy", {})
    except tomllib.TOMLDecodeError as exc:
        found = re.search(r"line (\d+)", str(exc))
        raise SettingsFileError(
            source, "(syntax)", int(found.group(1)) if found else 1, "not valid TOML"
        ) from None
    try:
        return AutonomyPolicy.model_validate(section)
    except ValidationError as exc:
        errors = sorted(exc.errors(), key=lambda error: error["type"] != "extra_forbidden")
        loc = ("autonomy", *(str(part) for part in errors[0]["loc"]))
        raise SettingsFileError(
            source, ".".join(loc), path_line(text, loc), errors[0]["msg"]
        ) from None
