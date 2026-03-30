# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""Pipeline execution API endpoints — list, run, status, log, resume, gate."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Query

from specweaver.api.deps import get_db
from specweaver.api.v1.paths import resolve_project_root
from specweaver.api.v1.schemas import (
    GateDecisionRequest,
    PipelineRunRequest,
    PipelineRunResponse,
)
from specweaver.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.config.paths import state_db_path

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.get("/pipelines")
def list_pipelines() -> list[dict[str, str]]:
    """List available pipeline templates."""
    from specweaver.flow.parser import list_bundled_pipelines

    names = list_bundled_pipelines()
    return [{"name": n, "source": "bundled"} for n in names]


@router.post("/pipelines/{name}/run", response_model=PipelineRunResponse)
def start_pipeline_run(
    name: str,
    body: PipelineRunRequest,
    db: Database = _db_dep,
) -> PipelineRunResponse:
    """Start a pipeline run (fire-and-forget).

    Returns immediately with a ``run_id``. The pipeline executes
    in a background asyncio task. Monitor progress via
    ``GET /runs/{run_id}`` or ``WS /ws/pipeline/{run_id}``.
    """
    import uuid

    from specweaver.api.errors import SpecWeaverAPIError
    from specweaver.flow.handlers import RunContext
    from specweaver.flow.parser import load_pipeline
    from specweaver.flow.runner import PipelineRunner
    from specweaver.flow.store import StateStore

    # Resolve project
    project_root = resolve_project_root(body.project, db)

    # Load pipeline definition
    try:
        pipeline_def = load_pipeline(Path(name))
    except (FileNotFoundError, ValueError) as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="PIPELINE_NOT_FOUND",
            status_code=404,
        ) from exc

    # Resolve spec path
    spec_path = project_root / body.spec
    if not spec_path.exists():
        raise SpecWeaverAPIError(
            detail=f"Spec file not found: {body.spec}",
            error_code="FILE_NOT_FOUND",
            status_code=404,
        )

    # Build context
    context = RunContext(
        project_path=project_root,
        spec_path=spec_path,
        output_dir=project_root / "src",
    )

    # State store
    state_db = state_db_path()
    store = StateStore(state_db)

    # Get or create event bridge
    from specweaver.api.app import get_event_bridge

    bridge = get_event_bridge()

    # Build runner
    run_id = str(uuid.uuid4())
    event_cb = bridge.make_event_callback(run_id)
    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=event_cb,
    )

    # Start background run
    try:
        bridge.start_run(run_id, runner.run())
    except RuntimeError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="MAX_CONCURRENT_RUNS",
            status_code=429,
        ) from exc

    return PipelineRunResponse(
        run_id=run_id,
        detail=f"Pipeline '{name}' started as run '{run_id}'.",
    )


@router.get("/runs/{run_id}")
def get_run_status(
    run_id: str,
    detail: str = Query(default="summary", description="'summary' or 'full'."),
) -> dict[str, object]:
    """Get run status and step results."""
    from specweaver.api.errors import SpecWeaverAPIError
    from specweaver.flow.store import StateStore

    state_db = state_db_path()
    store = StateStore(state_db)

    run = store.load_run(run_id)
    if run is None:
        raise SpecWeaverAPIError(
            detail=f"Run '{run_id}' not found.",
            error_code="RUN_NOT_FOUND",
            status_code=404,
        )

    data = run.model_dump()
    if detail == "summary":
        # Strip heavy step result details
        for rec in data.get("step_records", []):
            if rec.get("result"):
                rec["result"].pop("output", None)

    # Dashboard helper fields
    data["pending_gate"] = False
    data["pending_gate_prompt"] = None
    if run.status.value == "parked":
        data["pending_gate"] = True
        record = run.current_step_record()
        if record is not None and record.result is not None:
            # We look for a prompt/comment in the output of the paused step
            output = record.result.output
            if isinstance(output, dict):
                data["pending_gate_prompt"] = (
                    output.get("comment") or output.get("prompt") or str(output)
                )
            else:
                data["pending_gate_prompt"] = str(output)

    return data


