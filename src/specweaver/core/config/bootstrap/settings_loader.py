# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.core.config.bootstrap.project_settings import PROJECT_FILE_NAME, read_settings_text
from specweaver.core.config.settings import (
    DALImpactMatrix,
    SandboxSettings,
    SpecWeaverSettings,
    StandardsSettings,
)
from specweaver.core.config.settings_file import SettingsFileError, parse_section, validate
from specweaver.core.config.yaml_lines import yaml_line
from specweaver.workspace.store import WorkspaceRepository

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from specweaver.core.config.database import Database

try:
    from ruamel.yaml.error import YAMLError
except ImportError:  # expected: ruamel is optional; a stand-in keeps the except clauses valid

    class YAMLError(Exception):  # type: ignore
        pass


logger = logging.getLogger(__name__)


def _sync_or_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an already-created coroutine from sync code.

    Never re-enters a running loop — see `commons.async_bridge`.
    """
    from specweaver.commons.async_bridge import run_sync

    return run_sync(lambda: coro)


def _project_sections(root_path: str | None) -> tuple[StandardsSettings, SandboxSettings]:
    """The project's `[standards]` and `[sandbox]`; defaults when the file or a section is absent.

    Raises `SettingsFileError` naming the file, key and line of anything it cannot use.
    """
    if not root_path:
        return StandardsSettings(), SandboxSettings()
    path = Path(root_path) / PROJECT_FILE_NAME
    text, source = read_settings_text(path), str(path)
    return (
        parse_section(text, source, "standards", StandardsSettings),
        parse_section(text, source, "sandbox", SandboxSettings),
    )


def load_settings(db: Database, project_name: str) -> SpecWeaverSettings:
    logger.debug("load_settings called for project=%s", project_name)

    import typing

    return typing.cast(
        "SpecWeaverSettings",
        _sync_or_async(load_settings_async(db, project_name)),
    )


def _load_dal_matrix(root_path: object) -> DALImpactMatrix:
    """The project's DAL impact matrix, or the built-in default when it has no file.

    Raises `SettingsFileError` naming the file, key and line of a matrix it cannot use: a broken
    matrix must not quietly become the default one.
    """
    if not root_path:
        return DALImpactMatrix()

    dal_file = Path(str(root_path)) / ".specweaver" / "dal_definitions.yaml"
    if not dal_file.exists():
        return DALImpactMatrix()

    from ruamel.yaml import YAML

    text, source = dal_file.read_text(encoding="utf-8"), str(dal_file)
    try:
        data = YAML(typ="rt").load(text) or {}
    except YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        line = mark.line + 1 if mark is not None else 1
        raise SettingsFileError(source, "(syntax)", line, "not valid YAML") from None
    matrix = validate(
        DALImpactMatrix, data, text, source, line_of=lambda _, loc: yaml_line(data, loc)
    )
    logger.debug("Loaded DAL configuration from %s", dal_file)
    return matrix


async def load_settings_async(db: Database, project_name: str) -> SpecWeaverSettings:
    logger.debug("load_settings_async called for project=%s", project_name)

    async def _get_data() -> dict[str, object] | None:
        async with db.async_session_scope() as session:
            return await WorkspaceRepository(session).get_project(project_name)

    proj = await _get_data()

    if not proj:
        logger.error("Project '%s' not found in database", project_name)
        msg = f"Project '{project_name}' not found"
        raise ValueError(msg)

    root_path = proj.get("root_path")
    standards, sandbox = _project_sections(str(root_path) if root_path else None)

    return SpecWeaverSettings(
        dal_matrix=_load_dal_matrix(root_path),
        standards=standards,
        sandbox=sandbox,
    )
