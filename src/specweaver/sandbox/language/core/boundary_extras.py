# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The stricter boundary tools a project configured, run in addition to the shared check.

A tool runs only where the project has its config file: SpecWeaver never installs or configures
one. A configured tool that cannot run (not installed, timed out, output it cannot read) is
reported as not run, never as clean, and its reason goes with it. Each tool's violations carry
its name.
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from specweaver.commons import json
from specweaver.commons.qa import ArchitectureViolation, ExtraRun
from specweaver.sandbox.execution.container_executor import (
    ContainerEngineUnavailableError,
    ContainerSubprocessExecutor,
)
from specweaver.sandbox.language.core.python.toolchain_absence import why_it_did_not_run
from specweaver.sandbox.language.core.toolchain import timed_out

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class _Extra:
    tool: str
    languages: frozenset[str]
    #: The config files whose presence means the project chose this tool.
    configs: tuple[str, ...]
    #: The executable the host must have on its PATH.
    executable: str
    command: tuple[str, ...]
    read: Callable[[str], list[ArchitectureViolation]]


def run_extras(project_root: Path, language: str, executor: Any) -> list[ExtraRun]:
    """Every extra configured in `project_root` for `language`, each run once."""
    return [
        _run(extra, project_root, executor)
        for extra in _EXTRAS
        if language in extra.languages and _configured(project_root, extra)
    ]


def _configured(project_root: Path, extra: _Extra) -> bool:
    return any(next(project_root.glob(c), None) is not None for c in extra.configs)


def _run(extra: _Extra, project_root: Path, executor: Any) -> ExtraRun:
    # The host PATH says nothing in container mode: the tool is looked for inside the image there.
    is_container = isinstance(executor, ContainerSubprocessExecutor)
    if not is_container and not shutil.which(extra.executable):
        return ExtraRun(
            extra.tool, ran=False, reason=f"{extra.tool} is configured but not installed"
        )
    try:
        result = executor.execute(list(extra.command), timeout_seconds=_TIMEOUT_SECONDS)
    except ContainerEngineUnavailableError as exc:
        return ExtraRun(extra.tool, ran=False, reason=str(exc))
    reason = timed_out(result, extra.tool, _TIMEOUT_SECONDS) or why_it_did_not_run(
        result, extra.tool
    )
    if reason:
        return ExtraRun(extra.tool, ran=False, reason=reason)
    try:
        violations = extra.read(result.stdout)
    except ValueError as exc:
        logger.warning("%s output could not be read: %s", extra.tool, exc)
        return ExtraRun(
            extra.tool,
            ran=False,
            reason=f"{extra.tool} ran but SpecWeaver could not read its output: {exc}",
        )
    return ExtraRun(extra.tool, ran=True, violations=violations)


def _tach_violations(stdout: str) -> list[ArchitectureViolation]:
    """tach's `--output json`: a list of located diagnostics; undeclared dependencies are findings."""
    if not stdout.strip():
        return []
    data = json.loads(stdout)
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("tach output is not a JSON list of objects")
    found = []
    for item in data:
        located = item.get("Located", {})
        undeclared = located.get("details", {}).get("Code", {}).get("UndeclaredDependency")
        if undeclared:
            found.append(
                ArchitectureViolation(
                    file=str(located.get("file_path", "")),
                    code="tach:UndeclaredDependency",
                    message=(
                        f"Module '{undeclared.get('usage_module', '')}' cannot import "
                        f"'{undeclared.get('dependency', '')}' from "
                        f"'{undeclared.get('definition_module', '')}' (tach)"
                    ),
                )
            )
    return found


_EXTRAS: tuple[_Extra, ...] = (
    _Extra(
        tool="tach",
        languages=frozenset({"python"}),
        configs=("tach.toml",),
        executable="tach",
        command=("python", "-m", "tach", "check", "--output", "json"),
        read=_tach_violations,
    ),
)
