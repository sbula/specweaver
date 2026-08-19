# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Pipeline execution API endpoints — list, run, status, log, resume, gate."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Query

from specweaver.core.config.database import Database  # noqa: TC001 -- runtime for FastAPI DI
from specweaver.core.config.paths import state_db_path
from specweaver.core.flow.handlers.run_context import RunContext
from specweaver.interfaces.api.deps import get_db
from specweaver.interfaces.api.v1.paths import resolve_project_root
from specweaver.interfaces.api.v1.schemas import (
    GateDecisionRequest,
    PipelineRunRequest,
    PipelineRunResponse,
)

logger = logging.getLogger(__name__)


router = APIRouter()

_db_dep = Depends(get_db)


@router.get("/pipelines")
def list_pipelines() -> list[dict[str, str]]:
    """List available pipeline templates."""
    logger.debug("Executing list_pipelines API endpoint")
    from specweaver.core.flow.engine.parser import list_bundled_pipelines

    names = list_bundled_pipelines()
    return [{"name": n, "source": "bundled"} for n in names]


async def _resume_existing_run(run: Any, run_id: str, db: Database, store: Any) -> None:
    """Rebuild a parked run's context and hand it back to the bridge.

    `resume_run` and `submit_gate_decision` both do exactly this — a gate decision resumes the run it
    unblocks — and they carried the same thirty lines twice. The isolation policy is one line each of
    them needs, and a shared block is one place to forget it rather than two.
    """
    from specweaver.core.flow.engine.parser import load_pipeline
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

    project_root = await resolve_project_root(run.project_name, db)
    pipeline_def = load_pipeline(Path(run.pipeline_name))
    context = RunContext(
        project_path=project_root,
        spec_path=Path(run.spec_path),
        output_dir=project_root / "src",
    )
    await _apply_isolation(context, db, run.project_name)

    from specweaver.interfaces.api.event_bridge import get_event_bridge

    bridge = get_event_bridge()
    runner = PipelineRunner(
        pipeline_def,
        context,
        store=store,
        on_event=bridge.make_event_callback(run_id),
    )

    try:
        bridge.start_run(run_id, runner.resume(run_id))
    except RuntimeError as exc:
        raise SpecWeaverAPIError(
            detail=str(exc),
            error_code="MAX_CONCURRENT_RUNS",
            status_code=429,
        ) from exc


async def _apply_isolation(context: RunContext, db: Database, project: str) -> None:
    """Resolve the worktree-isolation policy for an API-triggered run.

    `ADR-002` puts this decision at the composition root, and there are two: the CLI's `sw run` /
    `sw resume`, and these endpoints. Only the CLI resolved it, so an API-launched run executed with
    isolation OFF whatever `[sandbox]` declared — untrusted generated code running against the real
    worktree because of which door the run came through.

    Async on purpose: the settings loader has an async form, and calling the sync one inside an
    endpoint would block the event loop.
    """
    from specweaver.core.config.bootstrap.settings_loader import load_settings_async
    from specweaver.core.flow.engine.isolation import apply_isolation_policy

    try:
        settings = await load_settings_async(db, project)
    except Exception:  # best-effort by contract — a policy lookup must not fail a run
        logger.debug("Could not resolve settings for '%s'; isolation defaults to off.", project)
        return
    apply_isolation_policy(context, settings, logger)


@router.post("/pipelines/{name}/run", response_model=PipelineRunResponse)
async def start_pipeline_run(
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

    from specweaver.core.flow.engine.parser import load_pipeline
    from specweaver.core.flow.engine.runner import PipelineRunner
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

    # Resolve project
    project_root = await resolve_project_root(body.project, db)

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
    await _apply_isolation(context, db, body.project)

    # State store
    state_db = state_db_path()
    store = StateStore(state_db)

    # Get or create event bridge
    from specweaver.interfaces.api.event_bridge import get_event_bridge

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


def _pending_gate_prompt(run: Any) -> str | None:
    """The prompt a parked run is waiting on, read from the paused step's output.

    A dict output is searched for `comment` then `prompt` before falling back to its repr, so the
    dashboard shows the gate's question rather than the whole payload where one was supplied.
    """
    record = run.current_step_record()
    if record is None or record.result is None:
        return None
    output = record.result.output
    if isinstance(output, dict):
        return str(output.get("comment") or output.get("prompt") or output)
    return str(output)


@router.get("/runs/{run_id}")
def get_run_status(
    run_id: str,
    detail: str = Query(default="summary", description="'summary' or 'full'."),
) -> dict[str, object]:
    """Get run status and step results."""
    logger.debug("Executing get_run_status API endpoint")
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

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
    data["pending_gate"] = run.status.value == "parked"
    data["pending_gate_prompt"] = _pending_gate_prompt(run) if data["pending_gate"] else None

    return data


@router.get("/runs/{run_id}/log")
def get_run_log(run_id: str) -> list[dict[str, object]]:
    """Get audit log for a pipeline run."""
    logger.debug("Executing get_run_log API endpoint")
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

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
async def resume_run(
    run_id: str,
    db: Database = _db_dep,
) -> PipelineRunResponse:
    """Resume a parked pipeline run."""
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

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
    await _resume_existing_run(run, run_id, db, store)

    return PipelineRunResponse(
        run_id=run_id,
        detail=f"Run '{run_id}' resumed.",
    )


@router.post("/runs/{run_id}/gate")
async def submit_gate_decision(
    run_id: str,
    body: GateDecisionRequest,
    db: Database = _db_dep,
) -> dict[str, str]:
    """Submit a HITL gate decision (approve/reject).

    On approve, the run is resumed as a background task.
    """
    from specweaver.core.flow.engine.store import StateStore
    from specweaver.interfaces.api.errors import SpecWeaverAPIError

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
        from specweaver.core.flow.engine.state import RunStatus

        run.status = RunStatus.FAILED
        store.save_run(run)
        return {"detail": f"Run '{run_id}' rejected and marked as failed."}

    # Approve → resume

    await _resume_existing_run(run, run_id, db, store)

    return {"detail": f"Run '{run_id}' approved and resumed."}
