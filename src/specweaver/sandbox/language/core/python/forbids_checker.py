# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Context.yaml forbids checker — verifies Python imports against boundary rules.

Extracted from PythonQARunner to keep runner.py under the file size limit.
This module provides pure functions for loading forbids rules from context.yaml
and scanning Python AST imports against those rules.
"""

from __future__ import annotations

import ast
import fnmatch
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from specweaver.sandbox.qa_runner.core.interface import ArchitectureViolation

logger = logging.getLogger(__name__)


def load_forbids(target_path: Path, project_root: Path) -> list[str]:
    """Load forbids rules from the nearest context.yaml.

    Walks up from target_path's parent toward project_root looking for a
    context.yaml file containing a ``forbids`` key.

    Args:
        target_path: The Python file being checked.
        project_root: The project root directory (stop boundary).

    Returns:
        List of forbids patterns (e.g., ``["specweaver/sandbox/*"]``).
    """
    import yaml

    ctx_dir = target_path.parent
    while (
        ctx_dir != project_root
        and ctx_dir.parent != ctx_dir
        and not (ctx_dir / "context.yaml").exists()
    ):
        ctx_dir = ctx_dir.parent

    ctx_file = ctx_dir / "context.yaml"
    if not ctx_file.exists():
        return []

    try:
        data = yaml.safe_load(ctx_file.read_text(encoding="utf-8")) or {}
        forbids: list[str] = data.get("forbids", [])
        return forbids
    except Exception as e:
        logger.warning("Failed to parse context.yaml at %s: %s", ctx_file, e)
        return []


def check_file_forbids(target_path: Path, project_root: Path) -> list[ArchitectureViolation]:
    """Check a single Python file's imports against its context.yaml forbids.

    Args:
        target_path: The Python file to scan.
        project_root: The project root (stop boundary for context.yaml lookup).

    Returns:
        List of architecture violations found.
    """
    if not (target_path.is_file() and target_path.suffix == ".py"):
        return []

    forbids = load_forbids(target_path, project_root)
    if not forbids:
        return []

    return _scan_imports_against_forbids(target_path, forbids)


def _scan_imports_against_forbids(
    target_path: Path,
    forbids: list[str],
) -> list[ArchitectureViolation]:
    """Parse a Python file's AST and check imports against forbids patterns."""
    try:
        source = target_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(target_path))
    except Exception as e:
        logger.warning("Failed to parse %s for import checking: %s", target_path, e)
        return []

    violations: list[ArchitectureViolation] = []

    # RED-5: Collect nodes inside TYPE_CHECKING blocks to avoid false positives
    type_checking_ids: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            for child in ast.walk(node):
                type_checking_ids.add(id(child))

    for node in ast.walk(tree):
        if id(node) in type_checking_ids:
            continue
        if isinstance(node, ast.Import):
            for alias in node.names:
                violations.extend(
                    _check_forbids(alias.name, forbids, target_path)
                )
        elif isinstance(node, ast.ImportFrom) and node.module:
            violations.extend(
                _check_forbids(node.module, forbids, target_path)
            )

    return violations


def _check_forbids(
    import_module: str,
    forbids: list[str],
    target_path: Path,
) -> list[ArchitectureViolation]:
    """Check if an import matches any forbids pattern.

    Supports glob-style patterns:
    - ``specweaver/sandbox/*`` matches ``specweaver.sandbox.anything``
    - ``specweaver/llm`` matches ``specweaver.llm`` exactly
    """
    violations: list[ArchitectureViolation] = []
    for pattern in forbids:
        module_pattern = pattern.replace("/", ".")
        if fnmatch.fnmatch(import_module, module_pattern):
            violations.append(
                ArchitectureViolation(
                    file=str(target_path),
                    code="ForbiddenImport",
                    message=(
                        f"Import '{import_module}' violates context.yaml "
                        f"forbids pattern '{pattern}'"
                    ),
                )
            )
    return violations
