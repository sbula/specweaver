# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Review API endpoint — POST /review."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.errors import SpecWeaverAPIError
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

    from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter
    from specweaver.interfaces.cli._helpers import _load_constitution_content
    from specweaver.interfaces.cli.settings_loader import load_settings_async
    from specweaver.workflows.review.reviewer import Reviewer

    settings = await load_settings_async(db, body.project)

    try:
        _, adapter, gen_config = create_llm_adapter(
            settings,
            telemetry_project=body.project,
        )
    except (LLMAdapterError, ValueError) as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="LLM_ERROR",
            status_code=500,
        ) from exc

    from specweaver.assurance.standards.loader import load_standards_content_async

    reviewer = Reviewer(llm=adapter, config=gen_config)

    constitution = _load_constitution_content(project_root, spec_path=abs_path)
    standards = await load_standards_content_async(
        db,
        project_name=body.project,
        project_path=project_root,
    )

    try:
        result = await reviewer.review_spec(
            abs_path,
            constitution=constitution,
            standards=standards,
        )
    finally:
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        if isinstance(adapter, TelemetryCollector):
            await adapter.flush_async(db)

    return result.model_dump()
