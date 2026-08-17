# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Loader for declarative evaluator schemas."""

from pathlib import Path
from typing import Any

from specweaver.core.config.settings import deep_merge_dict


def _merge_schema(
    schemas: dict[str, dict[str, Any]], language: str, text: str, origin: str, name: str
) -> None:
    """Parse one YAML schema and merge it into `schemas[language]`, in place.

    A malformed file is logged and skipped rather than raised: one bad evaluator schema must not
    stop every other language's from loading. Shared by both sources, which differ only in the
    wording of that warning.
    """
    import io
    import logging

    from ruamel.yaml import YAML

    try:
        content = YAML(typ="safe").load(io.StringIO(text)) or {}
    except Exception as e:
        logging.getLogger(__name__).warning(
            "Failed to parse %s YAML schema %s: %s", origin, name, e
        )
        return
    if isinstance(content, dict):
        schemas[language] = deep_merge_dict(schemas.get(language, {}), content)


def _packaged_schemas(schemas: dict[str, dict[str, Any]]) -> None:
    """Merge every schema shipped inside the package."""
    import importlib.resources

    try:
        frameworks_dir = importlib.resources.files("specweaver.workflows.evaluators.frameworks")
        for yaml_file in frameworks_dir.iterdir():
            if yaml_file.is_file() and yaml_file.name.endswith(".yaml"):
                _merge_schema(
                    schemas,
                    yaml_file.name[:-5],
                    yaml_file.read_text(encoding="utf-8"),
                    "package",
                    yaml_file.name,
                )
    except (FileNotFoundError, ModuleNotFoundError, TypeError, OSError):
        pass


def _project_schemas(schemas: dict[str, dict[str, Any]], project_dir: Path) -> None:
    """Merge the project's own overrides on top of the packaged ones."""
    local_dir = project_dir / ".specweaver" / "evaluators"
    if not local_dir.is_dir():
        return
    for yaml_file in local_dir.glob("*.yaml"):
        _merge_schema(
            schemas,
            yaml_file.stem,
            yaml_file.read_text(encoding="utf-8"),
            "user-supplied",
            yaml_file.name,
        )


def load_evaluator_schemas(project_dir: Path | None = None) -> dict[str, Any]:
    """Dynamically load yaml schemas for framework annotator evaluation.

    Packaged schemas first, then the project's `.specweaver/evaluators/` overrides on top — the
    order is the precedence.
    """
    schemas: dict[str, dict[str, Any]] = {}
    _packaged_schemas(schemas)
    if project_dir:
        _project_schemas(schemas, project_dir)
    return schemas
