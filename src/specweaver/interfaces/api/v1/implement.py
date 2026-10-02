# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Implementation API endpoint — POST /implement."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

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

    from specweaver.assurance.graph.loader import load_topology, select_topology_contexts
    from specweaver.core.config.bootstrap.settings_loader import load_settings_async
    from specweaver.infrastructure.llm.models import TaskType
    from specweaver.interfaces.api.v1._llm import api_router
    from specweaver.workflows.implementation.generator import Generator
    from specweaver.workspace.project.constitution import find_constitution

    settings = await load_settings_async(db, body.project)

    router = api_router(project_root, body.project, settings, [TaskType.IMPLEMENT])
    routed = router.get_for_task(TaskType.IMPLEMENT)
    generator = Generator(llm=routed.adapter, config=routed.config)

    # Load topology context
    topo_graph = load_topology(project_root)
    module_name = spec_path.stem.removesuffix("_spec")
    topo_contexts = select_topology_contexts(
        topo_graph,
        module_name,
        selector_name=body.selector,
    )

    # Derive output paths
    stem = spec_path.stem.removesuffix("_spec")
    code_path = project_root / "src" / f"{stem}.py"
    test_path = project_root / "tests" / f"test_{stem}.py"

    from specweaver.assurance.standards.loader import load_standards_content_async

    _info = find_constitution(project_root, spec_path=spec_path)
    constitution = _info.content if _info else None
    standards = await load_standards_content_async(
        db,
        project_name=body.project,
        project_path=project_root,
    )

    try:
        # Generate code
        await generator.generate_code(  # type: ignore[call-arg]
            spec_path,
            code_path,
            topology_contexts=topo_contexts,
            constitution=constitution,
            standards=standards,
        )

        # Generate tests
        await generator.generate_tests(  # type: ignore[call-arg]
            spec_path,
            test_path,
            topology_contexts=topo_contexts,
            constitution=constitution,
            standards=standards,
        )
    finally:
        for collector in router.collectors():
            await collector.flush_async(db)

    return ImplementResponse(
        code_path=str(code_path),
        test_path=str(test_path),
    )
