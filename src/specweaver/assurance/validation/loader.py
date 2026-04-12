# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Dynamic rule loader -- discovers custom Rule subclasses from directories.

Uses importlib to load .py files from registered directories, finds Rule
subclasses, validates D-prefix, and registers them in a RuleRegistry.

Trust model: custom rules run arbitrary code, same as Pylint plugins.
Users must trust the source. Each file is wrapped in try/except so a
broken custom rule doesn't crash the entire validation run.
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import re
import sys
from pathlib import Path  # noqa: TC003  -- used at runtime (is_dir, glob)
from typing import TYPE_CHECKING, Literal

from specweaver.assurance.validation.models import Rule

if TYPE_CHECKING:
    from specweaver.assurance.validation.registry import RuleRegistry

logger = logging.getLogger(__name__)

_D_PREFIX = re.compile(r"^D\d{2,3}$")


def load_rules_from_directory(
    directory: Path,
    *,
    registry: RuleRegistry | None = None,
    category: Literal["spec", "code"] = "spec",
) -> list[str]:
    """Scan a directory for .py files, discover Rule subclasses, register them.

    Args:
        directory: Path to scan for custom rule files.
        registry: Registry to add rules to. Uses global if not provided.
        category: Category to register under ('spec' or 'code').

    Returns:
        List of successfully loaded rule_ids.
    """
    if registry is None:
        from specweaver.assurance.validation.registry import get_registry

        registry = get_registry()

    if not directory.is_dir():
        logger.warning("load_rules_from_directory: path does not exist: %s", directory)
        return []

    loaded: list[str] = []

    for py_file in sorted(directory.glob("*.py")):
        if py_file.name.startswith("__"):
            continue

        try:
            rule_ids = _load_rules_from_file(py_file, registry, category)
            loaded.extend(rule_ids)
        except Exception:
            logger.exception("load_rules_from_directory: failed to load %s", py_file)

    logger.debug("load_rules_from_directory: loaded %d rules from %s", len(loaded), directory)
    return loaded


def load_rules_from_paths(
    paths: list[Path],
    *,
    registry: RuleRegistry | None = None,
    category: Literal["spec", "code"] = "spec",
) -> list[str]:
    """Load custom rules from multiple directories.

    Args:
        paths: List of directories to scan.
        registry: Registry to add rules to.
        category: Category to register under.

    Returns:
        List of all successfully loaded rule_ids.
    """
    loaded: list[str] = []
    for path in paths:
        loaded.extend(load_rules_from_directory(path, registry=registry, category=category))
    return loaded


def _load_rules_from_file(
    filepath: Path,
    registry: RuleRegistry,
    category: Literal["spec", "code"],
) -> list[str]:
    """Load a single .py file and register any Rule subclasses found."""
    module_name = f"specweaver_custom_rules.{filepath.stem}"

    spec = importlib.util.spec_from_file_location(module_name, filepath)
    if spec is None or spec.loader is None:
        logger.warning("Could not create module spec for %s", filepath)
        return []

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        logger.exception("Failed to execute module %s", filepath)
        # Clean up partially loaded module
        sys.modules.pop(module_name, None)
        raise

    loaded: list[str] = []

    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if not issubclass(obj, Rule) or obj is Rule:
            continue

        # Instantiate to get rule_id
        try:
            instance = obj()
        except Exception:
            logger.exception("Failed to instantiate %s from %s", obj.__name__, filepath)
            continue

        rule_id = instance.rule_id

        if not _D_PREFIX.match(rule_id):
            logger.warning(
                "Custom rule '%s' from %s has invalid prefix (must match D\\d{2,3}), skipping",
                rule_id,
                filepath,
            )
            continue

        try:
            registry.register(rule_id, obj, category)
            loaded.append(rule_id)
            logger.info("Loaded custom rule %s (%s) from %s", rule_id, obj.__name__, filepath)
        except ValueError:
            logger.warning("Rule %s already registered, skipping from %s", rule_id, filepath)

    # Clean up module from sys.modules to avoid conflicts on reload
    sys.modules.pop(module_name, None)

    return loaded
