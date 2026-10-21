# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Turning a test target into the filter a build tool takes, so one task runs only its own tests."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_EXTENSIONS = {"java": ".java", "kotlin": ".kt"}


def jvm_test_class(target: str, language: str) -> str | None:
    """The class a JVM test file declares, fully qualified when it sits under `src/test/<lang>/`;
    None for a folder, the project, or a file outside the test sources."""
    path = PurePosixPath(target.replace("\\", "/"))
    if path.suffix != _EXTENSIONS.get(language) or "main" in path.parts[:-1]:
        return None
    parts = path.parts
    for index in range(len(parts) - 2):
        if parts[index : index + 3] == ("src", "test", language):
            return ".".join((*parts[index + 3 : -1], path.stem))
    return path.stem


def cargo_test_file(target: str) -> str | None:
    """The integration test `tests/<name>.rs` names, or None for anything else."""
    path = PurePosixPath(target.replace("\\", "/"))
    if path.suffix == ".rs" and len(path.parts) >= 2 and path.parts[-2] == "tests":
        return path.stem
    return None


_WRAPPERS = {"gradle": ("gradlew", "gradlew.bat"), "maven": ("mvnw", "mvnw.cmd")}
_ON_PATH = {"gradle": "gradle", "maven": "mvn"}


def build_launcher(project: Path, tool: str) -> str:
    """The project's own wrapper (`./gradlew`, `./mvnw`), else the tool on PATH.

    A bare `gradlew` is looked up on PATH only, never in the project, so the wrapper is named by
    its path. The wrapper wins because the machine's own install may be too old for the project.
    """
    for wrapper in _WRAPPERS[tool]:
        if (project / wrapper).is_file():
            return wrapper if wrapper.endswith((".bat", ".cmd")) else f"./{wrapper}"
    return _ON_PATH[tool]
