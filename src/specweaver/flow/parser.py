# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Pipeline parser — load pipeline definitions from YAML files.

Resolution order for ``load_pipeline()``:
1. If path exists on disk as-is → load directly
2. If path has no suffix, try ``<path>.yaml`` on disk
3. Check bundled templates via ``importlib.resources``
4. Raise ``FileNotFoundError``
"""

from __future__ import annotations

import importlib.resources
import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError
from ruamel.yaml import YAML

from specweaver.flow.models import PipelineDefinition

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from pathlib import Path


def load_pipeline(path: Path) -> PipelineDefinition:
    """Load a pipeline definition from a YAML file.

    Args:
        path: Path to a YAML file, or a pipeline name (e.g. "new_feature")
              which will be resolved against bundled templates.

    Returns:
        A validated PipelineDefinition.

    Raises:
        FileNotFoundError: If the pipeline file cannot be found.
        ValueError: If the YAML is invalid or doesn't match the schema.
    """
    resolved = _resolve_path(path)
    logger.debug("load_pipeline: loading from resolved path '%s'", resolved)
    yaml = YAML(typ="safe")
    data = yaml.load(resolved.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        msg = f"Pipeline file must contain a YAML mapping, got {type(data).__name__}"
        raise ValueError(msg)

    try:
        return PipelineDefinition.model_validate(data)
    except ValidationError as exc:
        msg = f"Invalid pipeline definition in {resolved}: {exc}"
        raise ValueError(msg) from exc


def list_bundled_pipelines() -> list[str]:
    """List all bundled pipeline template names.

    Returns:
        List of pipeline names (without .yaml extension).
    """
    names: list[str] = []
    pipelines_pkg = importlib.resources.files("specweaver.pipelines")
    for item in pipelines_pkg.iterdir():
        name = item.name
        if name.endswith(".yaml"):
            names.append(name.removesuffix(".yaml"))
    return sorted(names)


def _resolve_path(path: Path) -> Path:
    """Resolve a pipeline path, checking disk then bundled templates.

    Args:
        path: File path or pipeline name.

    Returns:
        Resolved absolute path to the YAML file.

    Raises:
        FileNotFoundError: If no matching file is found.
    """
    # 1. Direct file path
    if path.exists():
        return path

    # 2. Try adding .yaml suffix
    with_suffix = path.with_suffix(".yaml")
    if with_suffix.exists():
        return with_suffix

    # 3. Check bundled templates by name
    name = path.stem
    try:
        pipelines_pkg = importlib.resources.files("specweaver.pipelines")
        template = pipelines_pkg / f"{name}.yaml"
        # importlib.resources returns a Traversable — we need a real Path
        with importlib.resources.as_file(template) as real_path:
            if real_path.exists():
                return real_path
    except (FileNotFoundError, TypeError, ModuleNotFoundError):
        pass

    msg = f"Pipeline not found: '{path}'. Checked: {path}, {with_suffix}, bundled templates."
    raise FileNotFoundError(msg)
