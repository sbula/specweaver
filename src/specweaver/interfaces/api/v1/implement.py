# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Implementation API endpoint — POST /implement."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from specweaver.commons.spec_names import module_stem
from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.v1.paths import resolve_file_in_project
from specweaver.interfaces.api.v1.schemas import ImplementRequest, ImplementResponse

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.post("/implement", response_model=ImplementResponse)
async def implement_spec(
    body: ImplementRequest,
    db: Database = _db_dep,
) -> ImplementResponse:
    """Generate code + tests from a spec file.

    Uses the LLM to generate implementation and test files.
    """
    project_root, spec_path = await resolve_file_in_project(body.file, body.project, db)

    from specweaver.core.flow.engine.models import (
        PipelineDefinition,
        PipelineStep,
        StepAction,
        StepTarget,
    )
    from specweaver.core.flow.engine.state import RunStatus
    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.interfaces.api.errors import SpecWeaverAPIError
    from specweaver.interfaces.api.v1._llm import run_steps

    stem = module_stem(spec_path)
    pipeline = PipelineDefinition(
        name="implement_spec",
        description=f"Generate code and tests for {stem}",
        steps=[
            PipelineStep(name="generate_code", action=StepAction.GENERATE, target=StepTarget.CODE),
            PipelineStep(
                name="generate_tests", action=StepAction.GENERATE, target=StepTarget.TESTS
            ),
        ],
    )
    run, unwritten = await run_steps(
        pipeline,
        project_root=project_root,
        spec_path=spec_path,
        project=body.project,
        db=db,
        roles=[TaskType.IMPLEMENT],
        memory_task=True,
    )
    if run.status is not RunStatus.COMPLETED:
        failed = next((r for r in run.step_records if r.result and r.result.error_message), None)
        raise SpecWeaverAPIError(
            detail=failed.result.error_message if failed and failed.result else "generation failed",
            error_code="GENERATION_FAILED",
            status_code=500,
        )
    code_path = project_root / "src" / f"{stem}.py"
    test_path = project_root / "tests" / f"test_{stem}.py"

    return ImplementResponse(
        code_path=str(code_path),
        test_path=str(test_path),
        unwritten_calls=unwritten,
    )
