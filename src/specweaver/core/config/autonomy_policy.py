# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How far agentic work may go in a project, as its `specweaver.toml` says in `[autonomy]`.

`mode` is the project's default for its generate steps; a step may say otherwise. `agentic_max_dal`
is the riskiest DAL an agentic step may run at; there is none until the project names one, and
then no step runs agentic. The decision itself is the engine's (`core.flow.engine.autonomy`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from specweaver.commons.enums.dal import DALLevel
from specweaver.core.config.settings_file import parse_section


class AutonomyPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    mode: Literal["oneshot", "agentic"] = "oneshot"
    agentic_max_dal: DALLevel | None = None


def parse_autonomy(text: str, source: str) -> AutonomyPolicy:
    """The `[autonomy]` section of a project's settings text; an absent section is the empty policy."""
    return parse_section(text, source, "autonomy", AutonomyPolicy)
