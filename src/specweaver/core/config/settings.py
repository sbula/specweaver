# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""SpecWeaver configuration loading.

Settings are loaded from:
1. SQLite database at ~/.specweaver/specweaver.db (project config, LLM profiles)
2. Environment variables (GEMINI_API_KEY — secrets never in DB)
3. Built-in defaults (when no DB profile is linked)

Legacy support: .specweaver/config.yaml in a project can be migrated
into the DB via migrate_legacy_config().
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Literal

import anyio
from pydantic import BaseModel, ConfigDict

from specweaver.commons.enums.dal import DALLevel  # noqa: TC001
from specweaver.infrastructure.llm.store import LlmRepository

if TYPE_CHECKING:
    from specweaver.core.config.database import Database

logger = logging.getLogger(__name__)


def deep_merge_dict(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively deeply merges the overlay dictionary into a copy of the base dictionary.

    Keys in overlay overwrite keys in base. If both values are dictionaries,
    the merge is performed recursively. List elements are wholly overwritten.

    Args:
        base: The fundamental dictionary.
        overlay: The dictionary to overlay on top.

    Returns:
        A new nested dictionary with the merged results.
    """
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge_dict(merged[key], value)
        else:
            merged[key] = value
    return merged


class LLMSettings(BaseModel):
    """LLM-related configuration."""

    model: str
    temperature: float = 0.7
    max_output_tokens: int = 4096
    response_format: Literal["text", "json"] = "text"
    provider: str = "gemini"
    api_key: str = ""


class RuleOverride(BaseModel):
    """Per-rule validation override for a project.

    Any field left as None means "use the rule's built-in default".
    ``extra_params`` holds rule-specific parameters that don't fit the
    standard warn/fail pattern (e.g. S01's ``max_h2``).
    """

    rule_id: str
    enabled: bool = True
    warn_threshold: float | None = None
    fail_threshold: float | None = None
    extra_params: dict[str, float] = {}


class ValidationSettings(BaseModel):
    """Container for all validation overrides for a project."""

    overrides: dict[str, RuleOverride] = {}

    def get_override(self, rule_id: str) -> RuleOverride | None:
        """Get the override for a specific rule, or None if not set."""
        return self.overrides.get(rule_id)

    def is_enabled(self, rule_id: str) -> bool:
        """Check if a rule is enabled. Defaults to True if no override."""
        override = self.get_override(rule_id)
        return override.enabled if override else True


class DALImpactMatrix(BaseModel):
    """A risk-based FFI override matrix.

    Maps each risk tier (DALLevel) to discrete ValidationSettings overrides.
    """

    model_config = ConfigDict(use_enum_values=False)

    matrix: dict[DALLevel, ValidationSettings] = {}


class StitchSettings(BaseModel):
    """Stitch UI mockup generation configuration."""

    mode: Literal["auto", "prompt", "off"] = "off"
    api_key: str = ""


class StandardsSettings(BaseModel):
    """Standards auto-discovery behavioral configurations."""

    mode: Literal["mimicry", "best_practice"] = "mimicry"


class SpecWeaverSettings(BaseModel):
    """Root configuration object spanning all domains."""

    llm: LLMSettings
    stitch: StitchSettings = StitchSettings()
    validation: ValidationSettings = ValidationSettings()
    dal_matrix: DALImpactMatrix = DALImpactMatrix()
    standards: StandardsSettings = StandardsSettings()


