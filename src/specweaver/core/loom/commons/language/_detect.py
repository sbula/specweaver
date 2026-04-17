# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Language detection helpers.

Auto-discovers the target project language based on the presence of manifest
files in a given directory. Pure-logic, no I/O side effects beyond ``Path.exists()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

# Canonical language identifiers used across the scenario pipeline
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"python", "java", "kotlin", "typescript", "rust"})

# Mapping from canonical language name to scenario test file extension
_SCENARIO_EXTENSIONS: dict[str, str] = {
    "python": "py",
    "java": "java",
    "kotlin": "kt",
    "typescript": "ts",
    "rust": "rs",
}


def detect_language(cwd: Path) -> str:
    """Return the canonical language name for a project directory.

    Detection is done by sniffing well-known manifest files.
    The order matches ``commons/qa_runner/factory.py`` to ensure consistency.

    Args:
        cwd: Project root directory to inspect.

    Returns:
        One of: ``"python"``, ``"java"``, ``"kotlin"``, ``"typescript"``, ``"rust"``.
        Defaults to ``"python"`` when no manifest is found.
    """
    if (cwd / "package.json").exists():
        return "typescript"
    if (cwd / "Cargo.toml").exists():
        return "rust"
    if (cwd / "build.gradle").exists() or (cwd / "build.gradle.kts").exists():
        return "kotlin"
    if (cwd / "pom.xml").exists():
        return "java"
    return "python"


def detect_scenario_extension(cwd: Path) -> str:
    """Return the file extension for generated scenario test files.

    Args:
        cwd: Project root directory to inspect.

    Returns:
        File extension string (without leading dot), e.g. ``"py"``, ``"java"``.
    """
    return _SCENARIO_EXTENSIONS.get(detect_language(cwd), "py")
