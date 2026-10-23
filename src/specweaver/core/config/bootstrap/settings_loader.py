# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.core.config.bootstrap.llm_settings_loader import (
    PROJECT_FILE_NAME,
    read_settings_text,
)
from specweaver.core.config.settings import (
    DALImpactMatrix,
    SandboxSettings,
    SpecWeaverSettings,
    StandardsSettings,
    deep_merge_dict,
)
from specweaver.core.config.settings_file import parse_section
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
    """The project's DAL impact matrix, or the built-in default.

    A malformed file is logged and the default used: DAL only *escalates* isolation, so falling
    back is the safe direction — a parse error must not leave a project unable to load at all.
    """
    if not root_path:
        return DALImpactMatrix()

    dal_file = Path(str(root_path)) / ".specweaver" / "dal_definitions.yaml"
    if not dal_file.exists():
        return DALImpactMatrix()

    from ruamel.yaml import YAML

    try:
        dal_dict = YAML(typ="safe").load(dal_file) or {}
        matrix = DALImpactMatrix(**deep_merge_dict({}, dal_dict))
    except Exception:
        logger.exception("Failed to parse dal_definitions.yaml at %s", dal_file)
        return DALImpactMatrix()

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


def load_settings_for_active(db: Database) -> SpecWeaverSettings:
    logger.debug("load_settings_for_active called")

    async def _get_active() -> str | None:
        async with db.async_session_scope() as session:
            return await WorkspaceRepository(session).get_active_project()

    active = _sync_or_async(_get_active())
    if not active:
        logger.error("No active project found")
        msg = "No active project. Run 'sw init <name> --path <path>' first."
        raise ValueError(msg)
    logger.debug("Active project resolved to '%s'", active)
    return load_settings(db, active)
