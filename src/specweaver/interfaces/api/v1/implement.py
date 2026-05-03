# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Implementation API endpoint — POST /implement."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.errors import SpecWeaverAPIError
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

    from specweaver.infrastructure.llm.factory import LLMAdapterError, create_llm_adapter
    from specweaver.interfaces.cli._helpers import (
        _load_constitution_content,
        _load_topology,
        _select_topology_contexts,
    )
    from specweaver.interfaces.cli.settings_loader import load_settings_async
    from specweaver.workflows.implementation.generator import Generator

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

    gen_config.temperature = 0.2  # Low temp for code generation

    generator = Generator(llm=adapter, config=gen_config)

    # Load topology context
    topo_graph = _load_topology(project_root)
    module_name = spec_path.stem.removesuffix("_spec")
    topo_contexts = _select_topology_contexts(
        topo_graph,
        module_name,
        selector_name=body.selector,
    )

    # Derive output paths
    stem = spec_path.stem.removesuffix("_spec")
    code_path = project_root / "src" / f"{stem}.py"
    test_path = project_root / "tests" / f"test_{stem}.py"

    from specweaver.assurance.standards.loader import load_standards_content_async

    constitution = _load_constitution_content(project_root, spec_path=spec_path)
    standards = await load_standards_content_async(
        db,
        project_name=body.project,
        project_path=project_root,
    )

    try:
        # Generate code
        await generator.generate_code(
            spec_path,
            code_path,
            topology_contexts=topo_contexts,
            constitution=constitution,
            standards=standards,
        )

        # Generate tests
        await generator.generate_tests(
            spec_path,
            test_path,
            topology_contexts=topo_contexts,
            constitution=constitution,
            standards=standards,
        )
    finally:
        from specweaver.infrastructure.llm.collector import TelemetryCollector

        if isinstance(adapter, TelemetryCollector):
            await adapter.flush_async(db)

    return ImplementResponse(
        code_path=str(code_path),
        test_path=str(test_path),
    )
