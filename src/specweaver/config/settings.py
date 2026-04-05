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

import logging
import os
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

from specweaver.config.dal import DALLevel  # noqa: TC001

if TYPE_CHECKING:
    from specweaver.config.database import Database

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


class SpecWeaverSettings(BaseModel):
    """Root configuration object spanning all domains."""

    llm: LLMSettings
    stitch: StitchSettings = StitchSettings()
    validation: ValidationSettings = ValidationSettings()
    dal_matrix: DALImpactMatrix = DALImpactMatrix()


def load_settings(
    db: Database,
    project_name: str,
    *,
    llm_role: str = "review",
) -> SpecWeaverSettings:
    """Load settings for a project from the database.

    Loads the database variables, plus optionally loads and deep merges
    `.specweaver/dal_definitions.yaml` for DAL matrices.

    Args:
        db: Database instance.
        project_name: Name of the project to load config for.
        llm_role: Which LLM profile role to use (default: "review").

    Returns:
        Fully resolved settings with API key from environment.

    Raises:
        ValueError: If project is not registered.
    """
    logger.debug("load_settings called for project=%s, role=%s", project_name, llm_role)
    proj = db.get_project(project_name)
    if not proj:
        logger.error("Project '%s' not found in database", project_name)
        msg = f"Project '{project_name}' not found"
        raise ValueError(msg)

    profile = db.get_project_profile(project_name, llm_role)

    if not profile:
        logger.info(
            "No profile for project=%s role=%s, falling back to system-default",
            project_name,
            llm_role,
        )
        profile = db.get_llm_profile_by_name("system-default")

    if not profile:
        logger.error(
            "System default profile not found; cannot load settings for '%s'", project_name
        )
        msg = f"System default profile not found in database. Cannot load settings for '{project_name}'."
        raise ValueError(msg)

    provider_val = str(profile.get("provider", "gemini"))
    env_key = f"{provider_val.upper()}_API_KEY"
    logger.debug("Resolved provider=%s for project=%s", provider_val, project_name)

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

    # -------------------------------------------------------------
    # Feature 3.20b: DAL Impact Matrix Loading and Merging
    # -------------------------------------------------------------
    from pathlib import Path

    dal_matrix = DALImpactMatrix()

    # We resolve the project root path
    root_path = proj.get("root_path")
    if root_path and isinstance(root_path, str):
        dal_file = Path(root_path) / ".specweaver" / "dal_definitions.yaml"
        if dal_file.exists():
            from ruamel.yaml import YAML

            yaml_parser = YAML(typ="safe")
            try:
                dal_dict = yaml_parser.load(dal_file) or {}
                # Assume empty internal base definition, deep_merge over it
                merged_dal_dict = deep_merge_dict({}, dal_dict)
                # Hydrate the model
                dal_matrix = DALImpactMatrix(**merged_dal_dict)
                logger.debug("Loaded DAL configuration from %s", dal_file)
            except Exception:
                logger.exception("Failed to parse dal_definitions.yaml at %s", dal_file)

    return SpecWeaverSettings(llm=llm, stitch=stitch, dal_matrix=dal_matrix)


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
    logger.debug("load_settings_for_active called with role=%s", llm_role)
    active = db.get_active_project()
    if not active:
        logger.error("No active project found")
        msg = "No active project. Run 'sw init <name> --path <path>' first."
        raise ValueError(msg)
    logger.debug("Active project resolved to '%s'", active)
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

    logger.debug("migrate_legacy_config called for project=%s, path=%s", project_name, project_path)
    config_file = Path(project_path) / ".specweaver" / "config.yaml"
    if not config_file.is_file():
        logger.debug("No legacy config.yaml found at %s", config_file)
        return False

    # Check if project already exists (before parsing)
    existing = db.get_project(project_name)
    if existing:
        logger.error("Project '%s' already exists in database", project_name)
        msg = f"Project '{project_name}' already exists"
        raise ValueError(msg)

    # Parse legacy YAML
    yaml = YAML()
    try:
        data = yaml.load(config_file)
    except YAMLError:
        logger.exception("Failed to parse legacy config at %s", config_file)
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

    logger.info(
        "Migrated legacy config for project '%s' (provider=%s, model=%s)",
        project_name,
        provider,
        model,
    )
    return True
