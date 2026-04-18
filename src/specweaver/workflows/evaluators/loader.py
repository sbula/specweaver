# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Loader for declarative evaluator schemas."""

from pathlib import Path
from typing import Any

from specweaver.core.config.settings import deep_merge_dict


def load_evaluator_schemas(project_dir: Path | None = None) -> dict[str, Any]:  # noqa: C901
    """Dynamically load yaml schemas for framework annotator evaluation."""
    import importlib.resources
    import io

    from ruamel.yaml import YAML

    _yaml = YAML(typ="safe")
    schemas: dict[str, dict[str, Any]] = {}

    try:
        frameworks_dir = importlib.resources.files("specweaver.workflows.evaluators.frameworks")
        for yaml_file in frameworks_dir.iterdir():
            if yaml_file.is_file() and yaml_file.name.endswith(".yaml"):
                language = yaml_file.name[:-5]  # remove .yaml
                text = yaml_file.read_text(encoding="utf-8")
                try:
                    content = _yaml.load(io.StringIO(text)) or {}
                    if isinstance(content, dict):
                        if language not in schemas:
                            schemas[language] = {}
                        schemas[language] = deep_merge_dict(schemas[language], content)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        "Failed to parse package YAML schema %s: %s", yaml_file.name, e
                    )
    except (FileNotFoundError, ModuleNotFoundError, TypeError, OSError):
        pass

    # Load from project directory overrides if provided
    if project_dir:
        local_evaluators_dir = project_dir / ".specweaver" / "evaluators"
        if local_evaluators_dir.is_dir():
            for yaml_file in local_evaluators_dir.glob("*.yaml"):
                language = yaml_file.stem  # e.g., java.yaml -> java
                text = yaml_file.read_text(encoding="utf-8")
                try:
                    content = _yaml.load(io.StringIO(text)) or {}
                    if isinstance(content, dict):
                        if language not in schemas:
                            schemas[language] = {}
                        schemas[language] = deep_merge_dict(schemas[language], content)
                except Exception as e:
                    import logging

                    logging.getLogger(__name__).warning(
                        "Failed to parse user-supplied YAML schema %s: %s", yaml_file.name, e
                    )

    return schemas
