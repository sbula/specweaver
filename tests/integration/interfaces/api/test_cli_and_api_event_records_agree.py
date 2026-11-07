# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""`sw run --json` and the API's event stream give a runner event the same record.

Both are built by one function, `core.flow.engine.events.event_record`; this test drives the two
real consumers with the same events and compares what each one emits.

Proves: TECH-090 FR-14

| Bucket | Case |
|---|---|
| Happy | a step start, a step end with a result and a run end give equal records |
| Boundary | an event with no fields gives only `event` |
| Degradation | a failed step's error message is carried; an empty one is `None` |
| Hostile | unknown keyword fields are dropped by both, never passed through |
"""

from __future__ import annotations

import asyncio
import io
import json
from types import SimpleNamespace
from typing import Any

import pytest

from specweaver.core.flow.engine.display import JsonPipelineDisplay
from specweaver.core.flow.engine.events import event_record
from specweaver.core.flow.engine.state import RunStatus, StepResult, StepStatus
from specweaver.interfaces.api.event_bridge import EventBridge

pytestmark = pytest.mark.integration

_PASSED = StepResult(status=StepStatus.PASSED, output={"ok": 1}, started_at="t0", completed_at="t1")
_FAILED = StepResult(status=StepStatus.FAILED, error_message="", started_at="t0", completed_at="t1")
_RUN = SimpleNamespace(run_id="run-1", status=RunStatus.COMPLETED)

_EVENTS: list[tuple[str, dict[str, Any]]] = [
    ("run_started", {}),
    ("step_started", {"step_idx": 0, "step_name": "a", "total_steps": 2}),
    ("step_completed", {"step_idx": 0, "step_name": "a", "total_steps": 2, "result": _PASSED}),
    ("step_failed", {"step_idx": 1, "step_name": "b", "result": _FAILED, "verdict": "fail"}),
    ("run_completed", {"run": _RUN, "secret": "never sent"}),
]


def _from_the_cli() -> list[dict[str, Any]]:
    out = io.StringIO()
    display = JsonPipelineDisplay(output=out)
    for event, kwargs in _EVENTS:
        display(event, **kwargs)
    return [json.loads(line) for line in out.getvalue().splitlines()]


async def _from_the_api() -> list[dict[str, Any]]:
    bridge = EventBridge()
    queue = bridge.subscribe("run-1")
    callback = bridge.make_event_callback("run-1")
    for event, kwargs in _EVENTS:
        callback(event, **kwargs)
    await asyncio.sleep(0)
    records = [queue.get_nowait() for _ in _EVENTS]
    return json.loads(json.dumps(records, default=str))


async def test_the_cli_and_the_api_emit_the_same_records() -> None:
    expected = [json.loads(json.dumps(event_record(e, **k), default=str)) for e, k in _EVENTS]

    assert _from_the_cli() == expected
    assert await _from_the_api() == expected


def test_the_record_carries_only_known_fields() -> None:
    assert event_record("run_started") == {"event": "run_started"}
    assert event_record("run_completed", run=_RUN, secret="x") == {
        "event": "run_completed",
        "run_id": "run-1",
        "run_status": "completed",
    }
    assert event_record("step_failed", result=_FAILED)["result"] == {
        "status": "failed",
        "error_message": None,
        "output": {},
    }
