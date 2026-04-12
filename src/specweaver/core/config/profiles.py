# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Domain profiles — named validation pipeline presets for project domains.

A *profile* is simply a name that maps to a built-in or custom
YAML pipeline file (``validation_spec_<profile>.yaml``).  Applying a
profile does **not** write any DB overrides; it only stores the
pipeline name so that ``sw check`` auto-selects the matching YAML.

Two configuration layers are completely independent and must not be
confused:

1. **YAML pipeline** (profile) — controls which rules run and their
   base parameters.  Selected by ``sw config set-profile <name>``.
   Lives in ``specweaver/pipelines/`` or ``.specweaver/pipelines/``.

2. **DB overrides** (per-rule runtime tuning) — controlled by
   ``sw config set <RULE> --warn/--fail``.  Always applied on top of
   the pipeline, regardless of which profile is active.

Usage::

    from specweaver.core.config.profiles import list_profiles, profile_exists

    if profile_exists("web-app"):
        ...
    for p in list_profiles():
        print(p.name, p.description)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Profiles that are reserved for internal use and must never appear in
# the public listing (they are pipeline implementation details, not domains).
_RESERVED_PIPELINE_NAMES = frozenset({"default", "feature", "code"})

# Base name prefix used by all spec-level pipeline YAML files.
_PIPELINE_PREFIX = "validation_spec_"


@dataclass(frozen=True)
class DomainProfile:
    """A named domain profile backed by a YAML pipeline file.

    Attributes:
        name: Profile identifier (e.g. ``"web-app"``).
        description: Human-readable description from the YAML header.
    """

    name: str
    description: str


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------


def _builtin_pipelines_dir() -> Path:
    """Return the path to the built-in pipelines directory."""
    return Path(__file__).parent.parent.parent / "workflows" / "pipelines"


def _custom_pipelines_dir(project_dir: Path | None = None) -> Path | None:
    """Return the path to a project's custom pipelines directory, or None."""
    base = project_dir or Path.cwd()
    candidate = base / ".specweaver" / "pipelines"
    return candidate if candidate.is_dir() else None


def _extract_description(yaml_path: Path) -> str:
    """Extract the ``description`` field from a pipeline YAML file.

    Uses simple line-by-line parsing to avoid loading ruamel.yaml for
    every profile scan.  Returns an empty string if the field is absent.
    """
    try:
        for line in yaml_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("description:"):
                return stripped.removeprefix("description:").strip().strip("'\"")
    except OSError:
        logger.debug("Could not read pipeline YAML: %s", yaml_path)
    return ""


def _profile_name_from_yaml(path: Path) -> str | None:
    """Return the profile name derived from a pipeline YAML filename.

    Returns ``None`` for reserved names (default, feature, code).
    """
    stem = path.stem  # e.g. "validation_spec_web_app"
    if not stem.startswith(_PIPELINE_PREFIX):
        return None
    profile = stem[len(_PIPELINE_PREFIX) :]  # e.g. "web_app"
    profile_hyphen = profile.replace("_", "-")  # e.g. "web-app"
    if profile_hyphen in _RESERVED_PIPELINE_NAMES:
        return None
    return profile_hyphen


def _scan_profiles(project_dir: Path | None = None) -> list[DomainProfile]:
    """Scan built-in and custom pipeline directories for domain profiles.

    Args:
        project_dir: Optional project root for custom pipeline discovery.

    Returns:
        Sorted list of ``DomainProfile`` instances (alphabetically by name).
    """
    seen: dict[str, DomainProfile] = {}

    dirs: list[Path] = [_builtin_pipelines_dir()]
    custom = _custom_pipelines_dir(project_dir)
    if custom:
        dirs.append(custom)

    for d in dirs:
        for yaml_file in sorted(d.glob(f"{_PIPELINE_PREFIX}*.yaml")):
            name = _profile_name_from_yaml(yaml_file)
            if name is None:
                continue
            description = _extract_description(yaml_file)
            seen[name] = DomainProfile(name=name, description=description)

    logger.debug("Profile scan found %d profiles", len(seen))
    return sorted(seen.values(), key=lambda p: p.name)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def profile_exists(
    name: str,
    project_dir: Path | None = None,
) -> bool:
    """Return True if a profile pipeline YAML exists for ``name``.

    Args:
        name: Profile name (e.g. ``"web-app"``).
        project_dir: Optional project root for custom pipeline lookup.
    """
    logger.debug("profile_exists check for name=%s", name)
    return get_profile(name, project_dir=project_dir) is not None


def get_profile(
    name: str,
    project_dir: Path | None = None,
) -> DomainProfile | None:
    """Get a profile by name, or None if not found.

    Looks up built-in pipelines first, then custom project pipelines.

    Args:
        name: Profile name (e.g. ``"web-app"``).
        project_dir: Optional project root for custom pipeline lookup.
    """
    logger.debug("get_profile called for name=%s", name)
    if not name:
        return None
    normalised = name.lower().replace("_", "-")
    if normalised in _RESERVED_PIPELINE_NAMES:
        return None

    dirs: list[Path] = [_builtin_pipelines_dir()]
    custom = _custom_pipelines_dir(project_dir)
    if custom:
        dirs.append(custom)

    # Convert "web-app" → "web_app" for the filename
    stem_suffix = normalised.replace("-", "_")
    filename = f"{_PIPELINE_PREFIX}{stem_suffix}.yaml"

    for d in dirs:
        yaml_path = d / filename
        if yaml_path.exists():
            description = _extract_description(yaml_path)
            return DomainProfile(name=normalised, description=description)

    return None


def list_profiles(project_dir: Path | None = None) -> list[DomainProfile]:
    """Return all available profiles in alphabetical order.

    Includes built-in profiles and any custom profiles found under
    ``{project_dir}/.specweaver/pipelines/``.

    Args:
        project_dir: Optional project root for custom pipeline discovery.
    """
    logger.debug("list_profiles called")
    return _scan_profiles(project_dir)


def profile_to_pipeline_name(profile_name: str) -> str:
    """Convert a profile name to its YAML pipeline name.

    Args:
        profile_name: Profile name (e.g. ``"web-app"``).

    Returns:
        Pipeline name without ``.yaml`` (e.g. ``"validation_spec_web_app"``).
    """
    stem_suffix = profile_name.lower().replace("-", "_")
    return f"{_PIPELINE_PREFIX}{stem_suffix}"
