# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""The one way an API endpoint gets its models: the router, from the project's settings files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
from specweaver.core.config.llm_settings import SettingsFileError
from specweaver.infrastructure.llm.budget import SpendLimitReachedError
from specweaver.infrastructure.llm.router import build_router
from specweaver.interfaces.api.errors import SpecWeaverAPIError

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from specweaver.core.config.database import Database
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.state import PipelineRun
    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.infrastructure.llm.router import ModelRouter


def api_router(
    project_root: Path, project: str, roles: Iterable[TaskType], db: Database | None = None
) -> ModelRouter:
    """The endpoint's router with every role it uses checked, or a 500 naming the settings error."""
    try:
        return build_router(
            load_llm_settings(project_root),
            project=project,
            roles=roles,
            db=db,
        )
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code="LLM_SETTINGS", status_code=500
        ) from exc


async def run_steps(
    pipeline: PipelineDefinition,
    *,
    project_root: Path,
    spec_path: Path,
    project: str,
    db: Database,
    roles: Iterable[TaskType],
) -> PipelineRun:
    """Run an endpoint's steps through the same handlers as the CLI; a spend stop is a 402."""
    from specweaver.assurance.standards.loader import load_standards_content_async
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.handlers.run_context import GuidanceContent, ModelAccess, RunContext
    from specweaver.workspace.project.constitution import find_constitution

    router = api_router(project_root, project, roles, db)
    constitution = find_constitution(project_root, spec_path=spec_path)
    context = RunContext(
        project_path=project_root,
        spec_path=spec_path,
        model=ModelAccess(llm_router=router),
        db=db,
        guidance=GuidanceContent(
            constitution=constitution.content if constitution else None,
            standards=await load_standards_content_async(
                db, project_name=project, project_path=project_root
            ),
        ),
    )
    try:
        run = await PipelineRunner(pipeline, context).run()
    finally:
        for collector in router.collectors():
            await collector.flush_async(db)
    stopped = getattr(getattr(router, "budget", None), "stopped", None)
    if isinstance(stopped, SpendLimitReachedError):
        raise SpecWeaverAPIError(detail=str(stopped), error_code="SPEND_LIMIT", status_code=402)
    return run
