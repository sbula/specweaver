# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""WebSocket endpoint for real-time pipeline progress streaming."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


router = APIRouter()

logger = logging.getLogger(__name__)


@router.websocket("/ws/pipeline/{run_id}")
async def pipeline_ws(websocket: WebSocket, run_id: str) -> None:
    """Stream real-time pipeline events over WebSocket.

    Sends NDJSON events as text messages. Sends a final
    ``{"event": "done"}`` and closes when the run completes.
    """
    from specweaver.api.app import get_event_bridge

    bridge = get_event_bridge()
    await websocket.accept()

    queue = bridge.subscribe(run_id)
    try:
        while True:
            message = await queue.get()
            if message is None:
                # Run completed — send final event and close
                await websocket.send_text(json.dumps({"event": "done"}))
                break
            await websocket.send_text(json.dumps(message, default=str))
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected for run %s", run_id)
    finally:
        bridge.unsubscribe(run_id, queue)
