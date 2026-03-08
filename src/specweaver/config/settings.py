# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SpecWeaver configuration loading.

Settings are loaded from multiple sources with the following priority:
1. Environment variables (GEMINI_API_KEY, etc.)
2. .env file (auto-loaded by Pydantic BaseSettings)
3. .specweaver/config.yaml (project-specific, non-secrets only)
4. Built-in defaults
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML, YAMLError

if TYPE_CHECKING:
    from pathlib import Path


class LLMSettings(BaseModel):
    """LLM-related configuration."""

    model: str = "gemini-2.5-flash"
    temperature: float = 0.7
    max_output_tokens: int = 4096
    response_format: Literal["text", "json"] = "text"
    api_key: str = ""


class SpecWeaverSettings(BaseModel):
    """Root settings model for SpecWeaver."""

    llm: LLMSettings = LLMSettings()


def load_settings(project_path: Path) -> SpecWeaverSettings:
    """Load SpecWeaver settings from config.yaml + env vars.

    Args:
        project_path: Root directory of the target project.

    Returns:
        Fully resolved settings with defaults for missing values.

    Raises:
        ValueError: If config.yaml exists but is malformed or contains
            invalid values.
    """
    config_file = project_path / ".specweaver" / "config.yaml"
    raw: dict = {}  # type: ignore[type-arg]

    if config_file.is_file():
        try:
            yaml = YAML()
            loaded = yaml.load(config_file)
            if isinstance(loaded, dict):
                raw = loaded
            # None/null YAML → use empty dict (defaults)
        except YAMLError as exc:
            msg = f"Failed to parse .specweaver/config.yaml: {exc}"
            raise ValueError(msg) from exc

    # Build nested settings from YAML data
    llm_raw = raw.get("llm", {})
    if not isinstance(llm_raw, dict):
        llm_raw = {}

    # Overlay env vars for secrets (API key)
    api_key = os.environ.get("GEMINI_API_KEY", "")

    try:
        llm = LLMSettings(api_key=api_key, **llm_raw)
    except ValidationError as exc:
        msg = f"Invalid values in .specweaver/config.yaml: {exc}"
        raise ValueError(msg) from exc

    return SpecWeaverSettings(llm=llm)
