# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""How an endpoint that waits for its run runs it: set up by the builder, a spend stop a 402."""

from __future__ import annotations

from typing import TYPE_CHECKING

from specweaver.infrastructure.llm.budget import SpendLimitReachedError
from specweaver.interfaces.api.errors import SpecWeaverAPIError

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.config.database import Database
    from specweaver.core.flow.engine.models import PipelineDefinition
    from specweaver.core.flow.engine.state import PipelineRun


async def run_steps(
    pipeline: PipelineDefinition,
    *,
    project_root: Path,
    spec_path: Path,
    project: str,
    db: Database,
    memory_task: bool = False,
    selector: str = "direct",
    read_only: bool = False,
) -> tuple[PipelineRun, int]:
    """Run an endpoint's steps through the same run setup as the CLI; a spend stop is a 402.

    Gives the run and how many of its calls the cost ledger misses."""
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.session import SessionWorktreeError
    from specweaver.interfaces.api.v1.run_doors import build_api_run, worktree_unavailable

    context = await build_api_run(
        project_root,
        spec_path,
        pipeline,
        project=project,
        db=db,
        selector=selector,
        read_only=read_only,
    )
    router = context.model.llm_router
    try:
        run = await PipelineRunner(pipeline, context, memory_task=memory_task).run()
    except SessionWorktreeError as exc:
        raise worktree_unavailable(exc) from exc
    stopped = getattr(getattr(router, "budget", None), "stopped", None)
    if isinstance(stopped, SpendLimitReachedError):
        raise SpecWeaverAPIError(detail=str(stopped), error_code="SPEND_LIMIT", status_code=402)
    return run, router.unwritten() if router is not None else 0
