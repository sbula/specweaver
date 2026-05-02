# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pipeline YAML loader -- loads and resolves ValidationPipeline from YAML.

Searches in order:
1. Project-local: ``{project}/.specweaver/pipelines/{name}.yaml``
2. Packaged defaults: ``specweaver/pipelines/{name}.yaml``

Applies inheritance resolution (extends/override/remove/add) before
returning the final pipeline.
"""

from __future__ import annotations

import importlib.resources
import io
import logging
from pathlib import Path  # noqa: TC003  -- used at runtime
from typing import Any, cast

from ruamel.yaml import YAML

from specweaver.assurance.validation.inheritance import resolve_pipeline
from specweaver.assurance.validation.pipeline import ValidationPipeline

logger = logging.getLogger(__name__)

_yaml = YAML(typ="safe")


def load_pipeline_yaml(
    name: str,
    *,
    project_dir: Path | None = None,
) -> ValidationPipeline:
    """Load a validation pipeline by name, resolving inheritance.

    Search order:
        1. ``{project_dir}/.specweaver/pipelines/{name}.yaml``
        2. Packaged ``specweaver/pipelines/{name}.yaml``

    Args:
        name: Pipeline name (e.g. 'validation_spec_default').
        project_dir: Project root for local overrides.

    Returns:
        Fully resolved ValidationPipeline (no inheritance markers).

    Raises:
        FileNotFoundError: If the pipeline YAML is not found.
    """
    logger.debug("load_pipeline_yaml called for name=%s", name)
    raw = _load_raw_yaml(name, project_dir=project_dir)
    pipeline = ValidationPipeline(**raw)

    if pipeline.extends:
        pipeline = resolve_pipeline(
            pipeline,
            base_loader=lambda base_name: load_pipeline_yaml(
                base_name,
                project_dir=project_dir,
            ),
        )

    return pipeline


def _load_raw_yaml(
    name: str,
    *,
    project_dir: Path | None = None,
) -> dict[str, Any]:
    """Load raw YAML dict for a pipeline by name."""
    # 1. Project-local override
    if project_dir:
        local_path = project_dir / ".specweaver" / "pipelines" / f"{name}.yaml"
        if local_path.is_file():
            logger.debug("Loading pipeline '%s' from project: %s", name, local_path)
            text = local_path.read_text(encoding="utf-8")
            return cast("dict[str, Any]", _yaml.load(io.StringIO(text)))

    # 2. Packaged default
    try:
        files = importlib.resources.files("specweaver.workflows.pipelines")
        resource = files.joinpath(f"{name}.yaml")
        if resource.is_file():
            text = resource.read_text(encoding="utf-8")
            logger.debug("Loading pipeline '%s' from package", name)
            return cast("dict[str, Any]", _yaml.load(io.StringIO(text)))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        pass

    # 3. Framework Plugins
    try:
        frameworks_dir = importlib.resources.files("specweaver.workflows.pipelines.frameworks")
        for framework_pkg in frameworks_dir.iterdir():
            if framework_pkg.is_dir() and framework_pkg.name != "__pycache__":
                resource = framework_pkg.joinpath(f"{name}.yaml")
                if resource.is_file():
                    text = resource.read_text(encoding="utf-8")
                    logger.debug(
                        "Loading pipeline '%s' from framework %s", name, framework_pkg.name
                    )
                    return cast("dict[str, Any]", _yaml.load(io.StringIO(text)))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        pass

    msg = f"Validation pipeline '{name}' not found. Searched in: packaged defaults, frameworks"
    if project_dir:
        msg += f", {project_dir / '.specweaver' / 'pipelines'}"
    raise FileNotFoundError(msg)


def resolve_pipeline_name(
    level: str,
    pipeline: str | None = None,
    *,
    active_profile: str | None = None,
) -> str:
    """Resolve the validation pipeline YAML name from level and context.

    Precedence (highest to lowest):
    1. ``pipeline`` — explicit override, always wins.
    2. ``level='feature'`` — always uses feature pipeline, ignores profile.
    3. Active project domain profile — auto-selects profile pipeline YAML.
    4. ``level='component'`` / ``level='code'`` — default YAML.

    Args:
        level: One of 'feature', 'component', 'code'.
        pipeline: Explicit pipeline name override.
        active_profile: The name of the active project's domain profile.

    Returns:
        Resolved pipeline name (e.g. 'validation_spec_default').

    Raises:
        ValueError: If the level is unknown.
    """
    logger.debug("resolve_pipeline_name: level=%s, pipeline=%s", level, pipeline)
    if pipeline:
        return pipeline
    if level == "feature":
        return "validation_spec_feature"
    if level == "code":
        return "validation_code_default"
    if level == "component":
        # Check for an active domain profile
        if active_profile:
            from specweaver.core.config.profiles import profile_to_pipeline_name

            return profile_to_pipeline_name(active_profile)
        return "validation_spec_default"
    logger.warning("resolve_pipeline_name: unknown level '%s'", level)
    msg = f"Unknown validation level '{level}'. Use 'feature', 'component', or 'code'."
    raise ValueError(msg)
