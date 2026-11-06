# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The language and build tool a project pins in its `specweaver.toml` `[implement]` section.

None means the project pins none; its root decides (`commons.project_profile`).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from specweaver.commons.project_profile import BUILD_TOOLS, GENERATED_LANGUAGES
from specweaver.core.config.settings_file import parse_section


class ImplementPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    language: str | None = None
    build_tool: str | None = None

    @field_validator("language")
    @classmethod
    def _a_generated_language(cls, value: str | None) -> str | None:
        return _one_of(value, GENERATED_LANGUAGES)

    @field_validator("build_tool")
    @classmethod
    def _a_build_tool(cls, value: str | None) -> str | None:
        return _one_of(value, BUILD_TOOLS)


def _one_of(value: str | None, allowed: tuple[str, ...]) -> str | None:
    if value is not None and value not in allowed:
        msg = f"must be one of {', '.join(allowed)}"
        raise ValueError(msg)
    return value


def parse_implement(text: str, source: str) -> ImplementPolicy:
    """The `[implement]` section of a project's settings text; an absent section names nothing."""
    return parse_section(text, source, "implement", ImplementPolicy)
