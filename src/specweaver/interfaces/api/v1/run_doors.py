# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How an API endpoint sets up its run: through the run builder, its errors as HTTP answers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.core.config.bootstrap.project_settings import PROJECT_FILE_NAME
from specweaver.core.config.settings_file import SettingsFileError
from specweaver.interfaces.api.errors import SpecWeaverAPIError

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.session import SessionWorktreeError
    from specweaver.core.flow.run_state.run_context import RunContext
    from specweaver.infrastructure.database import Database


async def build_api_run(
    project_root: Path,
    spec_path: Path,
    pipeline: PipelineDefinition,
    *,
    project: str,
    db: Database,
    selector: str = "direct",
    read_only: bool = False,
    needs_profile: bool = False,
) -> RunContext:
    """The run's context for the request's project; a broken setting is a 500 naming it, a root
    that decides no language a 400 (`needs_profile`, or session isolation on)."""
    from specweaver.commons.project_profile import ProjectUndecidedError
    from specweaver.interfaces.run_setup.builder import RunRequest, build_run

    try:
        return await build_run(
            RunRequest(
                project_root=project_root,
                spec_path=spec_path,
                pipeline=pipeline,
                project=project,
                db=db,
                selector=selector,
                read_only=read_only,
                needs_profile=needs_profile,
            )
        )
    except ProjectUndecidedError as exc:
        raise project_undecided(exc) from exc
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code=settings_error_code(exc), status_code=500
        ) from exc


def project_undecided(exc: Exception) -> SpecWeaverAPIError:
    """The answer to a project whose root decides no language: 400, naming the setting."""
    return SpecWeaverAPIError(detail=str(exc), error_code="PROJECT_UNDECIDED", status_code=400)


def settings_error_code(exc: SettingsFileError) -> str:
    """Which setting stopped the run: the DAL file, the machine's models, a section, else `[sandbox]`."""
    if exc.source.endswith("dal_definitions.yaml"):
        return "DAL_DEFINITIONS"
    if not exc.source.endswith(PROJECT_FILE_NAME):
        return "LLM_SETTINGS"
    codes = {
        "docs": "DOC_POLICY",
        "autonomy": "AUTONOMY_POLICY",
        "implement": "IMPLEMENT_POLICY",
        "standards": "STANDARDS_SETTINGS",
        "llm": "LLM_SETTINGS",
    }
    return codes.get(exc.key.split(".")[0], "SANDBOX_SETTINGS")


def worktree_unavailable(exc: SessionWorktreeError) -> SpecWeaverAPIError:
    """The answer to a run whose worktree cannot start: the project's state, so a 409."""
    return SpecWeaverAPIError(
        detail=f'{exc} `git init` the project, or set [sandbox] auto_isolate_min_dal = "off".',
        error_code="WORKTREE_UNAVAILABLE",
        status_code=409,
    )
