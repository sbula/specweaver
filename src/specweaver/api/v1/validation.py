# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Validation API endpoints — POST /check, GET /rules."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from specweaver.api.deps import get_db
from specweaver.api.v1.paths import resolve_file_in_project, validate_relative_path
from specweaver.api.v1.schemas import (
    CheckRequest,
    CheckResponse,
    FindingResponse,
    RuleInfo,
    RuleResultResponse,
)
from specweaver.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI

router = APIRouter()

_db_dep = Depends(get_db)


@router.post("/check", response_model=CheckResponse)
def run_check(
    body: CheckRequest,
    db: Database = _db_dep,
) -> CheckResponse:
    """Run validation rules against a spec or code file."""
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.executor import execute_validation_pipeline
    from specweaver.validation.pipeline_loader import (
        load_pipeline_yaml,
        resolve_pipeline_name,
    )

    validate_relative_path(body.file)
    project_root, abs_path = resolve_file_in_project(body.file, body.project, db)

    content = abs_path.read_text(encoding="utf-8")

    active = db.get_active_project()
    pipeline_name = resolve_pipeline_name(
        body.level,
        body.pipeline,
        db=db,
        active_project=active,
    )

    resolved = load_pipeline_yaml(pipeline_name, project_dir=project_root)
    results = execute_validation_pipeline(resolved, content, abs_path)

    # Build response envelope
    rule_results = [
        RuleResultResponse(
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
        for r in results
    ]

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
    import specweaver.validation.rules.code
    import specweaver.validation.rules.spec  # noqa: F401
    from specweaver.validation.pipeline_loader import load_pipeline_yaml

    rules: list[RuleInfo] = []
    seen: set[str] = set()

    for pname, level in [
        ("validation_spec_default", "spec"),
        ("validation_code_default", "code"),
    ]:
        try:
            resolved = load_pipeline_yaml(pname)
        except FileNotFoundError:
            continue
        for step in resolved.steps:
            if step.rule not in seen:
                seen.add(step.rule)
                rules.append(RuleInfo(id=step.rule, name=step.name, level=level))

    return rules
