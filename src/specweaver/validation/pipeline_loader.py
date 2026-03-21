# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

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

from specweaver.validation.inheritance import resolve_pipeline
from specweaver.validation.pipeline import ValidationPipeline

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
    raw = _load_raw_yaml(name, project_dir=project_dir)
    pipeline = ValidationPipeline(**raw)

    if pipeline.extends:
        pipeline = resolve_pipeline(
            pipeline,
            base_loader=lambda base_name: load_pipeline_yaml(
                base_name, project_dir=project_dir,
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
        files = importlib.resources.files("specweaver.pipelines")
        resource = files.joinpath(f"{name}.yaml")
        text = resource.read_text(encoding="utf-8")
        logger.debug("Loading pipeline '%s' from package", name)
        return cast("dict[str, Any]", _yaml.load(io.StringIO(text)))
    except (FileNotFoundError, ModuleNotFoundError, TypeError):
        pass

    msg = (
        f"Validation pipeline '{name}' not found. "
        f"Searched in: packaged defaults"
    )
    if project_dir:
        msg += f", {project_dir / '.specweaver' / 'pipelines'}"
    raise FileNotFoundError(msg)
