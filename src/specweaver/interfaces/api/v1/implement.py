# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Implementation API endpoint — POST /implement."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from fastapi import APIRouter, Depends

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.v1.paths import resolve_file_in_project
from specweaver.interfaces.api.v1.schemas import (
    ImplementRequest,
    ImplementResponse,
    ImplementTests,
    ImplementValidation,
)

if TYPE_CHECKING:
    from pathlib import Path

    from specweaver.core.flow.engine.state import PipelineRun
    from specweaver.core.flow.engine.task_files import TaskFiles

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.post("/implement", response_model=ImplementResponse)
async def implement_spec(
    body: ImplementRequest,
    db: Database = _db_dep,
) -> ImplementResponse:
    """Run the implement pipeline `sw implement` runs: code, tests, lint fix, the tests with their
    loop back to generation, validation. Tests still failing after the loop answer 200 `failed`.
    """
    project_root, spec_path = await resolve_file_in_project(body.file, body.project, db)

    from specweaver.core.flow.engine.parser import load_bundled_pipeline
    from specweaver.interfaces.api.v1._llm import run_steps

    task = _task_files(project_root, spec_path)
    run, unwritten = await run_steps(
        load_bundled_pipeline("implement_spec"),
        project_root=project_root,
        spec_path=spec_path,
        project=body.project,
        db=db,
        memory_task=True,
        selector=body.selector,
    )
    outputs = _outputs_by_step(run)
    return ImplementResponse(
        code_path=str(project_root / task.code),
        test_path=str(project_root / task.tests),
        status=_status(run),
        tests=_tests(outputs.get("run_tests")),
        lint_errors_remaining=(outputs.get("lint_fix") or {}).get("lint_errors_remaining"),
        validation=_validation(outputs.get("validate_code")),
        unwritten_calls=unwritten,
    )


def _task_files(project_root: Path, spec_path: Path) -> TaskFiles:
    """The task's files in the project's `[implement]` language; a bad setting is a 500 naming it,
    a spec whose `Package` line is not a package a 400 naming the line."""
    from specweaver.core.config.bootstrap.project_settings import load_section
    from specweaver.core.config.implement_policy import parse_implement
    from specweaver.core.config.settings_file import SettingsFileError
    from specweaver.core.flow.engine.task_files import task_files_for
    from specweaver.interfaces.api.errors import SpecWeaverAPIError
    from specweaver.interfaces.api.v1.run_doors import settings_error_code

    try:
        language = load_section(project_root, parse_implement).language
    except SettingsFileError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc), error_code=settings_error_code(exc), status_code=500
        ) from exc
    try:
        return task_files_for(project_root, spec_path, language)
    except ValueError as exc:
        raise SpecWeaverAPIError(detail=str(exc), error_code="SPEC_INVALID") from exc


def _outputs_by_step(run: PipelineRun) -> dict[str, dict[str, Any]]:
    """Each step's last output, by step name."""
    return {r.step_name: (r.result.output if r.result else {}) for r in run.step_records}


def _status(run: PipelineRun) -> Literal["completed", "failed"]:
    """`completed`, or `failed` when the tests still fail after the loop; any other stop is a 500
    naming the failing step's error."""
    from specweaver.core.flow.engine.state import RunStatus, StepStatus
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

    if run.status is RunStatus.COMPLETED:
        return "completed"
    stopped = next(
        (r for r in run.step_records if r.status in (StepStatus.FAILED, StepStatus.ERROR)), None
    )
    if stopped is not None and (stopped.step_name, stopped.status) == (
        "run_tests",
        StepStatus.FAILED,
    ):
        return "failed"
    failed = next((r for r in run.step_records if r.result and r.result.error_message), None)
    message = failed.result.error_message if failed and failed.result else "generation failed"
    raise SpecWeaverAPIError(
        # The step's message can carry a traceback for the log; the client gets the message only.
        detail=message.split("\nTraceback", 1)[0],
        error_code="GENERATION_FAILED",
        status_code=500,
    )


def _tests(output: dict[str, Any] | None) -> ImplementTests | None:
    if output is None:
        return None
    return ImplementTests(
        passed=output.get("passed", 0),
        failed=output.get("failed", 0),
        coverage_pct=output.get("coverage_pct"),
    )


def _validation(output: dict[str, Any] | None) -> ImplementValidation | None:
    if output is None:
        return None
    failed = [
        str(r.get("rule_id"))
        for r in output.get("results", [])
        if str(r.get("status", "")).lower().startswith("fail")
    ]
    return ImplementValidation(
        passed=output.get("passed", 0), total=output.get("total", 0), failed_rules=failed
    )
