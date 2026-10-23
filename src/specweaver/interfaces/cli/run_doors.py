# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How a CLI command sets up its run: through the run builder, its errors as refusals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, NoReturn

import typer

from specweaver.interfaces.cli import _core

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.llm_settings import RoleEntry, SettingNotSetError
    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.core.flow.engine.session import SessionWorktreeError
    from specweaver.core.flow.engine.state import StepRecord
    from specweaver.core.flow.handlers.run_context import RunContext


def build_run_or_exit(
    project_path: Path | None,
    spec_path: Path,
    pipeline: PipelineDefinition,
    *,
    models: Literal["required", "optional", "none"] = "required",
    selector: str = "direct",
    run_model: RoleEntry | None = None,
    read_only: bool = False,
) -> RunContext:
    """The run's context for the project at `project_path` (the active one when None)."""
    from specweaver.core.config.settings_file import SettingsFileError
    from specweaver.infrastructure.llm.interfaces.command import tell_missing_at_end
    from specweaver.interfaces.run_setup.builder import (
        RunRequest,
        UnknownProjectError,
        build_run_sync,
        project_for,
    )
    from specweaver.workspace.store import project_root_of

    db = _core.get_db()
    try:
        project = project_for(db, project_path)
        root = project_path if project_path is not None else project_root_of(db, project)
        if root is None:
            raise UnknownProjectError(f"Project '{project}' has no folder registered.")
        context = build_run_sync(
            RunRequest(
                project_root=root,
                spec_path=spec_path,
                pipeline=pipeline,
                project=project,
                db=db,
                run_model=run_model,
                selector=selector,
                ask=_core.spend_asker(),
                models=models,
                read_only=read_only,
                on_model_skipped=_say_no_model,
            )
        )
    except SettingsFileError as err:
        _core.refuse_settings(err)
    except UnknownProjectError as err:
        _core.print_error(err)
        raise typer.Exit(code=1) from err
    if context.model.llm_router is not None:
        tell_missing_at_end(context.model.llm_router)
    return context


def run_one_step(
    project_path: Path | None,
    spec_path: Path,
    *,
    name: str,
    action: StepAction,
    target: StepTarget,
    description: str,
    params: dict[str, Any] | None = None,
    models: Literal["required", "optional", "none"] = "required",
    read_only: bool = False,
) -> tuple[StepRecord | None, RunContext]:
    """Run a one-step pipeline set up by the builder; its last step record, and its context."""
    import asyncio

    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.runner import PipelineRunner

    pipeline = PipelineDefinition.create_single_step(
        name=name, action=action, target=target, description=description, params=params or {}
    )
    context = build_run_or_exit(
        project_path, spec_path, pipeline, models=models, read_only=read_only
    )
    run = asyncio.run(PipelineRunner(pipeline, context).run())
    return (run.step_records[-1] if run.step_records else None), context


def _say_no_model(err: SettingNotSetError) -> None:
    _core.console.print(f"No model used: {err.key}: {err.message}", style="dim", markup=False)


def refuse_unstarted_worktree(err: SessionWorktreeError) -> NoReturn:
    """Stop a command whose run could not start its worktree, or whose worktree is gone."""
    _core.print_error(err)
    raise typer.Exit(code=1) from err


def recorded_project_root(name: str) -> Path:
    """The folder of the project a run recorded; a project no longer registered stops the command."""
    from specweaver.workspace.store import project_root_of

    root = project_root_of(_core.get_db(), name)
    if root is None:
        _core.console.print(
            f"Error: the run belongs to project '{name}', which is not registered any more. "
            f"Register it again with: sw init {name} --path <folder>",
            style="red",
            markup=False,
        )
        raise typer.Exit(code=1)
    return root
