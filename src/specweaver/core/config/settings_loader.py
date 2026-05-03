from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import anyio

from specweaver.core.config.settings import (
    DALImpactMatrix,
    LLMSettings,
    SpecWeaverSettings,
    StandardsSettings,
    StitchSettings,
    deep_merge_dict,
)
from specweaver.infrastructure.llm.store import LlmRepository
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
    import asyncio

    import nest_asyncio  # type: ignore

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        nest_asyncio.apply(loop)
        return loop.run_until_complete(coro)

    return anyio.run(lambda: coro)

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


def load_settings(
    db: Database, project_name: str, *, llm_role: str = "review"
) -> SpecWeaverSettings:
    logger.debug("load_settings called for project=%s, role=%s", project_name, llm_role)



    import typing

    return typing.cast(
        "SpecWeaverSettings",
        _sync_or_async(load_settings_async(db, project_name, llm_role=llm_role)),
    )


async def load_settings_async(
    db: Database, project_name: str, *, llm_role: str = "review"
) -> SpecWeaverSettings:
    logger.debug("load_settings_async called for project=%s, role=%s", project_name, llm_role)

    async def _get_data() -> tuple[dict[str, object] | None, dict[str, object] | None, str | None]:
        async with db.async_session_scope() as session:
            ws_repo = WorkspaceRepository(session)
            proj = await ws_repo.get_project(project_name)
            if not proj:
                return None, None, None
            stitch_mode = await ws_repo.get_stitch_mode(project_name)
            repo = LlmRepository(session)
            p = await repo.get_project_profile(project_name, llm_role)
            if not p:
                p = await repo.get_llm_profile_by_name("system-default")

            if p:
                profile_dict = {
                    "model": p.model,
                    "temperature": p.temperature,
                    "max_output_tokens": p.max_output_tokens,
                    "response_format": p.response_format,
                    "provider": p.provider,
                }
            else:
                profile_dict = None

            return proj, profile_dict, stitch_mode

    proj, profile, stitch_mode = await _get_data()

    if not proj:
        logger.error("Project '%s' not found in database", project_name)
        msg = f"Project '{project_name}' not found"
        raise ValueError(msg)

    if not profile:
        logger.error(
            "System default profile not found; cannot load settings for '%s'", project_name
        )
        msg = f"System default profile not found in database. Cannot load settings for '{project_name}'."
        raise ValueError(msg)

    provider_val = str(profile.get("provider", "gemini"))
    env_key = f"{provider_val.upper()}_API_KEY"
    logger.debug("Resolved provider=%s for project=%s", provider_val, project_name)

    llm = LLMSettings(
        model=str(profile["model"]),
        temperature=float(profile["temperature"]),  # type: ignore[arg-type]
        max_output_tokens=int(str(profile["max_output_tokens"])),
        response_format=str(profile["response_format"]),  # type: ignore[arg-type]
        provider=provider_val,
        api_key=os.environ.get(env_key, ""),
    )

    stitch = StitchSettings(
        mode=stitch_mode or "off",  # type: ignore[arg-type]
        api_key=os.environ.get("STITCH_API_KEY", ""),
    )

    root_path = proj.get("root_path")
    standards = _load_toml_standards(str(root_path) if root_path else None)

    dal_matrix = DALImpactMatrix()
    if root_path:
        dal_file = Path(str(root_path)) / ".specweaver" / "dal_definitions.yaml"
        if dal_file.exists():
            from ruamel.yaml import YAML

            yaml_parser = YAML(typ="safe")
            try:
                dal_dict = yaml_parser.load(dal_file) or {}
                merged_dal_dict = deep_merge_dict({}, dal_dict)
                dal_matrix = DALImpactMatrix(**merged_dal_dict)
                logger.debug("Loaded DAL configuration from %s", dal_file)
            except Exception:
                logger.exception("Failed to parse dal_definitions.yaml at %s", dal_file)

    return SpecWeaverSettings(llm=llm, stitch=stitch, dal_matrix=dal_matrix, standards=standards)


def load_settings_for_active(db: Database, *, llm_role: str = "review") -> SpecWeaverSettings:
    logger.debug("load_settings_for_active called with role=%s", llm_role)

    async def _get_active() -> str | None:
        async with db.async_session_scope() as session:
            return await WorkspaceRepository(session).get_active_project()

    active = _sync_or_async(_get_active())
    if not active:
        logger.error("No active project found")
        msg = "No active project. Run 'sw init <name> --path <path>' first."
        raise ValueError(msg)
    logger.debug("Active project resolved to '%s'", active)
    return load_settings(db, active, llm_role=llm_role)


def migrate_legacy_config(db: Database, project_name: str, project_path: str) -> bool:
    from pathlib import Path

    from ruamel.yaml import YAML
    logger.debug("migrate_legacy_config called for project=%s, path=%s", project_name, project_path)
    config_file = Path(project_path) / ".specweaver" / "config.yaml"
    if not config_file.is_file():
        logger.debug("No legacy config.yaml found at %s", config_file)
        return False

    async def _check_and_migrate() -> None:
        async with db.async_session_scope() as session:
            ws_repo = WorkspaceRepository(session)
            existing = await ws_repo.get_project(project_name)
            if existing:
                logger.error("Project '%s' already exists in database", project_name)
                msg = f"Project '{project_name}' already exists"
                raise ValueError(msg)

            yaml = YAML()
            try:
                data = yaml.load(config_file)
            except YAMLError:
                logger.exception("Failed to parse legacy config at %s", config_file)
                data = {}

            if not isinstance(data, dict):
                data = {}

            llm_raw = data.get("llm", {})
            if not isinstance(llm_raw, dict):
                llm_raw = {}

            await ws_repo.register_project(project_name, project_path)

            repo = LlmRepository(session)
            p = await repo.get_llm_profile_by_name("system-default")
            if not p:
                raise ValueError("Database missing system-default profile.")

            p_provider = p.provider or "gemini"
            _model = llm_raw.get("model", p.model)
            _provider = llm_raw.get("provider", p_provider)

            profile_id = await repo.create_llm_profile(
                name="legacy-import",
                is_global=False,
                model=_model,
                temperature=llm_raw.get("temperature", 0.7),
                max_output_tokens=llm_raw.get("max_output_tokens", 4096),
                response_format=llm_raw.get("response_format", "text"),
                provider=_provider,
            )

            for role in ("review", "draft", "search"):
                await repo.link_project_profile(project_name, role, profile_id)



    _sync_or_async(_check_and_migrate())
    logger.info("Migrated legacy config for project '%s'", project_name)
    return True
