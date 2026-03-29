# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""SpecWeaver configuration loading.

Settings are loaded from:
1. SQLite database at ~/.specweaver/specweaver.db (project config, LLM profiles)
2. Environment variables (GEMINI_API_KEY — secrets never in DB)
3. Built-in defaults (when no DB profile is linked)

Legacy support: .specweaver/config.yaml in a project can be migrated
into the DB via migrate_legacy_config().
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

if TYPE_CHECKING:
    from specweaver.config.database import Database


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


class StitchSettings(BaseModel):
    """Stitch UI mockup generation configuration."""

    mode: Literal["auto", "prompt", "off"] = "off"
    api_key: str = ""


class SpecWeaverSettings(BaseModel):
    """Root configuration object spanning all domains."""

    llm: LLMSettings
    stitch: StitchSettings = StitchSettings()
    validation: ValidationSettings = ValidationSettings()


def load_settings(
    db: Database,
    project_name: str,
    *,
    llm_role: str = "review",
) -> SpecWeaverSettings:
    """Load settings for a project from the database.

    Args:
        db: Database instance.
        project_name: Name of the project to load config for.
        llm_role: Which LLM profile role to use (default: "review").

    Returns:
        Fully resolved settings with API key from environment.

    Raises:
        ValueError: If project is not registered.
    """
    proj = db.get_project(project_name)
    if not proj:
        msg = f"Project '{project_name}' not found"
        raise ValueError(msg)

    profile = db.get_project_profile(project_name, llm_role)

    if not profile:
        profile = db.get_llm_profile_by_name("system-default")

    if not profile:
        msg = f"System default profile not found in database. Cannot load settings for '{project_name}'."
        raise ValueError(msg)

    provider_val = str(profile.get("provider", "gemini"))
    env_key = f"{provider_val.upper()}_API_KEY"

    llm = LLMSettings(
        model=str(profile["model"]),
        temperature=float(profile["temperature"]),  # type: ignore[arg-type]
        max_output_tokens=int(str(profile["max_output_tokens"])),
        response_format=str(profile["response_format"]),  # type: ignore[arg-type]
        provider=provider_val,
        api_key=os.environ.get(env_key, ""),
    )

    stitch_mode = db.get_stitch_mode(project_name)
    stitch = StitchSettings(
        mode=stitch_mode,  # type: ignore[arg-type]
        api_key=os.environ.get("STITCH_API_KEY", ""),
    )

    return SpecWeaverSettings(llm=llm, stitch=stitch)


def load_settings_for_active(
    db: Database,
    *,
    llm_role: str = "review",
) -> SpecWeaverSettings:
    """Load settings for the currently active project.

    Args:
        db: Database instance.
        llm_role: Which LLM profile role to use.

    Returns:
        Fully resolved settings.

    Raises:
        ValueError: If no project is active.
    """
    active = db.get_active_project()
    if not active:
        msg = "No active project. Run 'sw init <name> --path <path>' first."
        raise ValueError(msg)
    return load_settings(db, active, llm_role=llm_role)


def migrate_legacy_config(
    db: Database,
    project_name: str,
    project_path: str,
) -> bool:
    """Migrate a legacy .specweaver/config.yaml into the database.

    Reads the YAML, creates a project-specific LLM profile from the
    values, registers the project, and links the profile for all roles.

    Args:
        db: Database instance.
        project_name: Name to register the project as.
        project_path: Root directory of the project.

    Returns:
        True if migration was performed, False if no config.yaml found.

    Raises:
        ValueError: If project name already exists in DB.
    """
    from pathlib import Path

    from ruamel.yaml import YAML

    try:
        from ruamel.yaml import YAMLError  # type: ignore[attr-defined]
    except ImportError:
        YAMLError = Exception  # noqa: N806

    config_file = Path(project_path) / ".specweaver" / "config.yaml"
    if not config_file.is_file():
        return False

    # Check if project already exists (before parsing)
    existing = db.get_project(project_name)
    if existing:
        msg = f"Project '{project_name}' already exists"
        raise ValueError(msg)

    # Parse legacy YAML
    yaml = YAML()
    try:
        data = yaml.load(config_file)
    except YAMLError:
        data = {}

    if not isinstance(data, dict):
        data = {}

    llm_raw = data.get("llm", {})
    if not isinstance(llm_raw, dict):
        llm_raw = {}

    # Register project
    db.register_project(project_name, project_path)

    sys_profile = db.get_llm_profile_by_name("system-default")
    if not sys_profile:
        raise ValueError("Database missing system-default profile.")

    model = llm_raw.get("model", str(sys_profile["model"]))
    temperature = llm_raw.get("temperature", 0.7)
    max_tokens = llm_raw.get("max_output_tokens", 4096)
    resp_format = llm_raw.get("response_format", "text")
    provider = llm_raw.get("provider", str(sys_profile.get("provider", "gemini")))

    profile_id = db.create_llm_profile(
        name="legacy-import",
        is_global=False,
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        response_format=resp_format,
        provider=provider,
    )

    # Link this profile for all standard roles
    for role in ("review", "draft", "search"):
        db.link_project_profile(project_name, role, profile_id)

    return True
