# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the MIT License. See LICENSE file in the project root.

"""UI Router — HTML endpoints for the SpecWeaver Web Dashboard."""

from __future__ import annotations

from pathlib import Path

import bleach  # type: ignore
import markdown  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from specweaver.api.deps import get_db
from specweaver.api.v1.projects import list_projects
from specweaver.config.database import Database  # noqa: TC001

router = APIRouter(tags=["UI"])

# Locate the templates directory relative to this file
_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


def _render_markdown(text: str | None) -> str:
    """Safely render markdown to HTML."""
    if not text:
        return ""
    html = markdown.markdown(text, extensions=["fenced_code", "tables"])
    allowed_tags = bleach.ALLOWED_TAGS | {"p", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "div", "span", "br", "hr", "table", "thead", "tbody", "tr", "th", "td"}
    return str(bleach.clean(html, tags=allowed_tags))


templates.env.filters["markdown"] = _render_markdown


@router.get("/dashboard", response_class=HTMLResponse)
def get_dashboard_projects(
    request: Request,
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Render the main dashboard page (project list)."""
    projects = list_projects(db)
    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={"title": "Projects - SpecWeaver", "projects": projects},
    )


@router.get("/dashboard/runs", response_class=HTMLResponse)
def get_dashboard_runs(request: Request) -> HTMLResponse:
    """Render the dashboard runs list page."""
    from specweaver.flow.store import StateStore

    state_db = Path.home() / ".specweaver" / "pipeline_state.db"
    store = StateStore(state_db)
    runs = store.list_runs()

    return templates.TemplateResponse(
        request=request,
        name="runs.html",
        context={"title": "Runs - SpecWeaver", "runs": runs},
    )


@router.get("/dashboard/runs/{run_id}", response_class=HTMLResponse)
def get_dashboard_run_detail(request: Request, run_id: str) -> HTMLResponse:
    """Render the details of a specific pipeline run."""
    from specweaver.flow.store import StateStore

    state_db = Path.home() / ".specweaver" / "pipeline_state.db"
    store = StateStore(state_db)

    run = store.load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    events = store.get_audit_log(run_id)

    # Check for pending gate logic to pass pre-computed fields
    pending_gate = False
    pending_gate_prompt = None
    if run.status.value == "parked":
        pending_gate = True
        record = run.current_step_record()
        if record is not None and record.result is not None:
            output = record.result.output
            if isinstance(output, dict):
                pending_gate_prompt = output.get("comment") or output.get("prompt") or str(output)

    return templates.TemplateResponse(
        request=request,
        name="run_detail.html",
        context={
            "title": f"Run {run_id[:8]}",
            "run": run,
            "events": events,
            "pending_gate": pending_gate,
            "pending_gate_prompt": pending_gate_prompt,
        },
    )
