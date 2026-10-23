# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""One way to set up a run, for every CLI command and API route.

The builder raises; each door turns its errors into a CLI refusal or an HTTP answer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from specweaver.core.config.database import Database
    from specweaver.core.config.llm_settings import RoleEntry
    from specweaver.core.config.settings import SpecWeaverSettings
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.handlers.run_context import RunContext

logger = logging.getLogger(__name__)


class UnknownProjectError(ValueError):
    """No project answers for this run."""


def project_for(db: Database, project_root: Path | None, *, named: str | None = None) -> str:
    """The run's one project: the one named, else the one registered at `project_root`, else (with
    no folder given) the active one. A folder no project is registered at has no project."""
    from specweaver.workspace.store import active_project, project_name_at

    if named:
        return named
    if project_root is not None:
        name = project_name_at(db, project_root)
        if name is None:
            msg = (
                f"No project is registered at {project_root}. "
                f"Register it with: sw init <name> --path {project_root}"
            )
            raise UnknownProjectError(msg)
        return name
    active = active_project(db)
    if active is None:
        msg = "No active project. Run 'sw init <name>' or 'sw use <name>' first."
        raise UnknownProjectError(msg)
    return active


@dataclass(frozen=True)
class RunRequest:
    """What a door knows about the run it starts."""

    project_root: Path
    spec_path: Path
    pipeline: PipelineDefinition
    project: str
    db: Database
    run_model: RoleEntry | None = None
    selector: str = "direct"
    #: Asked at a spend limit; None never asks (the API).
    ask: Callable[[str], bool] | None = None
    #: `required`: a model step with no model set raises; `optional`: it gives no router.
    models: Literal["required", "optional", "none"] = "required"


async def build_run(request: RunRequest) -> RunContext:
    """The run's context, every part from the request's one project. Raises; never exits."""
    from specweaver.assurance.standards.loader import load_standards_content_async
    from specweaver.core.flow.handlers._llm import roles_of
    from specweaver.core.flow.handlers.run_context import (
        AnalysisContext,
        GraphContext,
        GuidanceContent,
        IsolationPolicy,
        ModelAccess,
        RunContext,
    )
    from specweaver.workspace.analyzers.factory import AnalyzerFactory
    from specweaver.workspace.project.constitution import find_constitution

    doc_policy, autonomy, language = _sections(request.project_root)
    info = find_constitution(request.project_root, spec_path=request.spec_path)
    standards = await load_standards_content_async(
        request.db, request.project, request.project_root, target_path=request.spec_path
    )
    settings = await _settings(request)
    needs_model = bool(roles_of(request.pipeline)) and request.models != "none"
    context = RunContext(
        analysis=AnalysisContext(analyzer_factory=AnalyzerFactory),
        project_path=request.project_root,
        spec_path=request.spec_path,
        output_dir=request.project_root / "src",
        db=request.db,
        isolation=IsolationPolicy(doc_policy=doc_policy, autonomy=autonomy, language=language),
        guidance=GuidanceContent(constitution=info.content if info else None, standards=standards),
        model=ModelAccess(
            config=settings if needs_model else None,
            llm_router=_router(request) if needs_model else None,
        ),
        graph=GraphContext(topology=_topology(request)),
    )
    if settings is not None:
        _apply_isolation(context, settings)
    return context


def build_run_sync(request: RunRequest) -> RunContext:
    """`build_run` for a synchronous door."""
    from specweaver.commons.async_bridge import run_sync

    return run_sync(lambda: build_run(request))


def _sections(root: Path) -> tuple[Any, Any, str | None]:
    from specweaver.core.config.autonomy_policy import parse_autonomy
    from specweaver.core.config.bootstrap.project_settings import load_section
    from specweaver.core.config.doc_policy import parse_doc_policy
    from specweaver.core.config.implement_policy import parse_implement

    return (
        load_section(root, parse_doc_policy),
        load_section(root, parse_autonomy),
        load_section(root, parse_implement).language,
    )


async def _settings(request: RunRequest) -> SpecWeaverSettings | None:
    """The project's settings, read once; a broken file raises, an unknown project gives None."""
    from specweaver.core.config.bootstrap.settings_loader import load_settings_async

    try:
        return await load_settings_async(request.db, request.project)
    except ValueError as exc:
        from specweaver.core.config.settings_file import SettingsFileError

        if isinstance(exc, SettingsFileError):
            raise
        return None


def _router(request: RunRequest) -> Any:
    from specweaver.core.config.bootstrap.llm_settings_loader import load_llm_settings
    from specweaver.core.config.llm_settings import SettingNotSetError
    from specweaver.core.flow.handlers._llm import roles_of
    from specweaver.infrastructure.llm.router import build_router

    try:
        return build_router(
            load_llm_settings(request.project_root),
            project=request.project,
            roles=roles_of(request.pipeline),
            run_model=request.run_model,
            ask=request.ask,
            db=request.db,
        )
    except SettingNotSetError:
        if request.models == "optional":
            return None
        raise


def _topology(request: RunRequest) -> Any:
    from specweaver.assurance.graph.loader import load_topology, select_topology_contexts
    from specweaver.commons.spec_names import module_stem

    graph = load_topology(request.project_root)
    if graph is None:
        return None
    return select_topology_contexts(
        graph, module_stem(request.spec_path), selector_name=request.selector
    )


def _apply_isolation(context: RunContext, settings: SpecWeaverSettings) -> None:
    """Both isolation policies, with escalation by the code's DAL, in every door."""
    from specweaver.core.flow.engine.isolation import apply_session_policy

    context.isolation = context.isolation.model_copy(
        update={"enforce_isolation": settings.sandbox.enforce_worktree_isolation}
    )
    apply_session_policy(context, settings, logger, dal_auto_escalate=True)