@router.get("/runs/{run_id}/log")
def get_run_log(run_id: str) -> list[dict[str, object]]:
    """Get audit log for a pipeline run."""
    from specweaver.api.errors import SpecWeaverAPIError
    from specweaver.flow.store import StateStore

    state_db = state_db_path()
    store = StateStore(state_db)

    run = store.load_run(run_id)
    if run is None:
        raise SpecWeaverAPIError(
            detail=f"Run '{run_id}' not found.",
            error_code="RUN_NOT_FOUND",
            status_code=404,
        )

    return store.get_audit_log(run_id)


@router.post("/runs/{run_id}/resume")
def resume_run(
    run_id: str,
    db: Database = _db_dep,
) -> PipelineRunResponse:
    """Resume a parked pipeline run."""
    from specweaver.api.errors import SpecWeaverAPIError
    from specweaver.flow.handlers import RunContext
    from specweaver.flow.parser import load_pipeline
    from specweaver.flow.runner import PipelineRunner
    from specweaver.flow.store import StateStore

    state_db = state_db_path()
    store = StateStore(state_db)

    run = store.load_run(run_id)
    if run is None:
        raise SpecWeaverAPIError(
            detail=f"Run '{run_id}' not found.",
            error_code="RUN_NOT_FOUND",
            status_code=404,
        )

    if run.status.value != "parked":
        raise SpecWeaverAPIError(
            detail=f"Run '{run_id}' is not parked (status={run.status.value}).",
            error_code="RUN_NOT_PARKED",
            status_code=409,
        )

    # Rebuild context
    project_root = resolve_project_root(run.project_name, db)
    pipeline_def = load_pipeline(Path(run.pipeline_name))
    context = RunContext(
        project_path=project_root,
        spec_path=Path(run.spec_path),
        output_dir=project_root / "src",
    )

    from specweaver.api.app import get_event_bridge

    bridge = get_event_bridge()
    event_cb = bridge.make_event_callback(run_id)
    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=event_cb,
    )

    try:
        bridge.start_run(run_id, runner.resume(run_id))
    except RuntimeError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="MAX_CONCURRENT_RUNS",
            status_code=429,
        ) from exc

    return PipelineRunResponse(
        run_id=run_id,
        detail=f"Run '{run_id}' resumed.",
    )


@router.post("/runs/{run_id}/gate")
def submit_gate_decision(
    run_id: str,
    body: GateDecisionRequest,
    db: Database = _db_dep,
) -> dict[str, str]:
    """Submit a HITL gate decision (approve/reject).

    On approve, the run is resumed as a background task.
    """
    from specweaver.api.errors import SpecWeaverAPIError
    from specweaver.flow.store import StateStore

    state_db = state_db_path()
    store = StateStore(state_db)

    run = store.load_run(run_id)
    if run is None:
        raise SpecWeaverAPIError(
            detail=f"Run '{run_id}' not found.",
            error_code="RUN_NOT_FOUND",
            status_code=404,
        )

    if run.status.value != "parked":
        raise SpecWeaverAPIError(
            detail=f"Run '{run_id}' is not parked (status={run.status.value}).",
            error_code="RUN_NOT_PARKED",
            status_code=409,
        )

    if body.action not in ("approve", "reject"):
        raise SpecWeaverAPIError(
            detail=f"Invalid action '{body.action}'. Use 'approve' or 'reject'.",
            error_code="INVALID_ACTION",
            status_code=400,
        )

    # Log the decision
    store.log_event(run_id, f"gate_{body.action}")

    if body.action == "reject":
        # Mark as failed
        from specweaver.flow.state import RunStatus

        run.status = RunStatus.FAILED
        store.save_run(run)
        return {"detail": f"Run '{run_id}' rejected and marked as failed."}

    # Approve → resume
    from specweaver.flow.handlers import RunContext
    from specweaver.flow.parser import load_pipeline
    from specweaver.flow.runner import PipelineRunner

    project_root = resolve_project_root(run.project_name, db)
    pipeline_def = load_pipeline(Path(run.pipeline_name))
    context = RunContext(
        project_path=project_root,
        spec_path=Path(run.spec_path),
        output_dir=project_root / "src",
    )

    from specweaver.api.app import get_event_bridge

    bridge = get_event_bridge()
    event_cb = bridge.make_event_callback(run_id)
    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=event_cb,
    )

    try:
        bridge.start_run(run_id, runner.resume(run_id))
    except RuntimeError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="MAX_CONCURRENT_RUNS",
            status_code=429,
        ) from exc

    return {"detail": f"Run '{run_id}' approved and resumed."}
