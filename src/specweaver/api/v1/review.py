# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Review API endpoint — POST /review."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from specweaver.api.deps import get_db
from specweaver.api.errors import SpecWeaverAPIError
from specweaver.api.v1.paths import resolve_file_in_project
from specweaver.api.v1.schemas import ReviewRequest  # noqa: TC001 -- runtime for FastAPI
from specweaver.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI

router = APIRouter()

_db_dep = Depends(get_db)


@router.post("/review")
def review_spec(
    body: ReviewRequest,
    db: Database = _db_dep,
) -> dict[str, object]:
    """Run an LLM-powered review of a spec file (blocking).

    Returns the ReviewResult as a dict.
    """
    project_root, abs_path = resolve_file_in_project(body.file, body.project, db)

    from specweaver.cli._helpers import _load_constitution_content
    from specweaver.llm.factory import LLMAdapterError, create_llm_adapter
    from specweaver.review.reviewer import Reviewer
    from specweaver.standards.loader import load_standards_content

    try:
        _, adapter, gen_config = create_llm_adapter(
            db, telemetry_project=body.project,
        )
    except (LLMAdapterError, ValueError) as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="LLM_ERROR",
            status_code=500,
        ) from exc

    reviewer = Reviewer(llm=adapter, config=gen_config)

    constitution = _load_constitution_content(project_root, spec_path=abs_path)
    standards = load_standards_content(
        db, project_name=body.project, project_path=project_root,
    )

    try:
        result = asyncio.run(
            reviewer.review_spec(
                abs_path,
                constitution=constitution,
                standards=standards,
            ),
        )
    finally:
        from specweaver.llm.collector import TelemetryCollector

        if isinstance(adapter, TelemetryCollector):
            adapter.flush(db)

    return result.model_dump()
