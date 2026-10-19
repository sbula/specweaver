# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""WebSocket endpoint for real-time pipeline progress streaming."""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from specweaver.commons import json

logger = logging.getLogger(__name__)


router = APIRouter()

logger = logging.getLogger(__name__)


@router.websocket("/ws/pipeline/{run_id}")
async def pipeline_ws(websocket: WebSocket, run_id: str) -> None:
    """Stream real-time pipeline events over WebSocket.

    Sends NDJSON events as text messages, then ``{"event": "done"}`` and closes when the run ends. A
    run that is not running ends the stream at once: ``done`` if this server ran it, else
    ``RUN_NOT_FOUND``. A client that leaves ends its subscription, so nothing waits for nobody.
    """
    from specweaver.interfaces.api.event_bridge import get_event_bridge

    bridge = get_event_bridge()
    await websocket.accept()

    queue = bridge.subscribe(run_id)
    leaving = asyncio.ensure_future(_until_disconnect(websocket))
    try:
        if not bridge.is_active(run_id):
            ended = (
                {"event": "done"}
                if bridge.knows(run_id)
                else {"event": "error", "error_code": "RUN_NOT_FOUND"}
            )
            await websocket.send_text(json.dumps(ended))
            return
        while True:
            getting = asyncio.ensure_future(queue.get())
            await asyncio.wait({getting, leaving}, return_when=asyncio.FIRST_COMPLETED)
            if not getting.done():
                getting.cancel()
                logger.debug("WebSocket client disconnected for run %s", run_id)
                return
            message = getting.result()
            if message is None:
                await websocket.send_text(json.dumps({"event": "done"}))
                return
            await websocket.send_text(json.dumps(message, default=str))
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected for run %s", run_id)
    finally:
        leaving.cancel()
        bridge.unsubscribe(run_id, queue)


async def _until_disconnect(websocket: WebSocket) -> None:
    """Return when the client leaves; anything it sends meanwhile is ignored."""
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass
