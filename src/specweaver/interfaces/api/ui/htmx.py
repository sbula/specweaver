# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""HTMX fragment endpoints for the Web Dashboard."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse

from specweaver.core.config.database import Database  # noqa: TC001
from specweaver.interfaces.api.deps import get_db

logger = logging.getLogger(__name__)


router = APIRouter(tags=["UI", "HTMX"])


@router.post("/dashboard/runs/{run_id}/gate", response_class=HTMLResponse)
async def submit_hitl_gate(
    request: Request,
    run_id: str,
    action: str = Form(...),
    db: Database = Depends(get_db),  # noqa: B008
) -> HTMLResponse:
    """Handle HITL gate form submissions and return the updated Run Details partial."""
    from specweaver.interfaces.api.errors import SpecWeaverAPIError
    from specweaver.interfaces.api.v1.pipelines import submit_gate_decision
    from specweaver.interfaces.api.v1.schemas import GateDecisionRequest

    try:
        body = GateDecisionRequest(action=action)
        await submit_gate_decision(run_id, body, db)
    except SpecWeaverAPIError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    response = HTMLResponse(content="")
    response.headers["HX-Refresh"] = "true"
    return response
