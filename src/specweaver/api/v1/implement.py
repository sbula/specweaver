# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Implementation API endpoint — POST /implement."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from specweaver.api.deps import get_db
from specweaver.api.errors import SpecWeaverAPIError
from specweaver.api.v1.paths import resolve_file_in_project
from specweaver.api.v1.schemas import ImplementRequest, ImplementResponse
from specweaver.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI

router = APIRouter()

_db_dep = Depends(get_db)


@router.post("/implement", response_model=ImplementResponse)
def implement_spec(
    body: ImplementRequest,
    db: Database = _db_dep,
) -> ImplementResponse:
    """Generate code + tests from a spec file.

    Uses the LLM to generate implementation and test files.
    """
    project_root, spec_path = resolve_file_in_project(body.file, body.project, db)

    from specweaver.cli._helpers import (
        _load_constitution_content,
        _load_topology,
        _select_topology_contexts,
    )
    from specweaver.implementation.generator import Generator
    from specweaver.llm.factory import LLMAdapterError, create_llm_adapter
    from specweaver.standards.loader import load_standards_content

    try:
        _, adapter, gen_config = create_llm_adapter(db)
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
        topo_graph, module_name, selector_name=body.selector,
    )

    # Derive output paths
    stem = spec_path.stem.removesuffix("_spec")
    code_path = project_root / "src" / f"{stem}.py"
    test_path = project_root / "tests" / f"test_{stem}.py"

    constitution = _load_constitution_content(project_root, spec_path=spec_path)
    standards = load_standards_content(
        db, project_name=body.project, project_path=project_root,
    )

    # Generate code
    asyncio.run(
        generator.generate_code(
            spec_path, code_path,
            topology_contexts=topo_contexts,
            constitution=constitution,
            standards=standards,
        ),
    )

    # Generate tests
    asyncio.run(
        generator.generate_tests(
            spec_path, test_path,
            topology_contexts=topo_contexts,
            constitution=constitution,
            standards=standards,
        ),
    )

    return ImplementResponse(
        code_path=str(code_path),
        test_path=str(test_path),
    )
