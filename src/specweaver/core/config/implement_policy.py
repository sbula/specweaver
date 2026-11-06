# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The language and build tool a project pins in its `specweaver.toml` `[implement]` section.

None means the project pins none; its root decides (`commons.project_profile`).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from specweaver.core.config.settings_file import parse_section

Language = Literal["python", "java", "kotlin", "typescript", "rust"]
BuildTool = Literal["uv", "maven", "gradle", "cargo", "npm"]


class ImplementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: Language | None = None
    build_tool: BuildTool | None = None


def parse_implement(text: str, source: str) -> ImplementPolicy:
    """The `[implement]` section of a project's settings text; an absent section names nothing."""
    return parse_section(text, source, "implement", ImplementPolicy)
