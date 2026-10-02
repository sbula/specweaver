# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from specweaver.core.config.settings import (
    DALImpactMatrix,
    LLMSettings,
    SandboxSettings,
    SpecWeaverSettings,
    StandardsSettings,
    StitchSettings,
    deep_merge_dict,
)
from specweaver.workspace.store import WorkspaceRepository

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from specweaver.core.config.database import Database

try:
    from ruamel.yaml.error import YAMLError
except ImportError:

    class YAMLError(Exception):  # type: ignore
        pass


logger = logging.getLogger(__name__)


def _sync_or_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an already-created coroutine from sync code.

    Never re-enters a running loop — see `commons.async_bridge`.
    """
    from specweaver.commons.async_bridge import run_sync

    return run_sync(lambda: coro)


def _load_toml_standards(root_path: str | None) -> StandardsSettings:
    import tomllib

    standards = StandardsSettings()
    if root_path:
        toml_file = Path(root_path) / "specweaver.toml"
        if toml_file.exists():
            try:
                with open(toml_file, "rb") as f:
                    toml_data = tomllib.load(f)
                std_data = toml_data.get("standards", {})
                if std_data:
                    standards = StandardsSettings(**std_data)
            except Exception:
                logger.exception("Failed to parse specweaver.toml at %s", toml_file)
    return standards


def _load_toml_sandbox(root_path: str | None) -> SandboxSettings:
    """Load the opt-in [sandbox] TOML section, mirroring _load_toml_standards exactly.

    Defaults to SandboxSettings() (execution_mode="host") on any absence or parse failure, so an
    unconfigured project keeps host execution."""
    import tomllib

    sandbox = SandboxSettings()
    if root_path:
        toml_file = Path(root_path) / "specweaver.toml"
        if toml_file.exists():
            try:
                with open(toml_file, "rb") as f:
                    toml_data = tomllib.load(f)
                sandbox_data = toml_data.get("sandbox", {})
                if sandbox_data:
                    sandbox = SandboxSettings(**sandbox_data)
            except Exception:
                logger.exception("Failed to parse specweaver.toml at %s", toml_file)
    return sandbox


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

    async def _get_data() -> tuple[dict[str, object] | None, str | None]:
        async with db.async_session_scope() as session:
            ws_repo = WorkspaceRepository(session)
            proj = await ws_repo.get_project(project_name)
            if not proj:
                return None, None
            return proj, await ws_repo.get_stitch_mode(project_name)

    proj, stitch_mode = await _get_data()

    if not proj:
        logger.error("Project '%s' not found in database", project_name)
        msg = f"Project '{project_name}' not found"
        raise ValueError(msg)

    llm = LLMSettings()

    stitch = StitchSettings(
        mode=stitch_mode or "off",  # type: ignore[arg-type]
        api_key=os.environ.get("STITCH_API_KEY", ""),
    )

    root_path = proj.get("root_path")
    standards = _load_toml_standards(str(root_path) if root_path else None)
    sandbox = _load_toml_sandbox(str(root_path) if root_path else None)

    return SpecWeaverSettings(
        llm=llm,
        stitch=stitch,
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
