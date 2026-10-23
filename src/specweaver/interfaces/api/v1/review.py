# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Review API endpoint — POST /review."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.v1.paths import resolve_file_in_project
from specweaver.interfaces.api.v1.schemas import ReviewRequest  # noqa: TC001 -- runtime for FastAPI

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.post("/review")
async def review_spec(
    body: ReviewRequest,
    db: Database = _db_dep,
) -> dict[str, object]:
    """Run an LLM-powered review of a spec file.

    Returns the ReviewResult as a dict.
    """
    project_root, abs_path = await resolve_file_in_project(body.file, body.project, db)

    from specweaver.core.flow.engine.models import PipelineDefinition, StepAction, StepTarget
    from specweaver.interfaces.api.v1._llm import run_steps
    from specweaver.workflows.review.reviewer import result_from_run

    pipeline = PipelineDefinition.create_single_step(
        name="review_spec",
        action=StepAction.REVIEW,
        target=StepTarget.SPEC,
        description=f"Review {abs_path.name}",
    )
    run, unwritten = await run_steps(
        pipeline,
        project_root=project_root,
        spec_path=abs_path,
        project=body.project,
        db=db,
        read_only=True,
    )
    return {**result_from_run(run).model_dump(), "unwritten_calls": unwritten}
