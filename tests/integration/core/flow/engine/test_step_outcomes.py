# Copyright (c) 2026 sbula. All rights reserved.
# Licensed under the Apache License, Version 2.0. See LICENSE file in the project root.

"""Each step's outcome is stored when its run ends; an unfinished step has none.

Proves: B-FLOW-07 FR-2

The seam: the runner (`core.flow`) writes what its steps' records say into the history
(`infrastructure.llm`), keyed by run and step.

| Bucket | Case |
|---|---|
| Happy | a passed and a failed step are stored as `passed` and `failed` |
| Boundary | a parked run stores no outcome for its parked step; its resume stores `passed` |
| Degradation | not applicable — a run without a database stores nothing, as before |
| Hostile | not applicable — outcomes come from the runner, never from input |
"""

from __future__ import annotations

import json
import sqlite3
from typing import TYPE_CHECKING

import pytest

from specweaver.core.config.bootstrap.db_bootstrap import bootstrap_database
from specweaver.core.config.database import Database
from specweaver.core.flow.engine.models import PipelineDefinition
from specweaver.core.flow.engine.runner import PipelineRunner
from specweaver.core.flow.engine.state import StepResult, StepStatus
from specweaver.core.flow.engine.store import StateStore
from specweaver.core.flow.handlers.registry import StepHandlerRegistry
from specweaver.core.flow.handlers.run_context import RunContext

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.integration


class _Ends:
    def __init__(self, *statuses: StepStatus) -> None:
        self._statuses = list(statuses)

    async def execute(self, _step, _context) -> StepResult:
        status = self._statuses.pop(0) if len(self._statuses) > 1 else self._statuses[0]
        return StepResult(status=status, output={}, started_at="t0", completed_at="t1")


def _setup(tmp_path: Path, first: _Ends, second: _Ends):
    db_path = tmp_path / "specweaver.db"
    bootstrap_database(str(db_path))
    registry = StepHandlerRegistry()
    registry.register("review", "spec", first)
    registry.register("review", "code", second)
    pipeline = PipelineDefinition.model_validate_json(
        json.dumps(
            {
                "name": "p",
                "steps": [
                    {"name": "one", "action": "review", "target": "spec"},
                    {"name": "two", "action": "review", "target": "code"},
                ],
            }
        )
    )

    def make() -> PipelineRunner:
        context = RunContext(
            project_path=tmp_path, spec_path=tmp_path / "a_spec.md", db=Database(db_path)
        )
        return PipelineRunner(
            pipeline, context, registry=registry, store=StateStore(tmp_path / "state.db")
        )

    return db_path, make


def _outcomes(db_path: Path) -> dict[str, str]:
    with sqlite3.connect(db_path) as conn:
        return dict(conn.execute("SELECT step_name, outcome FROM llm_step_outcome").fetchall())


async def test_passed_and_failed_steps_are_stored(tmp_path: Path) -> None:
    db_path, make = _setup(tmp_path, _Ends(StepStatus.PASSED), _Ends(StepStatus.FAILED))

    await make().run()

    assert _outcomes(db_path) == {"one": "passed", "two": "failed"}


async def test_a_parked_step_has_no_outcome_until_its_resume_ends(tmp_path: Path) -> None:
    second = _Ends(StepStatus.WAITING_FOR_INPUT, StepStatus.PASSED)
    db_path, make = _setup(tmp_path, _Ends(StepStatus.PASSED), second)

    parked = await make().run()
    assert _outcomes(db_path) == {"one": "passed"}

    await make().resume(parked.run_id)
    assert _outcomes(db_path) == {"one": "passed", "two": "passed"}
