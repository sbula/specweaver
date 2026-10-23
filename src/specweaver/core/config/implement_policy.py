# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The language a project's code is written in, as its `specweaver.toml` says in `[implement]`.

None means the project names none, and its manifests decide (`sandbox.language`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from specweaver.core.config.settings_file import parse_section

Language = Literal["python", "java", "kotlin", "typescript", "rust"]


class ImplementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: Language | None = None


def parse_implement(text: str, source: str) -> ImplementPolicy:
    """The `[implement]` section of a project's settings text; an absent section names nothing."""
    return parse_section(text, source, "implement", ImplementPolicy)
