# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Validation API endpoints — POST /check, GET /rules."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.errors import SpecWeaverAPIError
from specweaver.interfaces.api.v1.paths import (
    require_bare_pipeline_name,
    resolve_file_in_project,
    validate_relative_path,
)
from specweaver.interfaces.api.v1.schemas import (
    CheckRequest,
    CheckResponse,
    FindingResponse,
    RuleInfo,
    RuleResultResponse,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


async def _active_domain_profile(db: Database) -> str | None:
    """The active project's `domain_profile`, or None when there is no active project."""
    from specweaver.workspace.store import WorkspaceRepository

    async with db.async_session_scope() as session:
        repo = WorkspaceRepository(session)
        active_name = await repo.get_active_project()
        if not active_name:
            return None
        proj = await repo.get_project(active_name)
        profile = proj.get("domain_profile") if proj else None
    return str(profile) if profile else None


def _rule_response(r: Any) -> RuleResultResponse:
    """One rule's result as its wire envelope."""
    return RuleResultResponse(
        rule_id=r.rule_id,
        rule_name=r.rule_name,
        status=r.status.value,
        message=r.message,
        findings=[
            FindingResponse(
                message=f.message,
                line=f.line,
                severity=f.severity.value,
                suggestion=f.suggestion,
            )
            for f in r.findings
        ],
    )


def _check_pipeline(body: CheckRequest, project_root: Path, active_profile: str | None) -> Any:
    """The validation pipeline `/check` runs: a bare name, the project's own or a packaged one."""
    from specweaver.assurance.validation.pipeline_loader import (
        load_pipeline_yaml,
        resolve_pipeline_name,
    )

    if body.pipeline is not None:
        require_bare_pipeline_name(body.pipeline)
    pipeline_name = resolve_pipeline_name(body.level, body.pipeline, active_profile=active_profile)
    try:
        return load_pipeline_yaml(pipeline_name, project_dir=project_root)
    except FileNotFoundError as exc:
        raise SpecWeaverAPIError(
            detail=f"Pipeline not found: '{pipeline_name}'",
            error_code="PIPELINE_NOT_FOUND",
            status_code=404,
        ) from exc


@router.post("/check", response_model=CheckResponse)
async def run_check(
    body: CheckRequest,
    db: Database = _db_dep,
) -> CheckResponse:
    """Run validation rules against a spec or code file."""
    import specweaver.assurance.validation.rules.code
    import specweaver.assurance.validation.rules.spec  # noqa: F401
    from specweaver.assurance.validation.executor import execute_validation_pipeline

    validate_relative_path(body.file)
    project_root, abs_path = await resolve_file_in_project(body.file, body.project, db)

    content = abs_path.read_text(encoding="utf-8")

    resolved = _check_pipeline(body, project_root, await _active_domain_profile(db))
    if body.level == "code":
        from specweaver.core.config.dal_resolver import DALResolver
        from specweaver.core.flow.handlers.validation_hydrator import execute_validation_flow

        dal_resolver = DALResolver(project_root)
        dal_level = dal_resolver.resolve(abs_path)
        results = execute_validation_flow(
            resolved,
            content,
            abs_path,
            project_root=project_root,
            dal_level=dal_level,
        )
    else:
        results = execute_validation_pipeline(resolved, content, abs_path)

    rule_results = [_rule_response(r) for r in results]

    passed = sum(1 for r in results if r.status.value == "pass")
    failed = sum(1 for r in results if r.status.value == "fail")
    warned = sum(1 for r in results if r.status.value == "warn")
    overall = "FAIL" if failed > 0 else ("WARN" if warned > 0 else "PASS")
    if body.strict and warned > 0:
        overall = "FAIL"

    return CheckResponse(
        results=rule_results,
        overall=overall,
        total=len(results),
        passed=passed,
        failed=failed,
        warned=warned,
    )


@router.get("/rules", response_model=list[RuleInfo])
def list_rules() -> list[RuleInfo]:
    """List all available validation rules."""
    import specweaver.assurance.validation.rules.code
    import specweaver.assurance.validation.rules.spec  # noqa: F401
    from specweaver.assurance.validation.pipeline_loader import load_pipeline_yaml

    rules: list[RuleInfo] = []
    seen: set[str] = set()

    for pname, level in [
        ("validation_spec_default", "spec"),
        ("validation_code_default", "code"),
    ]:
        try:
            resolved = load_pipeline_yaml(pname)
        except FileNotFoundError as exc:
            logger.debug("Pipeline %s is not listed: %s", pname, exc)
            continue
        for step in resolved.steps:
            if step.rule not in seen:
                seen.add(step.rule)
                rules.append(RuleInfo(id=step.rule, name=step.name, level=level))

    return rules
